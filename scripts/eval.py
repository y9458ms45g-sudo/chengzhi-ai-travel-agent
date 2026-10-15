"""
城知 Agent 评测脚本（golden set）
================================
跑法：
    python -m scripts.eval

分两类：
  A. 纯函数单测（不调 LLM，不花钱，秒出结果）
     - 城市识别 detect_city / detect_all_cities
     - 出发地/目的地消歧 pick_destination
     - 重置判断 should_reset
  B. 端到端冒烟（调真实 LLM，默认 skip；加 --e2e 才跑）
     - 跑 3 条典型 query，检查是否路由到正确城市、是否调了工具

产物：
  控制台输出通过率；data/eval_report.md 落盘
"""
from __future__ import annotations
import os, sys, time, json, re

# 让脚本能从项目根 import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.executor import (
    detect_city, detect_all_cities, pick_destination,
    should_reset, _extract_days, _is_meaningless_input,
    CITY_DETECT_RULES, IP_CITY_NAME,
)

# ---------- A. 纯函数 golden set ----------
# 每条: (描述, 用户输入, 期望 ip_key 或 None)
CITY_CASES = [
    ("直辖市直选", "推荐重庆好吃的", "chongqing"),
    ("成都地标", "熊猫基地值得去吗", "chengdu"),
    ("乐山美食", "跷脚牛肉哪家正宗", "leshan"),
    ("沈阳故宫优先于故宫", "沈阳故宫门票多少", "shenyang"),
    ("北京故宫", "故宫怎么预约", "beijing"),
    ("西安兵马俑", "兵马俑讲解", "xian"),
    ("上海外滩", "外滩夜景几点最好", "shanghai"),
    ("杭州西湖", "西湖游船", "hangzhou"),
    ("张家界", "天门山玻璃栈道", "zhangjiajie"),
    ("三亚", "亚龙湾住宿", "sanya"),
    ("无城市", "你好你是谁", None),
    ("广州早茶", "广州早茶推荐", "guangzhou"),
    ("桂林山水", "漓江竹筏", "guilin"),
    ("厦门鼓浪屿", "鼓浪屿船票", "xiamen"),
    ("哈尔滨冰雪", "冰雪大世界什么时候开", "harbin"),
    ("敦煌莫高窟", "莫高窟预约", "dunhuang"),
]

# (输入, 当前 ip, 期望目的地 ip, 期望出发地 ip)
ROUTE_CASES = [
    # 用户在 master，明确说去成都 → 切成都
    ("我想去成都玩两天", "master", "chengdu", None),
    # 用户在 master，说从重庆去成都 → 目的地成都，出发地重庆
    ("从重庆出发去成都", "master", "chengdu", "chongqing"),
    # 用户在成都接待，问重庆天气 → 不切（不是明确"去"）
    ("重庆天气怎么样", "chengdu", None, None),
    # 用户在成都接待，明确说去西安 → 切西安
    ("那我下周去西安", "chengdu", "xian", None),
    # 用户在 master，说"我在重庆" → master 阶段应路由到重庆接待官（这是用户当前位置=默认目的地）
    ("我现在在重庆", "master", "chongqing", "chongqing"),
]

RESET_CASES = [
    ("重新规划一下", True),
    ("换一个方案", True),
    ("明天天气", False),
    ("加一天", False),  # 天数变化单独测
]


def run_unit_tests() -> list[dict]:
    results = []

    # 城市识别
    for desc, text, expect in CITY_CASES:
        got = detect_city(text)
        ok = got == expect
        results.append({"suite": "city_detect", "case": desc,
                        "input": text, "expect": expect, "got": got, "pass": ok})

    # 路由
    for text, cur, exp_dest, exp_dep in ROUTE_CASES:
        cands = detect_all_cities(text)
        got_dest, got_dep = pick_destination(text, cands, cur)
        ok = (got_dest == exp_dest) and (got_dep == exp_dep)
        results.append({"suite": "route", "case": f"{text} (cur={cur})",
                        "input": text, "expect": f"dest={exp_dest}, dep={exp_dep}",
                        "got": f"dest={got_dest}, dep={got_dep}", "pass": ok})

    # reset
    for text, expect in RESET_CASES:
        got = should_reset(text, "", 0, 0)
        results.append({"suite": "reset", "case": text,
                        "input": text, "expect": expect, "got": got, "pass": got == expect})

    # 天数抽取
    for text, expect in [("3天2晚", 3), ("5天怎么安排", 5), ("周末", None)]:
        got = _extract_days(text)
        results.append({"suite": "extract_days", "case": text,
                        "input": text, "expect": expect, "got": got, "pass": got == expect})

    # 无意义输入
    for text, expect in [("嗯", True), ("好的", True), ("aaaaaaaa", True),
                         ("推荐成都美食", False)]:
        got = _is_meaningless_input(text)
        results.append({"suite": "meaningless", "case": repr(text),
                        "input": text, "expect": expect, "got": got, "pass": got == expect})
    return results


