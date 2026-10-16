"""
商业化开关与触发条件
====================
原则：先验证，再商业化。
- 面试结束 或 有效内测用户 >= 10，任一满足才允许开启商业化
- 开关默认关闭，即使触发条件满足也需要管理员手动确认开启
- 所有付费接口在调用前必须过 ``assert_commercialization_on``，
  开关关闭时一律 403，防止提前暴露付费能力。

「有效内测用户」定义：
  1. 完成注册（写入 users 表）
  2. 通过管理员审核（status='approved'）
  3. 实际发生过至少 1 次有效对话（在 metrics 表里有记录）
  三者同时满足才算 1 个有效用户。
"""
from __future__ import annotations
import os
import sqlite3
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "wenlv.db")

# ---------- 触发阈值 ----------
BETA_USER_THRESHOLD = 10  # 有效内测用户满 10 个

# ---------- 配置项（环境变量覆盖，方便沙箱/正式切换）----------
# 面试结束时间：手动写入或通过环境变量指定；None 表示面试尚未结束
INTERVIEW_END_AT: Optional[str] = os.getenv("INTERVIEW_END_AT")  # 例如 "2026-11-01"
# 商业化总开关：默认 False。只有触发条件满足后，管理员调用 enable() 才会变 True。
COMMERCIALIZATION_ENABLED = False


# ============================================================
# 一、有效内测用户统计
# ============================================================
def count_active_beta_users() -> int:
    """
    统计有效内测用户数。
    有效 = 已注册 + 审核通过 + 至少 1 次对话。
    """
    if not os.path.exists(DB_PATH):
        return 0
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            """
            SELECT COUNT(*) FROM users u
            WHERE u.status = 'approved'
              AND EXISTS (
                  SELECT 1 FROM metrics m
                  WHERE m.user_id = u.id AND m.created_at >= date('now', '-30 day')
              )
            """
        )
        return int(cur.fetchone()[0])
    except sqlite3.OperationalError:
        # 表还没建，返回 0
        return 0
    finally:
        conn.close()


# ============================================================
# 二、触发条件校验
# ============================================================
def _interview_finished() -> bool:
    """面试是否已结束。由环境变量 INTERVIEW_END_AT 控制，None 表示未结束。"""
    if not INTERVIEW_END_AT:
        return False
    try:
        return datetime.now() >= datetime.strptime(INTERVIEW_END_AT, "%Y-%m-%d")
    except ValueError:
        return False


def check_trigger() -> dict:
    """
    检查是否满足开启商业化的前置条件。
    返回 dict，前端/管理后台可据此提示管理员。
    """
    beta_users = count_active_beta_users()
    interview_done = _interview_finished()
    triggered = interview_done or (beta_users >= BETA_USER_THRESHOLD)
    return {
        "beta_user_count": beta_users,
        "beta_user_threshold": BETA_USER_THRESHOLD,
        "interview_finished": interview_done,
        "interview_end_at": INTERVIEW_END_AT,
        "triggered": triggered,
        "reason": (
            "面试已结束" if interview_done
            else f"有效内测用户 {beta_users}/{BETA_USER_THRESHOLD}"
        ),
    }


# ============================================================
# 三、商业化开关（默认关闭）
# ============================================================
def is_enabled() -> bool:
    """商业化开关当前是否开启。"""
    return COMMERCIALIZATION_ENABLED


def enable() -> tuple[bool, str]:
    """
    管理员手动开启商业化。必须先满足触发条件。
    返回 (是否成功, 说明)。
    """
    global COMMERCIALIZATION_ENABLED
    status = check_trigger()
    if not status["triggered"]:
        return False, f"触发条件未满足：{status['reason']}"
    COMMERCIALIZATION_ENABLED = True
    return True, f"商业化已开启（依据：{status['reason']}）"


def disable() -> None:
    """紧急关停。"""
    global COMMERCIALIZATION_ENABLED
    COMMERCIALIZATION_ENABLED = False


def assert_commercialization_on() -> None:
    """
    防御校验：所有付费接口在处理请求前调用一次。
    开关关闭时直接抛 RuntimeError，由 main.py 统一转成 403。
    """
    if not COMMERCIALIZATION_ENABLED:
        raise RuntimeError("COMMERCIALIZATION_DISABLED")


# ============================================================
# 四、前端配置下发
# ============================================================
def public_config() -> dict:
    """
    前端启动时拉取的配置。
    开关关闭时，前端必须隐藏所有付费入口（价格、购买按钮、订阅入口）。
    """
    return {
        "commercialization": {
            "enabled": is_enabled(),
            # 开关关闭时，前端必须把这些入口全部隐藏：
            "show_pricing": is_enabled(),
            "show_buy_button": is_enabled(),
            "show_subscribe_entry": is_enabled(),
            # 价格信息只在开关打开后才下发，避免设计稿泄露定价
            "pricing": _pricing() if is_enabled() else None,
        },
    }


def _pricing() -> dict:
    """定价表。沙箱期这里返回测试价。"""
    return {
        "per_chat": float(os.getenv("PRICE_PER_CHAT", "0.5")),   # 元/次
        "monthly": float(os.getenv("PRICE_MONTHLY", "19.9")),    # 元/月
        "beta_free_quota_per_day": 5,                            # 内测用户每天 5 次免费
    }
