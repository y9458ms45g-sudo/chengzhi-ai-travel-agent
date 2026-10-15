# 生产部署与数据库迁移方案

> 本文档回答面试官："你说要上应用商店、对接文旅局，SQLite 够用吗？"

## 一、当前 MVP 为什么用 SQLite

| 维度 | SQLite | Postgres |
|---|---|---|
| 部署复杂度 | 0（单文件） | 需运维实例 |
| 并发写 | 弱（WAL 下约 100 TPS） | 强（万级 TPS） |
| 多机部署 | 不支持 | 原生支持 |
| 数据量 | < 100 万条消息 | 任意 |
| 适合阶段 | 比赛 Demo / 内测 | 公网上线 |

**结论**：比赛阶段用 SQLite 是对的——零运维、备份就是拷贝文件。但公网上线必须换。

## 二、换 Postgres 的迁移步骤

### 1. 装依赖
```
pip install psycopg[binary]
```

### 2. 环境变量切换
`.env` 加一行：
```
DATABASE_URL=postgresql://user:pass@host:5432/chengzhi
```

### 3. db.py 改连接层
当前 `_conn()` 是写死的 sqlite3。生产版改成：
```python
import os
DATABASE_URL = os.getenv("DATABASE_URL", "")

def _conn():
    if DATABASE_URL:
        import psycopg
        return psycopg.connect(DATABASE_URL, autocommit=True)
    # 否则走 SQLite（开发/比赛）
    ...
```

SQL 方言差异点（已经在代码里隔离）：
- `INSERT OR IGNORE` → `INSERT ... ON CONFLICT DO NOTHING`
- `?` 占位符 → `%s`
- `AUTOINCREMENT` → `SERIAL`
- 时间戳都是 INTEGER 秒，无方言问题

### 4. 数据迁移脚本
见 `scripts/migrate_to_postgres.py`：
- 读 SQLite 全表
- 按表顺序写入 Postgres（sessions → messages → user_profile → feedback → metrics）

### 5. 上线前 checklist
- [ ] 压测：100 并发请求，P99 < 5s
- [ ] 连接池：psycopg 用 `psycopg_pool.ConnectionPool`，min=2 max=10
- [ ] 备份：每天 `pg_dump` 到对象存储
- [ ] 索引：messages(session_id, id)、metrics(created_at) 已建
- [ ] 敏感数据：用户偏好里的手机号/地址要加密列存

## 三、其他生产化改造

| 项 | 现状 | 生产做法 |
|---|---|---|
| 模型调用 | 同步阻塞 | asyncio + 连接池 |
| web_search 超时 | 无硬超时 | httpx.AsyncClient(timeout=10) |
| LLM API key | 写 .env | 走 KMS / 环境变量注入 |
| 日志 | 本地文件 | 接 ELK / 字节内部日志平台 |
| 监控 | print + logger | Prometheus + Grafana（延迟、错误率、token 消耗） |
| 限流 | 无 | 按 session_id 每分钟 10 次 |
| 鉴权 | 无 | 接文旅局 SSO / JWT |
| 灰度 | 无 | 按 user_id hash 分流 10% 新 prompt |

## 四、指标体系（已在代码里埋点）

`metrics` 表每次请求写一行，核心指标：

| 指标 | 计算方式 | 健康阈值 |
|---|---|---|
| P50/P99 延迟 | `latency_ms` 分位数 | P99 < 8s |
| 平均工具调用数 | `AVG(tool_calls)` | 2-4 次合理 |
| Reflector 修复率 | `SUM(has_reflector_fix)/COUNT(*)` | < 10%（高说明初版质量差） |
| 安全拦截率 | `SUM(safety_blocked)/COUNT(*)` | < 5% |
| 路由分布 | `GROUP BY routed_ip` | 看哪些城市冷/热 |
| 👍/👎 采纳率 | `feedback` 表 rating=1 / total | > 70% |
| 重问率 | 同 session 5 分钟内重复问题占比 | < 20% |

管理后台接口：`GET /api/admin/metrics`（用 `db.metrics_summary()`）。
