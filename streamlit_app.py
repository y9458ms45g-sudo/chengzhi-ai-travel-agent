"""
城知 · AI文旅智能对话系统（Streamlit版）
运行：streamlit run streamlit_app.py
"""
import streamlit as st
import sys
import os

# 把项目根目录加入path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Streamlit Cloud 部署适配：把 st.secrets 注入环境变量
try:
    for _k, _v in st.secrets.items():
        if _k not in os.environ:
            os.environ[_k] = str(_v)
except Exception:
    pass

st.set_page_config(
    page_title="城知 · 文旅智能对话系统",
    page_icon="🎋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============ 自定义CSS ============
st.markdown("""
<style>
  /* 隐藏默认padding */
  .block-container {padding-top: 0; padding-bottom: 0; max-width: 100%;}
  
  /* 顶栏 */
  .topbar {
    background: linear-gradient(135deg, #1a3a2a 0%, #2d5a3d 100%);
    padding: 12px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: #fff;
  }
  .topbar-logo {
    display: flex; align-items: center; gap: 12px;
  }
  .topbar-logo .logo-box {
    width: 36px; height: 36px; background: #fff; color: #1a3a2a;
    border-radius: 8px; display: flex; align-items: center; justify-content: center;
    font-weight: 900; font-size: 18px;
  }
  .topbar-logo .title {font-size: 20px; font-weight: 700;}
  .topbar-logo .subtitle {font-size: 12px; opacity: 0.7;}
  .city-switch {display: flex; gap: 8px;}
  .city-btn {
    padding: 6px 16px; border-radius: 20px; font-size: 13px;
    background: rgba(255,255,255,0.15); color: #fff; border: none;
  }
  .city-btn.active {background: #fff; color: #1a3a2a; font-weight: 600;}
  
  /* 三栏布局 */
  .main-row {display: flex; gap: 0; min-height: calc(100vh - 120px);}
  .col-left {width: 220px; background: #f8f7f4; border-right: 1px solid #e8e6e0; padding: 12px 8px; overflow-y: auto;}
  .col-center {flex: 1; padding: 20px 24px; overflow-y: auto;}
  .col-right {width: 300px; background: #faf9f6; border-left: 1px solid #e8e6e0; padding: 12px; overflow-y: auto;}
  
  /* 角色列表 */
  .ip-group-label {font-size: 11px; color: #999; padding: 8px 8px 4px; font-weight: 600;}
  .ip-item {
    display: flex; align-items: center; gap: 10px; padding: 8px;
    border-radius: 8px; cursor: pointer; margin-bottom: 2px;
    border-left: 3px solid transparent;
  }
  .ip-item:hover {background: #f0ede5;}
  .ip-item.active {background: #e8f0e5; border-left-color: #2d6a4f;}
  .ip-avatar {
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-size: 14px; font-weight: 700; flex-shrink: 0;
  }
  .ip-name {font-size: 13px; font-weight: 600; color: #222;}
  .ip-title {font-size: 11px; color: #888;}
  
  /* 欢迎区 */
  .welcome {text-align: center; padding: 40px 20px; color: #555;}
  .welcome h2 {font-size: 22px; color: #2d6a4f; margin-bottom: 8px;}
  .welcome p {font-size: 14px; line-height: 1.8;}
  
  /* 非遗文化墙 */
  .hr-title {font-size: 15px; font-weight: 700; color: #2d6a4f; padding: 8px 4px;}
  .hr-sub {font-size: 11px; color: #999; padding: 0 4px 12px;}
  .hr-card {
    background: #fff; border-radius: 10px; padding: 12px; margin-bottom: 10px;
    border: 1px solid #eee;
  }
  .hr-emoji {font-size: 28px;}
  .hr-name {font-size: 14px; font-weight: 600; color: #222; margin: 4px 0;}
  .hr-city {font-size: 11px; color: #e67e22;}
  .hr-desc {font-size: 12px; color: #666; line-height: 1.6; margin-top: 6px;}
  
  /* 底部免责声明 */
  .gov-footer {
    background: #f5f3ee; padding: 10px 24px; text-align: center;
    font-size: 11px; color: #888; border-top: 1px solid #e8e6e0;
  }
  
  /* 隐藏 Streamlit 默认元素 */
  #MainMenu {visibility: hidden;}
  footer {visibility: hidden;}
  .stChatInput {padding: 0 20px 10px;}
</style>
""", unsafe_allow_html=True)

# ============ 顶栏 ============
st.markdown("""
<div class="topbar">
  <div class="topbar-logo">
    <div class="logo-box">城</div>
    <div>
      <div class="title">城知</div>
      <div class="subtitle">文旅智能对话系统</div>
    </div>
  </div>
  <div class="city-switch">
    <div class="city-btn active">🏔️ 四川</div>
    <div class="city-btn">🌉 重庆</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ============ 角色数据 ============
IPS = [
    ("总控台", [("master", "知", "#1a3a4a", "小知·总控官", "全局调度 · 默认对话")]),
    ("省级接待官", [
        ("sichuan", "川", "#2d6a4f", "川川", "四川省级接待官"),
        ("chongqing", "渝", "#c0392b", "渝渝", "重庆省级接待官"),
    ]),
    ("成都平原圈", [
        ("chengdu", "蓉", "#e67e22", "蓉蓉", "成都 · 休闲之都"),
        ("meishan", "苏", "#16a085", "苏苏", "眉山 · 东坡故里"),
    ]),
    ("川南", [
        ("leshan", "佛", "#8e44ad", "山山", "乐山 · 大佛之城"),
        ("yibin", "酒", "#2980b9", "酒仙", "宜宾 · 酒香之城"),
        ("zigong", "灯", "#d35400", "灯灯", "自贡 · 恐龙灯城"),
    ]),
    ("川北 / 川东北", [
        ("mianyang", "绵", "#7f8c8d", "绵宝", "绵阳 · 科技之城"),
        ("nanchong", "充", "#c0392b", "充充", "南充 · 嘉陵古城"),
    ]),
    ("重庆区县", [
        ("cq_county", "县", "#34495e", "渝县", "重庆区县 · 山水江城"),
    ]),
    ("华北 · 西北", [
        ("beijing", "京", "#c0392b", "京京", "北京 · 帝都"),
        ("xian", "陕", "#b8860b", "西西", "西安 · 古都长安"),
    ]),
]

# ============ 非遗数据 ============
HERITAGE = [
    ("🎭", "川剧变脸", "📍成都", "一秒换脸的绝活。川剧绝活，清末康子林首创扯线变脸，一场最多连变九张脸，被誉为东方魔术。"),
    ("🪡", "蜀绣", "📍成都", "针尖上的山水。中国四大名绣之一，以针代笔、以线代墨，最高境界是双面三异绣。"),
    ("🚢", "川江号子", "📍重庆", "川江船工的呐喊。被誉为长江文化活化石，一领众和，与险滩恶水搏斗的生命之歌。"),
    ("🐉", "铜梁龙舞", "📍重庆铜梁", "会跳舞的东方巨龙。铜梁大龙长约50米，需三十人同舞，曾登北京奥运开幕式。"),
    ("🎋", "青神竹编", "📍眉山青神", "薄如蝉翼的竹丝。一根慈竹可劈两万根竹丝，最细0.02毫米，作品曾作国礼赠送外国元首。"),
]

# ============ 初始化 session ============
if "agent_session" not in st.session_state:
    from app.agent.executor import Session
    st.session_state.agent_session = Session()

if "messages" not in st.session_state:
    st.session_state.messages = []

# ============ 三栏布局 ============
col_left, col_center, col_right = st.columns([1.2, 4, 1.6])

# 左栏：总控台
with col_left:
    for group_name, items in IPS:
        st.markdown(f'<div class="ip-group-label">{group_name}</div>', unsafe_allow_html=True)
        for ip_id, avatar_char, color, name, title in items:
            active = "active" if ip_id == "master" else ""
            st.markdown(f"""
            <div class="ip-item {active}">
              <div class="ip-avatar" style="background:{color}">{avatar_char}</div>
              <div>
                <div class="ip-name">{name}</div>
                <div class="ip-title">{title}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

# 中栏：对话区
with col_center:
    if not st.session_state.messages:
        st.markdown("""
        <div class="welcome">
          <div style="font-size:48px;margin-bottom:16px">🏔️</div>
          <h2>你好，我是小知</h2>
          <p>我是城知总控官，你的专属文旅调度助手。<br>
          告诉我你在哪个城市、想玩几天，我来帮你安排。<br><br>
          <span style="color:#aaa;font-size:13px">例如："重庆3天2晚带老人"或"成都到西安怎么走"</span></p>
        </div>
        """, unsafe_allow_html=True)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 右栏：非遗文化墙
with col_right:
    st.markdown('<div class="hr-title">🎭 非遗文化墙</div>', unsafe_allow_html=True)
    st.markdown('<div class="hr-sub">指尖上的中国 · 点开任意一项听故事</div>', unsafe_allow_html=True)
    for emoji, name, city, desc in HERITAGE:
        st.markdown(f"""
        <div class="hr-card">
          <div style="display:flex;align-items:center;gap:8px">
            <span class="hr-emoji">{emoji}</span>
            <div>
              <div class="hr-name">{name}</div>
              <div class="hr-city">{city}</div>
            </div>
          </div>
          <div class="hr-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

# ============ 输入框 ============
user_input = st.chat_input("说说你的旅游需求...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with col_center:
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("AI正在查询天气、路况、景点、民俗信息，请稍候..."):
                from app.agent.executor import run_agent, should_reset
                if should_reset(user_input, "", 0):
                    st.session_state.agent_session.reset()
                try:
                    draft = run_agent(user_input, st.session_state.agent_session)
                    from app.agent.reflector import reflect
                    review = reflect(draft)
                    if review.get("has_problem"):
                        final = review.get("corrected_draft", draft)
                    else:
                        final = draft
                    st.markdown(final)
                    st.session_state.messages.append({"role": "assistant", "content": final})
                except Exception as e:
                    st.error(f"生成失败：{e}")
                    st.info("提示：请检查API密钥是否正确配置。")

# ============ 底部免责声明 ============
st.markdown("""
<div class="gov-footer">
  <strong>⚠️ 本服务由AI生成内容，仅供出行参考，不构成任何承诺。</strong>
  票价/开放时间以景区官方公告为准 · 对话数据仅用于服务改进，可随时「新对话」清空 ·
  隐私政策 · 用户协议<br>
  © 城知文旅智能服务平台 v4.0 · 技术支持：城知工作室
</div>
""", unsafe_allow_html=True)
