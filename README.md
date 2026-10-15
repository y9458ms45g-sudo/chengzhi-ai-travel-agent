# 城知 · ChengZhi AI 文旅 Agent

> 一个面向 C 端游客的多 Agent 文旅对话系统：总控官 + 省级接待官，用户提到哪座城，就由那座城的本地朋友出来接话。

[![Eval](https://img.shields.io/badge/eval-32%2F32%20pass-brightgreen)](scripts/eval.py)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## ✨ 核心特性

- **多 Agent 协作**：1 个总控官（小知）+ 60+ 城市接待官（蓉蓉/渝渝/京京…），基于关键词规则自动路由，毫秒级切城
- **三段式架构**：Planner（任务拆解 + 并行工具调用）→ Executor（ReAct 自由循环）→ Reflector（事实自校验）
- **出发地/目的地消歧**：用前后 6-8 字窗口识别"从重庆去成都"里谁是起点谁是终点，交通建议不会算错
- **SSE 流式输出**：边生成边吐 token，前端实时看到工具调用和回答
- **双层安全审核**：输入拦截（省 token）+ 输出过滤（合规）
- **长期用户记忆**：每轮后台小模型抽取"带老人/不吃辣/预算"等结构化偏好，跨会话生效
- **可观测埋点**：每次请求自动写 metrics 表，P99 延迟、路由分布、Reflector 修复率可聚合
- **自动化回归**：`scripts/eval.py` 32 条 golden set，改完 prompt 秒出通过率

## 🏗️ 架构

```
用户输入
   │
   ▼
executor.run_agent_stream()
   ├─ 0. 重置判断（关键词/15轮/天数变化）
   ├─ 0.5 输入安全审核
   ├─ 1. 城市识别（规则法，区分出发地 vs 目的地）
   ├─ 1.5 多城合奏（collaborator 并行调子 Agent）
   ├─ 1.7 单城转接 → 注入城市锁定 system prompt
   ├─ 2. 身份锚定（master / 城市接待官）
   ├─ 2.1 长期偏好注入
   ├─ 2.5 Planner 首轮：任务清单 → 线程池并行调工具
   ├─ 3. ReAct 循环（最多 8 次工具调用）
   ├─ 4. Reflector 自校验（事实错误回喂重写）
   ├─ 5. 输出安全二次过滤
   └─ 6. 落库 SQLite + 后台抽偏好 + metrics 埋点
```

## 🚀 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/yourname/chengzhi-agent.git
cd chengzhi-agent
pip install -r requirements.txt
```

### 2. 配置 API 密钥

```bash
cp .env.example .env
# 编辑 .env，至少填 LLM_API_KEY（DeepSeek/OpenAI 兼容接口）
```

### 3. 初始化数据库

```bash
python -c "from app.db import init_db; init_db()"
```

### 4. 启动后端

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

浏览器打开 http://localhost:8000 即可使用（前端是单文件 `web/index.html`）。

### 5. 跑自动化回归

```bash
python -m scripts.eval
# 预期：32/32 通过
```

## 📁 项目结构

```
chengzhi-agent/
├── app/
│   ├── main.py              # FastAPI 路由 + SSE 端点
│   ├── llm.py               # chat / chat_with_tools / chat_stream 封装
│   ├── db.py                # SQLite（WAL 模式）+ metrics 表
│   ├── safety.py            # 双层内容安全过滤
│   ├── feature_flags.py     # 灰度发布（按 session hash 分流）
│   ├── agent/
│   │   ├── executor.py      # ★ ReAct 执行循环（核心，1200 行）
│   │   ├── planner.py       # Planner：任务拆解
│   │   ├── reflector.py     # Reflector：事实自校验
│   │   └── collaborator.py  # 多城合奏：并行子 Agent + master 合并
│   └── tools/
│       ├── weather.py        # 天气
│       ├── traffic.py        # 路况/高德导航
│       ├── knowledge.py     # 民俗知识库
│       ├── web_search.py    # 联网搜索
│       ├── scenic.py        # 景点门票/开放时间
│       └── budget.py         # 预算估算
├── web/
│   ├── index.html           # 单文件前端（竹子青绿主题）
│   └── images/              # 省级接待官头像
├── scripts/
│   ├── eval.py              # ★ 32 条自动化回归
│   └── migrate_to_postgres.py  # 生产数据库迁移
├── docs/
│   └── production_deployment.md # 生产化改造清单
├── data/                    # SQLite 数据库（git 忽略）
└── requirements.txt
```

## 🎯 已实现 vs 待办

| 模块 | 状态 |
|---|---|
| ReAct 执行循环 | ✅ |
| Planner 并行工具调用（线程池 5 并发） | ✅ |
| Reflector 事实自校验 | ✅ |
| 60+ 城市路由 + 出发地/目的地消歧 | ✅ |
| 多 Agent 跨城合奏 | ✅ |
| SSE 流式输出 | ✅ |
| 双层安全审核 | ✅ |
| 长期用户偏好记忆（异步抽取） | ✅ |
| 工具硬超时（10s） | ✅ |
| 自动化回归 32 条 | ✅ |
| metrics 埋点 + 聚合 | ✅ |
| RAG 向量检索 | ✅ BM25 轻量版（生产可换 embedding+向量库） |
| 全链路 asyncio | 🟡 已留 async 接口，待迁移 |
| LLM-as-judge 端到端评测 | ✅ `python -m scripts.eval --judge` |
| 灰度发布 | ✅ `app/feature_flags.py`，按 session hash 分流 |

## 🧪 测试

```bash
python -m scripts.eval        # 纯函数回归（不花钱）
python -m scripts.eval --e2e   # 端到端冒烟（会调 LLM）
```

## 📊 生产部署

见 [docs/production_deployment.md](docs/production_deployment.md)。核心点：
- SQLite 已开 WAL 模式，MVP 阶段够用
- 生产换 Postgres：设 `DATABASE_URL` 环境变量 + 跑 `scripts/migrate_to_postgres.py`
- 7 个核心指标：P99 延迟、平均工具调用数、Reflector 修复率、安全拦截率、采纳率、重问率、路由分布

## 📝 License

MIT，见 [LICENSE](LICENSE)。

---

> 本项目为重庆邮电大学 × 政府 AI 创新应用大赛参赛作品。
