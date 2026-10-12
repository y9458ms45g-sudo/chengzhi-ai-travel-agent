"""
城知 Agent 回归评测脚本
用法（在项目根目录）：
    python -m tests.run_eval           # 跑全部（detect + agent，agent 会真实调 LLM/工具）
    python -m tests.run_eval --fast     # 只跑 detect（确定性、秒级、免费）
    python -m tests.run_eval --only a01,a02   # 只跑指定 id
退出码：全部通过=0，否则=1
"""
import argparse
import json
import os
import sys
import time

# 保证从项目根导入
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CASES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_cases.json")


def _load_cases():
    with open(CASES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _run_detect(cases, only):
    from app.agent.executor import detect_city
    passed, failed, rows = 0, 0, []
    for c in cases:
        if only and c["id"] not in only:
            continue
        got = detect_city(c["input"])
        ok = got == c["expect_ip"]
        rows.append((c["id"], ok, c["input"], f"expect={c['expect_ip']} got={got}", c.get("note", "")))
        if ok:
            passed += 1
        else:
            failed += 1
    return rows, passed, failed


def _run_agent(cases, only):
    from app.agent.executor import run_agent, Session
    passed, failed, rows = 0, 0, []
    for c in cases:
        if only and c["id"] not in only:
            continue
        sess = Session()
        t0 = time.time()
        try:
            out = run_agent(c["input"], sess, max_tool_calls=c.get("max_tool_calls", 4))
        except Exception as e:
            out = f"[EXC] {e}"
        dt = time.time() - t0

        problems = []
        must_contain = c.get("must_contain", [])
        any_terms = c.get("expect", []) if c.get("expect_any") else []
        for term in must_contain:
            if term not in out:
                problems.append(f"缺'{term}'")
        if any_terms and not any(t in out for t in any_terms):
            problems.append(f"命中不了任一: {any_terms}")
        for term in c.get("must_not_contain", []):
            if term in out:
                problems.append(f"不应出现'{term}'")

        ok = not problems
        preview = out.replace("\n", " ")[:90]
        rows.append((c["id"], ok, c["input"],
                     "PASS" if ok else "MISS:" + ";".join(problems),
                     f"{dt:.1f}s | {preview}", c.get("note", "")))
        if ok:
            passed += 1
        else:
            failed += 1
    return rows, passed, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="只跑 detect 用例")
    ap.add_argument("--only", type=str, default="", help="逗号分隔的用例 id")
    args = ap.parse_args()
    only = set(x.strip() for x in args.only.split(",") if x.strip())

    data = _load_cases()
    total_pass, total_fail = 0, 0

    print("=" * 78)
    print("[1/2] 城市识别 detect（确定性）")
    print("-" * 78)
    rows, p, f = _run_detect(data.get("detect", []), only)
    total_pass += p
    total_fail += f
    for cid, ok, inp, detail, note in rows:
        mark = "✅" if ok else "❌"
        line = f"{mark} {cid:5} | {inp[:24]:<24} | {detail}"
        if note and not ok:
            line += f"  ({note})"
        print(line)
    print(f"-- detect: {p} pass / {f} fail")

    if not args.fast:
        print()
        print("=" * 78)
        print("[2/2] 端到端 agent（真实调用 LLM/工具，较慢）")
        print("-" * 78)
        rows, p, f = _run_agent(data.get("agent", []), only)
        total_pass += p
        total_fail += f
        for cid, ok, inp, detail, preview, note in rows:
            mark = "✅" if ok else "❌"
            print(f"{mark} {cid:5} | {inp[:24]:<24} | {detail}")
            print(f"       ↳ {preview}")
        print(f"-- agent: {p} pass / {f} fail")

        # 回灌用户点踩用例（跑通即算过，不做硬断言）
        try:
            from app import db
            from app.agent.executor import run_agent, Session
            bad = db.load_feedback(rating=-1)
            if bad:
                print()
                print(f"[3/3] 回灌 👎 反馈用例 {len(bad)} 条（跑通即过）")
                bp = bf = 0
                for i, fb in enumerate(bad):
                    sess = Session()
                    try:
                        out = run_agent(fb["user_input"], sess, max_tool_calls=3)
                        ok = bool(out and len(out) > 20)
                    except Exception as e:
                        out = f"[EXC] {e}"; ok = False
                    bp += int(ok); bf += int(not ok)
                    print(f"{'✅' if ok else '❌'} fb{i+1:2} | {fb['user_input'][:30]}")
                total_pass += bp; total_fail += bf
                print(f"-- feedback: {bp} pass / {bf} fail")
        except Exception as e:
            print(f"(反馈回灌跳过: {e})")
    else:
        print("\n(--fast 模式，跳过 agent 用例)")

    total = total_pass + total_fail
    acc = (total_pass / total * 100) if total else 0.0
    print("=" * 78)
    print(f"总计：{total_pass} 过 / {total_fail} 败，准确率 {acc:.1f}%  (共 {total} 条)")
    print("=" * 78)
    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
