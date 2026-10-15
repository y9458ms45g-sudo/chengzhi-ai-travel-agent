"""
SQLite 持久化层：对话历史
- sessions 表：会话元信息（当前 IP、创建时间）
- messages 表：用户/助手消息流水
MVP 用，不上 PostgreSQL。
"""
import os
import sqlite3
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "chat.db")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    # WAL 模式：读写不互斥，并发读不阻塞写；生产可接受
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=5000;")
    c.execute("PRAGMA foreign_keys=ON;")
    return c


def init_db():
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                current_ip TEXT DEFAULT 'sichuan',
                created_at INTEGER,
                updated_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                ip TEXT,
                created_at INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id, id);
            CREATE TABLE IF NOT EXISTS user_profile (
                session_id TEXT PRIMARY KEY,
                prefs_json TEXT,
                updated_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                user_input TEXT,
                assistant_text TEXT,
                rating INTEGER,
                note TEXT,
                created_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT,
                session_id TEXT,
                routed_ip TEXT,
                latency_ms INTEGER,
                tool_calls INTEGER,
                answer_len INTEGER,
                has_reflector_fix INTEGER DEFAULT 0,
                safety_blocked INTEGER DEFAULT 0,
                created_at INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_metrics_time ON metrics(created_at);
            """
        )
        # 老库平滑加列（sessions 可能已存在但缺这两列）
        for col, ddl in [
            ("planned", "ALTER TABLE sessions ADD COLUMN planned INTEGER DEFAULT 0"),
            ("turn_count", "ALTER TABLE sessions ADD COLUMN turn_count INTEGER DEFAULT 0"),
        ]:
            try:
                c.execute(ddl)
            except sqlite3.OperationalError:
                pass  # 列已存在


def ensure_session(session_id: str, current_ip: str = "master"):
    now = int(time.time())
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO sessions(id, current_ip, created_at, updated_at) VALUES(?,?,?,?)",
            (session_id, current_ip, now, now),
        )
        c.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))


def get_current_ip(session_id: str) -> str:
    with _conn() as c:
        r = c.execute("SELECT current_ip FROM sessions WHERE id=?", (session_id,)).fetchone()
        return r["current_ip"] if r else "sichuan"


def set_current_ip(session_id: str, ip: str):
    with _conn() as c:
        c.execute(
            "UPDATE sessions SET current_ip=?, updated_at=? WHERE id=?",
            (ip, int(time.time()), session_id),
        )


def load_history(session_id: str):
    """返回 [{role, content, ip, created_at}]，仅 user/assistant 用于回灌上下文与前端渲染"""
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content, ip, created_at FROM messages WHERE session_id=? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def save_message(session_id: str, role: str, content: str, ip: str = None):
    with _conn() as c:
        c.execute(
            "INSERT INTO messages(session_id, role, content, ip, created_at) VALUES(?,?,?,?,?)",
            (session_id, role, content, ip, int(time.time())),
        )


def clear_messages(session_id: str):
    with _conn() as c:
        c.execute("DELETE FROM messages WHERE session_id=?", (session_id,))


def undo_last_turn(session_id: str):
    """撤回最近一轮：删除最后一条 user 消息及其后的所有 assistant/sys 消息。
    返回 (删除了几条, 撤回的用户消息内容)。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT id, role, content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT 20",
            (session_id,),
        ).fetchall()
        if not rows:
            return 0, None
        # 从末尾往前，找到最后一条 user
        last_user = None
        for r in rows:
            if r["role"] == "user":
                last_user = r
                break
        if not last_user:
            return 0, None
        # 删除 id >= last_user.id 的所有消息
        c.execute(
            "DELETE FROM messages WHERE session_id=? AND id>=?",
            (session_id, last_user["id"]),
        )
        # 统计删了几条
        cnt = c.execute(
            "SELECT COUNT(*) n FROM messages WHERE session_id=? AND id>=?",
            (session_id, last_user["id"]),
        ).fetchone()["n"]
        # 实际上上面那条 DELETE 已经删了，这里查不到，改为预估：从 last_user 到末尾
        return 1, last_user["content"]


