# AI文旅Agent

通过大模型调度天气、路况、民俗知识库、网红打卡点、景点信息等多源数据，为游客自动生成个性化旅游攻略。

## 快速开始

### 1. 安装依赖

```bash
cd wenlv-agent
pip install -r requirements.txt
```

### 2. 配置API密钥

复制 `.env.example` 为 `.env`，填入你自己的密钥：

```
LLM_API_KEY=sk-xxx          # 大模型（DeepSeek/通义/智谱均可）
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

**最少只配大模型就能跑**（其他工具未配置时会用模拟数据）。

推荐注册（免费额度）：
- 大模型：DeepSeek https://platform.deepseek.com/
- 天气：和风天气 https://dev.qweather.com/
- 地图：高德开放平台 https://lbs.amap.com/
- 搜索：博查AI https://api.bochaai.com/

### 3. 构建知识库（首次运行）

```bash
python build_knowledge.py
```

### 4. 启动前端

```bash
streamlit run streamlit_app.py
```

浏览器打开 http://localhost:8501 即可使用。

## 项目结构

```
wenlv-agent/
├── app/
│   ├── main.py              # FastAPI 后端
│   ├── llm.py               # LLM 客户端封装
│   ├── agent/
│   │   ├── planner.py       # 任务拆解
│   │   ├── executor.py     # ReAct 执行循环
│   │   └── reflector.py     # 反思校验
│   └── tools/
│       ├── weather.py       # 天气
│       ├── traffic.py       # 路况
│       ├── knowledge.py    # RAG知识库
│       ├── web_search.py    # 联网搜索
│       └── scenic.py       # 景点信息
├── data/
│   ├── knowledge/          # 原始文档（重庆文旅知识库.md）
│   └── chroma_db/          # 向量库
├── build_knowledge.py      # 构建知识库脚本
├── streamlit_app.py        # 前端
└── .env                    # 你的API密钥
```

## 已实现功能

- [x] 5个工具：天气、路况、知识库RAG、联网搜索、景点信息
- [x] ReAct 执行循环（LLM自主决定调用工具）
- [x] 反思校验（自动检查攻略问题）
- [x] 新建任务判断（说"重新来"自动清空上下文）
- [x] Streamlit 对话界面
- [x] 重庆知识库（民俗、景点、美食、交通、避坑）
- [ ] 并发工具调用（当前串行）
- [ ] 攻略导出PDF

## 比赛演示建议

1. 提前配好API密钥，运行 `python build_knowledge.py`
2. `streamlit run streamlit_app.py` 启动
3. 演示输入："重庆3天2晚，预算2000，喜欢美食和小众打卡"
4. 展示AI自动调用工具、生成攻略的过程
5. 多轮追问："第二天改成博物馆""预算降到1500"
6. 展示新建任务："重新规划，换成成都"
