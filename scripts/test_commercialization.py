"""
商业化开关 + 支付预埋 自测
==========================
跑：python -m scripts.test_commercialization
覆盖 6 个场景：
  1. 触发条件未满足时，开关默认关闭
  2. 开关关闭时，付费接口直接 403
  3. 触发条件满足前，enable() 被拒绝
  4. 触发条件满足后，enable() 成功
  5. enable 后 create_order/handle_callback 闭环
  6. disable() 后再次 403
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import commercialization as cz
from app import payments


def _reset():
    cz.COMMERCIALIZATION_ENABLED = False
    cz.INTERVIEW_END_AT = None


def run():
    payments.init_tables()
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  ✅ {name}")
        else:
            failed += 1
            print(f"  ❌ {name}")

    # 场景 1：默认关闭
    _reset()
    check("1. 默认开关关闭", not cz.is_enabled())

    # 场景 2：开关关闭，create_order 抛错
    try:
        payments.create_order("u1", "monthly")
        check("2. 关闭时 create_order 被拦截", False)
    except RuntimeError as e:
        check("2. 关闭时 create_order 被拦截", "COMMERCIALIZATION_DISABLED" in str(e))

    # 场景 3：触发条件未满足，enable() 被拒
    ok, msg = cz.enable()
    check(f"3. 未满足条件 enable() 被拒 (msg={msg})", not ok)

    # 场景 4：模拟面试结束，enable() 成功
    cz.INTERVIEW_END_AT = "2020-01-01"  # 过去时间 = 面试已结束
    status = cz.check_trigger()
    check(f"4a. 触发条件满足 ({status['reason']})", status["triggered"])
    ok, msg = cz.enable()
    check(f"4b. enable() 成功 (msg={msg})", ok and cz.is_enabled())

    # 场景 5：下单 + 回调闭环
    order = payments.create_order("u_test", "monthly")
    check("5a. 下单成功", order["order_id"].startswith("O"))
    cb = payments.handle_callback("mock", {"order_id": order["order_id"]})
    check("5b. 回调标记 paid", cb["ok"])
    q = payments.query_order(order["order_id"])
    check("5c. 订单状态=paid", q and q["status"] == "paid")

    # 场景 6：disable 后再次 403
    cz.disable()
    try:
        payments.create_order("u2", "monthly")
        check("6. disable 后再次拦截", False)
    except RuntimeError:
        check("6. disable 后再次拦截", True)

    # 前端配置：关闭时不暴露 pricing
    cfg = cz.public_config()
    check("7. 关闭时前端拿不到 pricing", cfg["commercialization"]["pricing"] is None)

    print(f"\n=== 通过 {passed} / {passed+failed} ===")
    return failed == 0


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