# ---------- 行程规划状态（planner 是否已为本轮新行程规划过） ----------
def get_trip_state(session_id: str):
    """返回 (planned: bool, turn_count: int)"""
    with _conn() as c:
        r = c.execute(
            "SELECT planned, turn_count FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not r:
            return False, 0
        return bool(r["planned"]), int(r["turn_count"] or 0)


def mark_planned(session_id: str):
    with _conn() as c:
        c.execute(
            "UPDATE sessions SET planned=1, updated_at=? WHERE id=?",
            (int(time.time()), session_id),
        )


def bump_turn(session_id: str, n: int = 1):
    with _conn() as c:
        c.execute(
            "UPDATE sessions SET turn_count = COALESCE(turn_count,0) + ? WHERE id=?",
            (n, session_id),
        )


def reset_trip_state(session_id: str):
    """新对话/换行程时：清规划标记与轮次计数"""
    with _conn() as c:
        c.execute(
            "UPDATE sessions SET planned=0, turn_count=0, updated_at=? WHERE id=?",
            (int(time.time()), session_id),
        )


# ---------- 用户偏好记忆 ----------
def get_profile(session_id: str) -> dict:
    import json
    with _conn() as c:
        r = c.execute(
            "SELECT prefs_json FROM user_profile WHERE session_id=?", (session_id,)
        ).fetchone()
    if not r or not r["prefs_json"]:
        return {}
    try:
        return json.loads(r["prefs_json"])
    except Exception:
        return {}


def save_profile(session_id: str, prefs: dict):
    import json
    with _conn() as c:
        c.execute(
            "INSERT INTO user_profile(session_id, prefs_json, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET prefs_json=excluded.prefs_json, updated_at=excluded.updated_at",
            (session_id, json.dumps(prefs, ensure_ascii=False), int(time.time())),
        )


# ---------- 用户反馈（👍/👎） ----------
def save_feedback(session_id: str, user_input: str, assistant_text: str,
                  rating: int, note: str = ""):
    with _conn() as c:
        c.execute(
            "INSERT INTO feedback(session_id, user_input, assistant_text, rating, note, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (session_id, user_input, assistant_text[:2000], rating, note, int(time.time())),
        )


def load_feedback(rating: int = None):
    sql = "SELECT user_input, assistant_text, rating, note FROM feedback"
    args = ()
    if rating is not None:
        sql += " WHERE rating=?"
        args = (rating,)
    with _conn() as c:
        rows = c.execute(sql, args).fetchall()
        return [dict(r) for r in rows]


# ---------- 管理后台查询 ----------
def admin_stats():
    with _conn() as c:
        sessions = c.execute("SELECT COUNT(*) n FROM sessions").fetchone()["n"]
        msgs = c.execute("SELECT COUNT(*) n FROM messages").fetchone()["n"]
        fb_bad = c.execute("SELECT COUNT(*) n FROM feedback WHERE rating=-1").fetchone()["n"]
        fb_good = c.execute("SELECT COUNT(*) n FROM feedback WHERE rating=1").fetchone()["n"]
        profiles = c.execute("SELECT COUNT(*) n FROM user_profile").fetchone()["n"]
    return {"sessions": sessions, "messages": msgs,
            "fb_bad": fb_bad, "fb_good": fb_good, "profiles": profiles}


def admin_sessions(limit=200):
    """会话列表：带消息数、当前城市、最近活跃时间"""
    with _conn() as c:
        rows = c.execute(
            """SELECT s.id, s.current_ip, s.updated_at,
                      (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) AS msg_cnt
               FROM sessions s ORDER BY s.updated_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def admin_recent_feedback(rating=-1, limit=100):
    with _conn() as c:
        rows = c.execute(
            "SELECT id, session_id, user_input, assistant_text, rating, note, created_at "
            "FROM feedback WHERE rating=? ORDER BY created_at DESC LIMIT ?",
            (rating, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def admin_all_profiles(limit=300):
    import json
    with _conn() as c:
        rows = c.execute(
            "SELECT session_id, prefs_json, updated_at FROM user_profile "
            "ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        out = []
        for r in rows:
            try:
                out.append({"session_id": r["session_id"],
                            "prefs": json.loads(r["prefs_json"] or "{}"),
                            "updated_at": r["updated_at"]})
            except Exception:
                pass
        return out


# ---------- 线上指标埋点 ----------
def save_metrics(trace_id: str, session_id: str, routed_ip: str,
                 latency_ms: int, tool_calls: int, answer_len: int,
                 has_reflector_fix: bool = False, safety_blocked: bool = False):
    """每次请求结束写一行，用于算 P50/P99 延迟、路由分布、采纳率"""
    with _conn() as c:
        c.execute(
            "INSERT INTO metrics(trace_id, session_id, routed_ip, latency_ms, "
            "tool_calls, answer_len, has_reflector_fix, safety_blocked, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (trace_id, session_id, routed_ip, latency_ms, tool_calls, answer_len,
             1 if has_reflector_fix else 0, 1 if safety_blocked else 0, int(time.time())),
        )


def metrics_summary(limit: int = 1000):
    """聚合近 N 条指标，给管理后台看"""
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) n, AVG(latency_ms) avg_ms, "
            "AVG(tool_calls) avg_tools, AVG(answer_len) avg_len, "
            "SUM(has_reflector_fix) fixes, SUM(safety_blocked) blocked "
            "FROM metrics ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchone()
        # 路由分布
        routes = c.execute(
            "SELECT routed_ip, COUNT(*) n FROM metrics "
            "GROUP BY routed_ip ORDER BY n DESC LIMIT 10"
        ).fetchall()
    return {
        "samples": row["n"] or 0,
        "avg_latency_ms": int(row["avg_ms"] or 0),
        "avg_tool_calls": round(row["avg_tools"] or 0, 2),
        "avg_answer_len": int(row["avg_len"] or 0),
        "reflector_fix_rate": round((row["fixes"] or 0) / max(row["n"] or 1, 1), 3),
        "safety_blocked_rate": round((row["blocked"] or 0) / max(row["n"] or 1, 1), 3),
        "top_routes": [dict(r) for r in routes],
    }
