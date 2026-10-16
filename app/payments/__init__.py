"""
支付模块预埋（沙箱）
====================
只定义接口和表结构，不真接微信/支付宝。
达到触发条件后，把 PROVIDER 从 "mock" 切到 "wechat" 或 "alipay" 即可。

环境变量：
    PAYMENT_PROVIDER = mock | wechat | alipay
    PAYMENT_MOCK_CALLBACK_URL = http://localhost:8000/api/pay/mock/callback
    PAYMENT_WECHAT_MCH_ID / PAYMENT_WECHAT_API_KEY / PAYMENT_WECHAT_NOTIFY_URL
    PAYMENT_ALIPAY_APP_ID / PAYMENT_ALIPAY_PRIVATE_KEY / PAYMENT_ALIPAY_NOTIFY_URL
"""
from __future__ import annotations
import os
import sqlite3
import time
import uuid
from typing import Optional

from app.commercialization import assert_commercialization_on, DB_PATH


PROVIDER = os.getenv("PAYMENT_PROVIDER", "mock")  # 默认沙箱 mock


# ============================================================
# 一、表结构（幂等建表，首次启动自动建）
# ============================================================
def init_tables() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE,
                status TEXT DEFAULT 'pending',   -- pending/approved/rejected
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                item TEXT NOT NULL,               -- 'per_chat_10' / 'monthly'
                amount_cents INTEGER NOT NULL,    -- 单位：分
                currency TEXT DEFAULT 'CNY',
                status TEXT DEFAULT 'created',    -- created/paid/closed/refunded
                provider TEXT NOT NULL,
                pay_url TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                paid_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
            """
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 二、下单（防御：商业化开关关闭时 403）
# ============================================================
def create_order(user_id: str, item: str) -> dict:
    assert_commercialization_on()  # 🔒 关键防御
    amount = _price_of(item)
    order_id = f"O{uuid.uuid4().hex[:16]}"
    pay_url = _build_pay_url(order_id, amount)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO orders(order_id,user_id,item,amount_cents,provider,pay_url)"
            " VALUES(?,?,?,?,?,?)",
            (order_id, user_id, item, amount, PROVIDER, pay_url),
        )
        conn.commit()
    finally:
        conn.close()

    return {"order_id": order_id, "amount_cents": amount, "pay_url": pay_url}


def _price_of(item: str) -> int:
    """元 → 分。mock 沙箱里直接给固定价。"""
    table = {"per_chat_10": 500, "monthly": 1990}  # 5元/10次，19.9元/月
    return table.get(item, 0)


def _build_pay_url(order_id: str, amount_cents: int) -> str:
    if PROVIDER == "mock":
        # 沙箱：返回一个本地模拟支付页 URL
        return f"/pay/mock/{order_id}?amount={amount_cents}"
    # 真接微信/支付宝时，这里调 SDK 生成 prepay_id
    return f"https://pay.{PROVIDER}.com/{order_id}"


# ============================================================
# 三、回调处理（签名校验留给真渠道）
# ============================================================
def handle_callback(provider: str, payload: dict) -> dict:
    """
    支付渠道异步回调。
    mock 沙箱：直接按 payload.order_id 标记 paid。
    真渠道：先验签，再更新订单。
    """
    order_id = payload.get("order_id")
    if not order_id:
        return {"ok": False, "err": "missing order_id"}

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE orders SET status='paid', paid_at=datetime('now')"
            " WHERE order_id=?",
            (order_id,),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "order_id": order_id, "status": "paid"}


# ============================================================
# 四、订单查询
# ============================================================
def query_order(order_id: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT order_id,user_id,item,amount_cents,status,created_at,paid_at"
            " FROM orders WHERE order_id=?",
            (order_id,),
        ).fetchone()
        if not row:
            return None
        return dict(zip(
            ["order_id", "user_id", "item", "amount_cents", "status", "created_at", "paid_at"],
            row,
        ))
    finally:
        conn.close()
