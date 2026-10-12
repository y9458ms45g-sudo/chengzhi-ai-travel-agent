"""
FastAPI 入口
"""
import json
import time
import secrets as _secrets
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.agent import should_reset, reflect
from app.agent.executor import run_agent, run_agent_stream, Session, IP_NAME_MAP
from app import db

app = FastAPI(title="城知文旅Agent")
_START_TS = __import__("time").time()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    db.init_db()
    # 双写日志：控制台 + data/logs/agent_YYYYMMDD.log
    import os, time, logging, builtins
    from logging.handlers import RotatingFileHandler

    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"agent_{time.strftime('%Y%m%d')}.log")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # 清掉重复 handler（uvicorn 重启时可能叠加）
    for h in list(logger.handlers):
        logger.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = RotatingFileHandler(log_path, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)

    # 把所有内置 print 自动双写到日志
    _orig_print = builtins.print
    def _patched_print(*args, **kwargs):
        msg = " ".join(str(a) for a in args)
        logging.info(msg)
    builtins.print = _patched_print

    logging.info("===== startup at %s =====", time.strftime("%Y-%m-%d %H:%M:%S"))
    logging.info("log file: %s", log_path)


class TripRequest(BaseModel):
    user_input: str
    session_id: str = "default"
    current_ip: str = "master"


def _build_session(session_id: str, current_ip: str) -> Session:
    """根据 session_id 从 SQLite 恢复历史对话上下文。
    上下文裁剪：只回灌最近 10 轮 user/assistant（20 条），防止长对话爆 token。"""
    history = db.load_history(session_id)
    # 只保留 user/assistant
    chat_msgs = [h for h in history if h["role"] in ("user", "assistant")]
    # 最近 15 轮 = 最近 30 条（兼顾长程记忆与 token 控制）
    MAX_RECENT = 30
    if len(chat_msgs) > MAX_RECENT:
        chat_msgs = chat_msgs[-MAX_RECENT:]
    messages = [{"role": h["role"], "content": h["content"]} for h in chat_msgs]
    return Session(messages=messages, current_ip=current_ip)


@app.post("/api/trip")
def generate_trip(req: TripRequest):
    if should_reset(req.user_input, "", 0):
        db.clear_messages(req.session_id)
    session = _build_session(req.session_id, req.current_ip)
    draft = run_agent(req.user_input, session)
    checked = reflect(draft)
    return {
        "draft": draft,
        "review": checked,
        "final": checked.get("corrected_draft", draft),
    }


@app.post("/api/trip/stream")
def generate_trip_stream(req: TripRequest):
    db.ensure_session(req.session_id, req.current_ip)
    # 注意：should_reset 的轮次/天数判断已移到 run_agent_stream 内部
    # 这里只做关键词级别的提前清空（双保险）
    from app.agent.executor import RESET_KEYWORDS
    if any(kw in req.user_input for kw in RESET_KEYWORDS):
        db.clear_messages(req.session_id)

    session = _build_session(req.session_id, req.current_ip)

    def event_gen():
        try:
            for event in run_agent_stream(req.user_input, session, session_id=req.session_id):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/history")
def get_history(session_id: str = "default"):
    """返回某会话的历史消息，供前端刷新后渲染"""
    db.ensure_session(session_id)
    history = db.load_history(session_id)
    current_ip = db.get_current_ip(session_id)
    return {
        "session_id": session_id,
        "current_ip": current_ip,
        "messages": history,
    }


@app.get("/api/ip_map")
def ip_map():
    """返回城市识别 → 前端 IP 的映射，供前端展示"""
    return {"ip_name_map": IP_NAME_MAP}


@app.get("/api/health")
def health():
    import time
    return {"status": "ok", "service": "城知文旅Agent", "version": "1.0", "uptime_s": int(time.time() - _START_TS)}


# ============================================================
# 对外端口 1：OpenAI 兼容接口（外部应用用标准 SDK 调用本 Agent）
# POST /v1/chat/completions
# Body: { "messages": [{"role":"user","content":"重庆有什么好吃的"}], "session_id": "xxx" }
# 返回: OpenAI 格式
# ============================================================
class ChatMessage(BaseModel):
    role: str
    content: str

class OpenAICompatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str = "openai_compat"
    current_ip: str = "master"
    temperature: float = 0.7
    stream: bool = False

