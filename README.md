# 城知 · AI文旅智能助手

> **🎯 在线 Demo（面试官可直接体验完整版）：** [https://chengzhi-ai-travel-agent-a2724.containers.snapdeploy.app](https://chengzhi-ai-travel-agent-a2724.containers.snapdeploy.app)
> 
> 竹林启动页 + 三栏精美界面 + 13个角色人设 + 非遗文化墙

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

### 4. 启动应用

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

浏览器打开 http://localhost:8000 即可使用（完整版精美界面）。

**备选：** 也可以用 Streamlit 简化版：
```bash
streamlit run streamlit_app.py
```

## 项目结构

```
wenlv-agent/
├── app/
│   ├── main.py              # FastAPI 后端（返回 web/index.html）
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
├── web/
│   ├── index.html           # 精美前端（单页应用，148KB）
│   └── images/              # 启动页竹林背景等图片
├── data/
│   ├── knowledge/          # 原始文档（重庆文旅知识库.md）
│   └── chroma_db/          # 向量库
├── build_knowledge.py      # 构建知识库脚本
├── streamlit_app.py        # Streamlit 简化版前端
├── requirements.txt        # Python 依赖
├── Procfile                # 部署启动命令
└── .env                    # 你的API密钥
```

## 已实现功能

### 核心能力
- [x] 5个工具：天气、路况、知识库RAG、联网搜索、景点信息
- [x] ReAct 执行循环（LLM自主决定调用工具）
- [x] 反思校验（自动检查攻略问题）
- [x] 新建任务判断（说"重新来"自动清空上下文）
- [x] 重庆知识库（民俗、景点、美食、交通、避坑）

### 精美前端（web/index.html）
- [x] 竹林实景启动页
- [x] 三栏布局（角色列表 + 对话区 + 非遗文化墙）
- [x] 13个角色人设（小知总控官、川川、渝渝、蓉蓉、苏苏、山山、酒仙、灯灯...）
- [x] 角色头像照片
- [x] 非遗文化墙（川剧变脸、蜀绣、川江号子、铜梁龙舞）
- [x] 消息卡片 + 点赞点踩
- [x] 小红书/抖音/马蜂窝分享按钮
- [x] 高德导航按钮
- [x] 语音输入（麦克风按钮）
- [x] 功能菜单（团建方案、预算测算、实时路况、逛一逛）
- [x] 四川/重庆城市切换

### 待开发
- [ ] 并发工具调用（当前串行）
- [ ] 攻略导出PDF
- [ ] 开发者控制台

## 比赛演示建议

1. 提前配好API密钥，运行 `python build_knowledge.py`
2. `streamlit run streamlit_app.py` 启动
3. 演示输入："重庆3天2晚，预算2000，喜欢美食和小众打卡"
4. 展示AI自动调用工具、生成攻略的过程
5. 多轮追问："第二天改成博物馆""预算降到1500"
6. 展示新建任务："重新规划，换成成都"