# ---------- B. 端到端冒烟（可选） ----------
def run_e2e() -> list[dict]:
    from app.agent.executor import Session, run_agent_stream
    cases = [
        ("重庆两天不要网红打卡点", "chongqing"),
        ("成都有什么本地美食", "chengdu"),
    ]
    out = []
    for text, expect_ip in cases:
        s = Session()
        final = ""
        routed_to = None
        t0 = time.perf_counter()
        try:
            for ev in run_agent_stream(text, s, session_id=None):
                if ev.get("type") == "transfer":
                    routed_to = ev.get("to")
                if ev.get("type") == "token":
                    final += ev.get("text", "")
            ok = (routed_to == expect_ip) and len(final) > 50
            out.append({"suite": "e2e", "case": text, "expect": expect_ip,
                        "got": f"routed={routed_to}, len={len(final)}",
                        "pass": ok, "latency_ms": int((time.perf_counter()-t0)*1000)})
        except Exception as e:
            out.append({"suite": "e2e", "case": text, "expect": expect_ip,
                        "got": f"ERR: {e}", "pass": False})
    return out


# ---------- C. LLM-as-judge（可选，--judge 开启） ----------
JUDGE_PROMPT = """你是严格的文旅攻略审核员。给你一个用户问题和 AI 的回答，按 4 个维度打分（1-5）：
1. 相关性：回答是否直接解决用户问题
2. 具体性：是否给了具体店名/价格/时间，而不是空话
3. 安全：有没有编造明显错误的信息（如把乐山大佛说成成都的）
4. 风格：有没有网络热词/结尾推销反问

只输出 JSON：{"relevance":1-5, "specificity":1-5, "factual":1-5, "style":1-5, "comment":"一句话"}
"""

def run_judge() -> list[dict]:
    """对 3 条典型回答让 LLM 打分，算平均分。"""
    from app.llm import chat
    samples = [
        ("重庆两天不要网红打卡点",
         "第一天：上午湖广会馆，下午山城步道，晚上南滨路看夜景。第二天：偏岩古镇半日，下午北碚温塘峡。人均约590元。"),
        ("成都有什么本地美食",
         "严太婆锅盔（文殊院街19号，人均15）、明婷饭店（曹家巷，脑花豆腐）、洞子口张老二凉粉。"),
        ("西安三天预算",
         "兵马俑+华清宫一天，城墙+回民街一天，陕西历史博物馆+大雁塔一天。门票约350/人，住宿300/晚，总预算约1800/人。"),
    ]
    out = []
    for q, a in samples:
        try:
            result = chat(
                [{"role": "system", "content": JUDGE_PROMPT},
                 {"role": "user", "content": f"用户问：{q}\nAI答：{a}"}],
                temperature=0.0, max_tokens=200, response_format="json",
            )
            score = json.loads(result)
            avg = (score.get("relevance",0)+score.get("specificity",0)
                   +score.get("factual",0)+score.get("style",0))/4
            out.append({"suite": "llm_judge", "case": q[:20],
                        "got": f"avg={avg:.1f}, {score.get('comment','')}",
                        "pass": avg >= 3.5, "score": avg})
        except Exception as e:
            out.append({"suite": "llm_judge", "case": q[:20],
                        "got": f"ERR: {e}", "pass": False, "score": 0})
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--e2e", action="store_true", help="跑端到端（花钱）")
    ap.add_argument("--judge", action="store_true", help="跑 LLM-as-judge 打分（花钱）")
    args = ap.parse_args()

    results = run_unit_tests()
    if args.e2e:
        results += run_e2e()
    if args.judge:
        results += run_judge()

    # 汇总
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    print(f"\n==== 评测结果：{passed}/{total} 通过 ====\n")
    by_suite = {}
    for r in results:
        by_suite.setdefault(r["suite"], [0, 0])
        by_suite[r["suite"]][1] += 1
        if r["pass"]:
            by_suite[r["suite"]][0] += 1
    for suite, (p, t) in by_suite.items():
        print(f"  {suite:15s} {p}/{t}")

    # 失败明细
    fails = [r for r in results if not r["pass"]]
    if fails:
        print("\n---- 失败用例 ----")
        for r in fails:
            print(f"[{r['suite']}] {r['case']}")
            print(f"   input:  {r['input']}")
            print(f"   expect: {r['expect']}")
            print(f"   got:    {r['got']}")

    # 落盘报告
    report = ["# 城知评测报告", "",
              f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
              f"- 通过: {passed}/{total} ({passed*100//max(total,1)}%)", ""]
    for suite, (p, t) in by_suite.items():
        report.append(f"## {suite}: {p}/{t}")
    report.append("")
    if fails:
        report.append("## 失败明细")
        for r in fails:
            report.append(f"- **{r['case']}** | expect={r['expect']} | got={r['got']}")
    os.makedirs("data", exist_ok=True)
    with open("data/eval_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print("\n报告已写入 data/eval_report.md")


if __name__ == "__main__":
    main()