@app.post("/v1/chat/completions")
def openai_compat(req: OpenAICompatRequest):
    """OpenAI 兼容接口：外部系统用 openai-python SDK 即可接入。"""
    # 取最后一条 user 消息作为本轮输入
    last_user = ""
    for m in reversed(req.messages):
        if m.role == "user":
            last_user = m.content
            break
    if not last_user:
        return {"error": "no user message"}

    db.ensure_session(req.session_id, req.current_ip)
    session = _build_session(req.session_id, req.current_ip)

    # 跑 Agent（非流式）
    final_text = ""
    for ev in run_agent_stream(last_user, session, session_id=req.session_id):
        if ev.get("type") == "token":
            final_text += ev.get("text", "")
        elif ev.get("type") == "done":
            final_text = ev.get("text", final_text)
        elif ev.get("type") == "error":
            return {"error": ev.get("message", "agent error")}

    return {
        "id": "chatcmpl-" + _secrets.token_hex(8),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "chengzhi-travel-agent",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": final_text},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    }


# ============================================================
# 对外端口 2：Harness 评测接口（批量跑测试用例）
# POST /harness/eval
# Body: { "cases": [{"id": "t1", "input": "重庆3天怎么玩", "expect": "..."}], "reset": true }
# 返回: { "results": [{"id": "t1", "input": "...", "output": "...", "pass": true/false, "reason": "..."}] }
# ============================================================
class EvalCase(BaseModel):
    id: str = ""
    input: str
    expect: str = ""

class EvalRequest(BaseModel):
    cases: list[EvalCase]
    reset: bool = True  # 每个用例用全新会话，互不污染

@app.post("/harness/eval")
def harness_eval(req: EvalRequest):
    """Harness 批量评测：逐条跑 Agent，返回完整回答供自动/人工评分。"""
    results = []
    for i, c in enumerate(req.cases):
        sid = f"eval_{int(time.time())}_{i}" if req.reset else "eval_shared"
        db.ensure_session(sid, "master")
        session = _build_session(sid, "master")
        out = ""
        try:
            for ev in run_agent_stream(c.input, session, session_id=sid):
                if ev.get("type") == "token":
                    out += ev.get("text", "")
                elif ev.get("type") == "done":
                    out = ev.get("text", out)
            # 简单自动评分：如果 expect 不为空，检查关键词是否在输出里
            passed = True
            reason = ""
            if c.expect:
                keywords = [k.strip() for k in c.expect.split("，") if k.strip()]
                missing = [k for k in keywords if k not in out]
                if missing:
                    passed = False
                    reason = f"缺少关键词: {', '.join(missing)}"
                else:
                    reason = "关键词全部命中"
            results.append({"id": c.id or f"case_{i}", "input": c.input, "output": out,
                           "pass": passed, "reason": reason})
        except Exception as e:
            results.append({"id": c.id or f"case_{i}", "input": c.input, "output": "",
                           "pass": False, "reason": f"运行异常: {e}"})
    return {"total": len(results), "passed": sum(1 for r in results if r["pass"]),
            "results": results}


@app.get("/harness")
def harness_page():
    return {"service": "城知 Harness 评测接口", "usage": "POST /harness/eval",
            "body": {"cases": [{"id": "t1", "input": "重庆3天怎么玩", "expect": "火锅,洪崖洞"}]}}


@app.get("/dev")
def dev_page():
    return FileResponse(os.path.join(WEB_DIR, "dev.html"))


@app.get("/api/dev/status")
def dev_status(authorization: str = Header(default="")):
    require_admin(authorization)
    s = db.admin_stats()
    import time
    return {**s, "uptime_s": int(time.time() - _START_TS), "version": "1.0"}


@app.get("/api/amap-key")
def amap_key(ip: str = ""):
    import os
    from dotenv import load_dotenv
    from app.agent.executor import IP_CITY_NAME
    load_dotenv()
    city = IP_CITY_NAME.get(ip, "成都") if ip else "成都"
    return {"key": os.getenv("AMAP_API_KEY", ""), "city": city}


@app.post("/api/speech-fix")
def speech_fix(req: dict):
    """语音识别后校正：把识别成英文的内容转回中文。
    body: {text: 识别结果}
    返回: {text: 校正后中文}"""
    from app.llm import chat
    text = (req.get("text") or "").strip()
    if not text:
        return {"text": text}
    import re as _re
    cn = len(_re.findall(r"[\u4e00-\u9fff]", text))
    if cn >= 2 or len(text) < 5:
        return {"text": text}
    try:
        prompt = f"用户用方言说了一句话，语音识别成了英文/拼音。请直接返回一句通顺的中文（文旅场景，通常是问城市/景点/行程/天气），不要解释。\n识别结果：{text}\n中文："
        fixed = chat([{"role":"user","content":prompt}], temperature=0.1, max_tokens=60)
        fixed = (fixed or "").strip().strip('"').strip("'")
        if fixed:
            return {"text": fixed}
    except Exception as e:
        pass
    return {"text": text}


@app.post("/api/dialect-normalize")
def dialect_normalize(req: dict):
    """方言词汇规范化：把识别出的方言词替换成普通话，让 LLM 能懂。
    body: {text: 识别文本}
    返回: {text: 规范化后文本, map: 替换记录}"""
    import re as _re
    text = (req.get("text") or "").strip()
    if not text:
        return {"text": text, "map": []}

    # 方言词典：按长度降序排，避免短词先替换
    DIALECT_DICT = {
        # 四川/重庆话
        "摆龙门阵": "聊天", "不存在": "没关系", "幺儿": "孩子",
        "啷个": "怎么", "啷凯": "怎么", "咋个": "怎么", "咋凯": "怎么",
        "啥子": "什么", "啥时候": "什么时候",
        "要得": "好的", "要得不": "好吗",
        "巴适": "好", "巴适得板": "非常好",
        "晓得": "知道", "晓不得": "不知道",
        "莫得": "没有", "莫得法": "没办法",
        "搞快": "快点", "搞归一": "搞定",
        "撤了": "走了", "煞搁": "结束",
        "耍朋友": "谈恋爱", "耍": "玩",
        "娃儿": "孩子", "老汉儿": "爸爸",
        "堂客": "妻子", "婆娘": "妻子",
        "慌啥子": "慌什么", "干啥子": "做什么",
        "咋整": "怎么办", "咋个办": "怎么办",
        "归一": "完了", "落教": "懂事",
        "抻抖": "清爽", "称展": "好看",
        "肥凼凼": "胖乎乎", "稀溜耙": "很软",
        # 东北话
        "咋整": "怎么办", "嘎哈": "干什么", "瞅啥": "看什么",
        "唠嗑": "聊天", "忽悠": "骗", "嘚瑟": "炫耀",
        "磕碜": "难看", "埋汰": "脏", "敞亮": "开朗",
        "老铁": "朋友", "干啥呢": "做什么呢",
        # 粤语
        "係": "是", "唔係": "不是", "唔该": "谢谢",
        "嘅": "的", "咁": "这样", "喺": "在",
        "乜": "什么", "嘢": "东西", "睇": "看",
        "食": "吃", "饮": "喝", "行": "走",
        "靓": "漂亮", "叻": "聪明", "锡": "疼",
        # 上海话
        "侬": "你", "阿拉": "我/我们", "啥地方": "哪里",
        "晓得": "知道", "伐": "吗", "额角头": "运气",
        # 陕西/西北
        "咋咧": "怎么了", "啥": "什么", "克里马擦": "快点",
        # 河南话
        "中": "好", "弄啥": "做什么", "咋着": "怎么",
    }

    replaced = []
    # 按词长降序，先替换长词
    for k in sorted(DIALECT_DICT.keys(), key=len, reverse=True):
        if k in text:
            v = DIALECT_DICT[k]
            text = text.replace(k, v)
            replaced.append(f"{k}→{v}")

    return {"text": text, "map": replaced}


@app.get("/api/visuals")
def visuals(ip: str = "", keyword: str = ""):
    """生成目的地相关的真实内容参考链接：小红书/抖音/马蜂窝/实景图。"""
    import urllib.parse
    from app.agent.executor import IP_CITY_NAME
    city = IP_CITY_NAME.get(ip, "成都") if ip else "成都"
    q = keyword or city
    return {
        "city": city,
        "links": [
            {"icon": "📕", "name": "小红书攻略", "url": f"https://www.xiaohongshu.com/search_result?keyword={urllib.parse.quote(q + ' 旅游攻略')}"},
            {"icon": "🎵", "name": "抖音实拍", "url": f"https://www.douyin.com/search/{urllib.parse.quote(q + ' 旅游')}"},
            {"icon": "🐴", "name": "马蜂窝", "url": f"https://www.mafengwo.cn/search/q.php?q={urllib.parse.quote(q)}"},
            {"icon": "📷", "name": "实景照片", "url": f"https://cn.bing.com/images/search?q={urllib.parse.quote(q + ' 景点')}"},
        ]
    }


@app.get("/api/nav-url")
def nav_url(ip: str = "", keyword: str = ""):
    """把城市/地点名转成高德导航 URL，前端一键跳转。
    - ip: 当前接待官 key（后端自己映射到城市名）
    - keyword: 目的地关键词（默认=城市名）
    返回 {url, name, point}"""
    import os, requests, urllib.parse
    from dotenv import load_dotenv
    from app.agent.executor import IP_CITY_NAME
    load_dotenv()
    key = os.getenv("AMAP_API_KEY", "")
    city = IP_CITY_NAME.get(ip, "成都") if ip else "成都"
    dest = keyword or city
    if not key:
        return {"url": f"https://uri.amap.com/search?keyword={urllib.parse.quote(dest)}&callnative=1",
                "name": dest, "point": None}
    try:
        r = requests.get("https://restapi.amap.com/v3/geocode/geo",
                         params={"address": dest, "city": city, "key": key}, timeout=10)
        data = r.json()
        if data.get("geocodes"):
            loc = data["geocodes"][0]["location"]
            url = (f"https://uri.amap.com/navigation?to={urllib.parse.quote(loc + ',' + dest)}"
                   f"&mode=car&policy=1&src=城知&coordinate=gaode&callnative=1")
            return {"url": url, "name": dest, "point": loc}
    except Exception as e:
        pass
    return {"url": f"https://uri.amap.com/search?keyword={urllib.parse.quote(dest)}&callnative=1",
            "name": dest, "point": None}


@app.get("/api/route-nav")
def route_nav(from_city: str = "", to_city: str = ""):
    """跨城路线导航：起点+终点都填好，一键跳转高德。
    返回 {url, from, to}"""
    import os, requests, urllib.parse
    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv("AMAP_API_KEY", "")

    def geocode(name):
        if not key:
            return None
        try:
            r = requests.get("https://restapi.amap.com/v3/geocode/geo",
                             params={"address": name, "key": key}, timeout=8)
            d = r.json()
            if d.get("geocodes"):
                return d["geocodes"][0]["location"]
        except Exception:
            pass
        return None

    from_loc = geocode(from_city)
    to_loc = geocode(to_city)
    if to_loc:
        to_part = f"{to_loc},{urllib.parse.quote(to_city)}"
    else:
        to_part = urllib.parse.quote(to_city)
    url = f"https://uri.amap.com/navigation?to={to_part}&mode=car&policy=1&src=城知&coordinate=gaode&callnative=1"
    if from_loc:
        url += f"&from={from_loc},{urllib.parse.quote(from_city)}"
    return {"url": url, "from": from_city, "to": to_city}


@app.get("/api/traffic")
def api_traffic(city: str = "成都"):
    """城市实时路况摘要：调用高德城市路况接口，返回拥堵路段概览。"""
    import os, requests
    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv("AMAP_API_KEY", "")
    if not key:
        return {"city": city, "status": "no_key", "message": "未配置高德密钥"}
    try:
        # 先地理编码拿城市中心
        g = requests.get("https://restapi.amap.com/v3/geocode/geo",
                         params={"address": city, "city": city, "key": key}, timeout=10)
        gj = g.json()
        loc = gj["geocodes"][0]["location"] if gj.get("geocodes") else "104.06,30.67"
        t = requests.get("https://restapi.amap.com/v3/traffic/status/circle",
                         params={"key": key, "location": loc, "level": "5", "extensions": "all"},
                         timeout=10)
        tj = t.json()
        if tj.get("status") == "1" and tj.get("trafficinfo"):
            info = tj["trafficinfo"]
            desc = info.get("description", "")
            roads = info.get("roads", [])[:6]
            def _lvl(spd):
                try:
                    s = float(spd)
                except (TypeError, ValueError):
                    return "缓行"
                if s >= 30: return "畅通"
                if s >= 15: return "缓行"
                return "拥堵"
            return {
                "city": city,
                "status": "ok",
                "description": desc,
                "congested_roads": [
                    {"name": r.get("name"), "lcode": _lvl(r.get("speed")),
                     "speed": r.get("speed"), "direction": r.get("direction")}
                    for r in roads if r.get("speed")
                ],
            }
        return {"city": city, "status": "fail", "message": tj.get("info", "未知")}
    except Exception as e:
        return {"city": city, "status": "error", "message": str(e)}


class BudgetRequest(BaseModel):
    city: str = "成都"
    people: int = 2
    days: int = 2
    level: str = "舒适"


@app.post("/api/budget")
def api_budget(req: BudgetRequest):
    from app.tools.budget import calc_budget
    return calc_budget(req.city, req.people, req.days, req.level)


class FeedbackRequest(BaseModel):
    session_id: str = "default"
    user_input: str = ""
    assistant_text: str = ""
    rating: int = 1  # 1=👍, -1=👎
    note: str = ""


@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest):
    db.save_feedback(req.session_id, req.user_input, req.assistant_text, req.rating, req.note)
    return {"status": "ok", "message": "感谢反馈" if req.rating > 0 else "已记录问题，我们会改进"}


