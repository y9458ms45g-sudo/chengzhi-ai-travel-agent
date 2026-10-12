"""
AI文旅Agent 前端（Streamlit）
运行：streamlit run streamlit_app.py
"""
import streamlit as st
import sys
import os

# 把项目根目录加入path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Streamlit Community Cloud 部署适配：把 st.secrets 注入环境变量
# （本地运行时 st.secrets 可能不存在，不影响；云上部署时所有 API Key 在此配置）
try:
    import streamlit as _st
    for _k, _v in _st.secrets.items():
        if _k not in os.environ:
            os.environ[_k] = str(_v)
except Exception:
    pass

st.set_page_config(
    page_title="AI文旅助手",
    page_icon="🏔️",
    layout="wide",
)

st.title("🏔️ AI文旅智能助手")
st.caption("输入你的旅游需求，AI自动查询天气、路况、民俗、景点、网红打卡点，为你生成专属攻略")

# 初始化session
if "agent_session" not in st.session_state:
    from app.agent.executor import Session
    st.session_state.agent_session = Session()

# 侧边栏：配置提示
with st.sidebar:
    st.header("⚙️ 配置状态")
    has_llm = bool(os.getenv("LLM_API_KEY") and "your-key" not in os.getenv("LLM_API_KEY", ""))
    has_weather = bool(os.getenv("WEATHER_API_KEY") and "your-qweather" not in os.getenv("WEATHER_API_KEY", ""))
    has_amap = bool(os.getenv("AMAP_API_KEY") and "your-amap" not in os.getenv("AMAP_API_KEY", ""))
    has_search = bool(os.getenv("SEARCH_API_KEY") and "your-bocha" not in os.getenv("SEARCH_API_KEY", ""))

    st.markdown(f"- 大模型：{'✅ 已配置' if has_llm else '❌ 未配置（请在.env中设置LLM_API_KEY）'}")
    st.markdown(f"- 天气API：{'✅ 已配置' if has_weather else '⚠️ 未配置（将使用模拟数据）'}")
    st.markdown(f"- 高德地图：{'✅ 已配置' if has_amap else '⚠️ 未配置（将使用模拟数据）'}")
    st.markdown(f"- 联网搜索：{'✅ 已配置' if has_search else '⚠️ 未配置（将使用模拟数据）'}")

    if st.button("🔄 清空对话，开启新任务"):
        st.session_state.agent_session.reset()
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.markdown("**使用示例：**")
    st.markdown("- 重庆3天2晚，喜欢美食和小众打卡，预算2000")
    st.markdown("- 周末去重庆，想看看有什么活动和网红点")
    st.markdown("- 去重庆要注意什么民俗？")

# 聊天历史
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入
user_input = st.chat_input("说说你的旅游需求...")
if user_input:
    if not has_llm:
        st.error("请先在 .env 文件中配置 LLM_API_KEY（大模型API密钥），再开始使用。")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("AI正在查询天气、路况、景点、民俗信息，请稍候..."):
            from app.agent.executor import run_agent, should_reset
            # 判断是否需要新建任务
            if should_reset(user_input, "", 0):
                st.session_state.agent_session.reset()
            try:
                draft = run_agent(user_input, st.session_state.agent_session)
                # 反思校验
                from app.agent.reflector import reflect
                review = reflect(draft)
                if review.get("has_problem"):
                    final = review.get("corrected_draft", draft)
                    with st.expander("🔍 智能审核发现的问题"):
                        for issue in review.get("issues", []):
                            st.markdown(f"- {issue}")
                else:
                    final = draft
                st.markdown(final)
                st.session_state.messages.append({"role": "assistant", "content": final})
            except Exception as e:
                st.error(f"生成失败：{e}")
                st.info("提示：请检查 .env 中的API密钥是否正确配置。")
