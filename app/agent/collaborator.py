"""
Collaborator：多 Agent 并行协作调度器
- 用户提到几个城市，就同时调动几个城市接待官
- 按用户提到城市的顺序编排行程（先提到 = 第一站）
- 所有子 Agent 并行收集本城信息，总控官最后整合输出
- 不做"转接"，而是"合奏"
"""
import json
import logging
import concurrent.futures

from app.llm import chat, chat_with_tools, chat_stream
from app.tools import execute_tool, OPENAI_TOOLS
from app.agent.executor import (
    detect_all_cities,
    IP_NAME_MAP, IP_CITY_NAME,
)

logger = logging.getLogger("agent.collaborator")


# ── 触发判断 ──────────────────────────────────────────────

def should_collaborate(user_input: str, current_ip: str) -> dict | None:
    """
    用户提到几个不同城市，就触发协作，全部拉进来。
    按城市在文本中出现的先后顺序排列（先提到 = 第一站）。
    返回 None 表示只提到 1 个城市，走单 Agent 路径。
    """
    raw_hits = detect_all_cities(user_input)  # [(kw, ip), ...] 按位置排序

    # 按出现顺序去重：同一个 ip 只保留第一次出现
    seen_ips = []
    for _kw, ip in raw_hits:
        if ip not in seen_ips:
            seen_ips.append(ip)

    if len(seen_ips) < 2:
        return None

    # 如果用户当前已经在某个城市接待，把那个城市排到最前面（出发点）
    if current_ip and current_ip != "master" and current_ip in seen_ips:
        seen_ips.remove(current_ip)
        seen_ips.insert(0, current_ip)

    # 最多同时调 3 个城市 Agent（太多会拖慢、token 爆炸）
    seen_ips = seen_ips[:3]

    total = len(seen_ips)
    agents = []
    for idx, ip in enumerate(seen_ips, start=1):
        city_name = IP_CITY_NAME.get(ip, ip)
        name = IP_NAME_MAP.get(ip, city_name)
        if idx == 1:
            role = "first"      # 第一个提到的城市
        elif idx == total:
            role = "last"       # 最后一个提到的城市（重点目的地）
        else:
            role = "middle"     # 中间途经站
        agents.append((ip, name, city_name, role, idx))

    first_city = agents[0][2]
    last_city = agents[-1][2]

    logger.info(json.dumps({
        "ev": "collab_trigger",
        "cities": [a[2] for a in agents],
        "roles": [a[3] for a in agents],
    }, ensure_ascii=False))

    return {
        "agents": agents,           # [(ip, name, city_name, role, idx), ...]
        "first_city": first_city,
        "last_city": last_city,
        "total_stops": total,
    }


# ── 单个城市子 Agent ──────────────────────────────────────

_SUBAGENT_SYSTEM = """你是{ip_name}，{city_name}的文旅接待官。
用户正在规划一次多城旅行，一共 {total} 站，{city_name}是其中第 {idx} 站。

【你负责收集{city_name}的信息】
- 当地天气
- 必玩景点（2-3个，本地人常去的优先）
- 必吃美食（2-3个，老城区/社区店优先）
- 实用贴士（交通/穿衣/避坑）

{role_extra}

【语气要求】
说人话，不用网络用语（禁止"出片""拿捏""绝绝子"等），不推销，回答完就结束。

【工具要求】
1. 必须调工具拿实时信息，不要凭记忆编
2. 最多调 4 次工具
3. 不要寒暄，收集完直接输出简报

【输出格式】
直接输出 200-400 字的城市简报，不要加标题。"""


def run_city_subagent(ip_key: str, name: str, city_name: str,
                      role: str, idx: int, total: int,
                      all_city_names: list[str],
                      user_input: str) -> dict:
    """运行单个城市子 Agent，返回简报。"""

    if role == "first":
        role_extra = (
            f"这是用户行程的第一站（起点）。除了本城信息，也查一下"
            f"从{city_name}到下一站{all_city_names[1]}的交通方式（高铁/自驾/飞机）。"
        )
    elif role == "last":
        role_extra = (
            f"这是整趟行程的最后一站（重点目的地），多花笔墨写景点和美食。"
            f"如果前面还有其他城市，不用管，专注本城。"
        )
    else:
        next_city = all_city_names[idx] if idx < total else ""
        role_extra = (
            f"这是中间途经站。除了本城精华，如果到下一站{next_city}方便，"
            f"顺带提一句交通衔接。"
        )

    system_prompt = _SUBAGENT_SYSTEM.format(
        ip_name=name, city_name=city_name,
        total=total, idx=idx, role_extra=role_extra,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"用户原始需求：{user_input}\n请收集{city_name}的旅游信息。"},
    ]

    tools_used = []
    for _ in range(4):
        try:
            msg = chat_with_tools(messages, OPENAI_TOOLS, temperature=0.2)
        except Exception as e:
            logger.warning(f"[subagent {name}] LLM failed: {e}")
            break

        if not msg.tool_calls:
            brief = (msg.content or "").strip()
            return {
                "ip": ip_key, "name": name, "city": city_name,
                "role": role, "idx": idx,
                "brief": brief, "tools_used": tools_used,
            }

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}
            tools_used.append(tc.function.name)
            result = execute_tool(tc.function.name, args)
            messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": str(result)[:800],
            })

    messages.append({
        "role": "user",
        "content": "信息够了，直接输出城市简报，不要调工具。",
    })
    try:
        brief = chat(messages, temperature=0.3, max_tokens=600)
    except Exception as e:
        brief = f"[{name}简报生成失败: {e}]"

    return {
        "ip": ip_key, "name": name, "city": city_name,
        "role": role, "idx": idx,
        "brief": brief, "tools_used": tools_used,
    }