@app.get("/api/feedback/bad")
def list_bad_feedback():
    """供 eval 回灌：返回所有点踩的用例"""
    return {"cases": db.load_feedback(rating=-1)}


class ResetRequest(BaseModel):
    session_id: str = "default"


@app.post("/api/reset")
def reset_session(req: ResetRequest):
    db.clear_messages(req.session_id)
    db.set_current_ip(req.session_id, "master")
    return {"status": "ok", "message": "对话已重置"}


@app.post("/api/undo")
def undo_session(req: ResetRequest):
    """撤回最近一轮：删除最后一条 user 消息及其后的 assistant 回复。"""
    n, content = db.undo_last_turn(req.session_id)
    return {"status": "ok", "removed": n, "content": content}


# ---------- 托管前端：一个网址 = 整个应用 ----------
import os
import secrets as _secrets
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi import Header, HTTPException, Query

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")

# ---------- 管理后台鉴权 ----------
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "chengzhi2026")
_admin_tokens = set()


def require_admin(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "") if authorization else ""
    if token not in _admin_tokens:
        raise HTTPException(status_code=401, detail="未授权：请先登录管理后台")
    return True


class LoginReq(BaseModel):
    password: str


@app.post("/api/admin/login")
def admin_login(req: LoginReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="密码错误")
    token = _secrets.token_hex(16)
    _admin_tokens.add(token)
    return {"token": token}


