"""
SQLite → Postgres 数据迁移脚本
================================
跑法（先在 Postgres 里建好库和表，表结构见 app/db.py init_db）：
    DATABASE_URL=postgresql://user:pass@host:5432/chengzhi \
    python -m scripts.migrate_to_postgres
"""
import os, sys, sqlite3, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import DB_PATH

TABLES = ["sessions", "messages", "user_profile", "feedback", "metrics"]


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("请先设置 DATABASE_URL 环境变量")
        sys.exit(1)

    import psycopg
    src = sqlite3.connect(DB_PATH)
    src.row_factory = sqlite3.Row
    dst = psycopg.connect(url, autocommit=False)

    for table in TABLES:
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        cols = rows[0].keys() if rows else []
        if not rows:
            print(f"[{table}] 空表，跳过")
            continue
        placeholders = ",".join(["%s"] * len(cols))
        col_sql = ",".join(cols)
        # 分批写
        BATCH = 500
        n = 0
        with dst.cursor() as cur:
            for i in range(0, len(rows), BATCH):
                batch = [tuple(r) for r in rows[i:i+BATCH]]
                cur.executemany(
                    f"INSERT INTO {table}({col_sql}) VALUES({placeholders}) "
                    f"ON CONFLICT DO NOTHING",
                    batch,
                )
                n += len(batch)
        dst.commit()
        print(f"[{table}] 迁移 {n} 行")
    src.close()
    dst.close()
    print("完成。建议在 Postgres 里跑 ANALYZE; 更新统计信息。")


if __name__ == "__main__":
    main()