# ── 总控官整合 ─────────────────────────────────────────────

_MASTER_MERGE_SYSTEM = """你是「小知·总控官」，城知文旅平台的总协调人。

你已经同时调动了以下城市接待官并行收集信息：{city_list_text}
下面是他们各自返回的城市简报。

【整合要求】
1. 语气像可靠的朋友给建议，说人话，不用网络用语（禁止"出片""拿捏""绝绝子"等）
2. 开头自然地说一句："我已经帮你联系了{city_list_short}的接待官，把这{total_stops}站的情况都了解了一下～"
3. 按用户提到城市的顺序（第1站→第2站→…）组织回答，把各城信息串成一条完整路线
4. 每站给出：玩什么、吃什么、天气/穿衣提醒、站间怎么去
5. 如果用户问了几天几晚，按天安排行程，合理分配每站停留时间
6. 给预算粗算和雨天备选
7. 不要说"XX接待官说"这种元话术，直接把信息揉成你自己的话
8. 不要在结尾推销"要不要我帮你XX"，回答完就结束
9. 不确定的信息标注"建议出发前再核实"
10. 如果用户说过不要网红/想小众，避开洪崖洞、锦里、宽窄巷子这类游客扎堆的地方，优先推荐本地人去的"""


def collaborative_reply(user_input: str, plan: dict):
    """多 Agent 协作主入口（生成器）。"""
    agents = plan["agents"]            # [(ip, name, city, role, idx), ...]
    total = plan["total_stops"]
    all_city_names = [a[2] for a in agents]

    # 给前端展示用的名单
    agent_labels = "、".join(f"{a[2]}·{a[1]}" for a in agents)
    city_list_text = "、".join(f"第{a[4]}站{a[2]}（{a[1]}）" for a in agents)
    city_list_short = "、".join(all_city_names)

    # 1) 通知前端
    yield {
        "type": "collab_start",
        "text": f"🔀 检测到{total}个城市，正在同时联系：{agent_labels}…",
        "agents": [
            {"ip": ip, "name": name, "city": city, "role": role, "idx": idx}
            for ip, name, city, role, idx in agents
        ],
    }

    # 2) 并行派出所有子 Agent
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(3, len(agents))) as ex:
        future_map = {
            ex.submit(run_city_subagent, ip, name, city, role, idx,
                      total, all_city_names, user_input): (ip, name)
            for ip, name, city, role, idx in agents
        }
        for fut in concurrent.futures.as_completed(future_map):
            ip, name = future_map[fut]
            try:
                result = fut.result()
                results[ip] = result
                yield {
                    "type": "collab_agent_done",
                    "ip": ip, "name": name,
                    "city": result["city"], "idx": result["idx"],
                    "preview": result["brief"][:100],
                }
                logger.info(f"[collab] {name} done, tools={result['tools_used']}")
            except Exception as e:
                logger.exception(f"[collab] {name} failed: {e}")
                results[ip] = {
                    "ip": ip, "name": name, "city": name,
                    "role": "", "idx": 0,
                    "brief": f"[{name}暂时没连上]",
                    "tools_used": [],
                }

    # 3) 按站序组装简报
    briefs_parts = []
    for ip, name, city, role, idx in sorted(agents, key=lambda a: a[4]):
        r = results.get(ip, {})
        briefs_parts.append(f"【第{idx}站：{city}（{name}）】\n{r.get('brief', '暂无')}")

    merge_messages = [
        {"role": "system", "content": _MASTER_MERGE_SYSTEM.format(
            city_list_text=city_list_text,
            city_list_short=city_list_short,
            total_stops=total,
        )},
        {"role": "user", "content":
            f"用户原始问题：{user_input}\n\n"
            + "\n\n".join(briefs_parts)
            + "\n\n请按站序整合，输出完整的多城旅行攻略。"
        },
    ]

    # 4) 总控官流式输出
    full = ""
    try:
        for chunk in chat_stream(merge_messages, temperature=0.4):
            full += chunk
            yield {"type": "token", "text": chunk}
    except Exception as e:
        logger.exception(f"[collab] merge failed: {e}")
        yield {"type": "token", "text": "抱歉，协作整合暂时出了点问题，让我换个方式帮你～\n"}

    yield {"type": "collab_done", "text": full, "results": results}