@app.get("/api/admin/stats")
def admin_stats(authorization: str = Header(default="")):
    require_admin(authorization)
    return db.admin_stats()


@app.get("/api/admin/sessions")
def admin_sessions(authorization: str = Header(default="")):
    require_admin(authorization)
    return {"sessions": db.admin_sessions()}


@app.get("/api/admin/chat")
def admin_chat(session_id: str, authorization: str = Header(default="")):
    require_admin(authorization)
    return {"messages": db.load_history(session_id)}


@app.get("/api/admin/feedback")
def admin_feedback(rating: int = -1, authorization: str = Header(default="")):
    require_admin(authorization)
    return {"cases": db.admin_recent_feedback(rating)}


@app.get("/api/admin/profiles")
def admin_profiles(authorization: str = Header(default="")):
    require_admin(authorization)
    return {"profiles": db.admin_all_profiles()}


@app.get("/api/admin/backup")
def admin_backup(authorization: str = Header(default="")):
    require_admin(authorization)
    import shutil, time
    tmp = os.path.join(WEB_DIR, "..", "data", f"chat_backup_{int(time.time())}.db")
    shutil.copy2(db.DB_PATH, tmp)
    return FileResponse(tmp, filename=os.path.basename(tmp))


@app.get("/admin")
def admin_page():
    return FileResponse(os.path.join(WEB_DIR, "admin.html"))


@app.get("/")
def home():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


# 必须最后挂载：/api 路由优先于静态目录
app.mount("/", StaticFiles(directory=WEB_DIR), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
