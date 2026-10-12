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

# 角色人设（切换后注入AI对话）
IP_PERSONAS = {
    "master": "你是小知，城知总控官，负责全局调度和默认对话。语气专业、亲切，帮用户规划整体行程。",
    "sichuan": "你是川川，四川省级接待官。语气热情活泼，带着四川口音，推荐四川全省的美食、景点和文化。",
    "chongqing": "你是渝渝，重庆省级接待官。性格豪爽直接，带着重庆口音，推荐重庆的火锅、夜景和山城步道。",
    "chengdu": "你是蓉蓉，成都接待官。语气慵懒悠闲，带着成都慢生活气质，推荐茶馆、熊猫、宽窄巷子和串串香。",
    "meishan": "你是苏苏，眉山接待官。文质彬彬，带着东坡文化气质，推荐三苏祠、东坡美食和青神竹编。",
    "leshan": "你是山山，乐山接待官。语气沉稳，推荐乐山大佛、峨眉山和跷脚牛肉。",
    "yibin": "你是酒仙，宜宾接待官。性格豪爽，带着酒文化气质，推荐五粮液、蜀南竹海和李庄白肉。",
    "zigong": "你是灯灯，自贡接待官。语气活泼，推荐自贡灯会、恐龙博物馆和盐帮菜。",
    "mianyang": "你是绵宝，绵阳接待官。科技感十足，推荐两弹城、科技城和米粉。",
    "nanchong": "你是充充，南充接待官。历史文化氛围浓厚，推荐阆中古城、嘉陵江和川北凉粉。",
    "cq_county": "你是渝县，重庆区县接待官。熟悉重庆各区县特色，推荐武隆天坑、酉阳桃花源和巫山小三峡。",
    "beijing": "你是京京，北京接待官。语气大气沉稳，带着老北京味儿，推荐故宫、长城、烤鸭和胡同。",
    "xian": "你是西西，西安接待官。历史感厚重，推荐兵马俑、大雁塔、肉夹馍和回民街。",
}

# 角色名映射（用于显示当前角色）
IP_NAME_MAP = {}
for group_name, items in IPS:
    for ip_id, avatar_char, color, name, title in items:
        IP_NAME_MAP[ip_id] = (name, title)

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

# ============ 启动页（竹林） ============
if "started" not in st.session_state:
    # 读取本地竹林照片并转 base64（不依赖外部 URL）
    import base64
    bg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "images", "splash-bg.jpg")
    if os.path.exists(bg_path):
        with open(bg_path, "rb") as f:
            bg_b64 = base64.b64encode(f.read()).decode()
        bg_css = f"url('data:image/jpeg;base64,{bg_b64}') center/cover no-repeat fixed"
    else:
        bg_css = "linear-gradient(160deg, #1a3a2a 0%, #2d5a3d 40%, #3d7a5a 100%)"
    st.markdown(f"""
    <style>
      .stApp {{
        background: linear-gradient(160deg, rgba(26,77,58,0.55) 0%, rgba(26,77,58,0.75) 100%), {bg_css} !important;
      }}
      .launch-page {{
        height: 90vh; display: flex; flex-direction: column;
        align-items: center; justify-content: center; text-align: center;
        color: #fff;
      }}
      .launch-subtitle {{
        font-size: 14px; letter-spacing: 6px; opacity: 0.75; margin-bottom: 30px;
        animation: fadeInDown 1.2s ease-out 0.3s both;
      }}
      .launch-title {{
        font-size: 110px; font-weight: 900; letter-spacing: 24px;
        text-indent: 24px; margin-bottom: 0; text-shadow: 0 4px 30px rgba(0,0,0,0.4);
        font-family: 'Noto Serif SC', serif;
        animation: fadeInZoom 1.5s ease-out 0.6s both;
      }}
      .launch-divider {{
        width: 60px; height: 2px; background: rgba(255,255,255,0.4);
        margin: 28px 0;
        animation: fadeIn 1s ease-out 1.5s both;
      }}
      .launch-desc {{
        font-size: 16px; line-height: 2; opacity: 0.85; letter-spacing: 2px;
        animation: fadeInUp 1.2s ease-out 1.8s both;
      }}
      @keyframes fadeInDown {{
        from {{ opacity: 0; transform: translateY(-20px); }}
        to {{ opacity: 0.75; transform: translateY(0); }}
      }}
      @keyframes fadeInZoom {{
        from {{ opacity: 0; transform: scale(0.8); }}
        to {{ opacity: 1; transform: scale(1); }}
      }}
      @keyframes fadeIn {{
        from {{ opacity: 0; }}
        to {{ opacity: 1; }}
      }}
      @keyframes fadeInUp {{
        from {{ opacity: 0; transform: translateY(20px); }}
        to {{ opacity: 0.85; transform: translateY(0); }}
      }}
    </style>
    <div class="launch-page">
      <div class="launch-subtitle">城 知 文 旅</div>
      <div class="launch-title">城知</div>
      <div class="launch-divider"></div>
      <div class="launch-desc">
        全 国 文 旅 · 你 的 接 待 官<br>
        不推网红打卡 · 只讲真实好去处<br>
        帮你把行程算明白
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1.2, 1])
    with col_btn2:
        if st.button("🌿 开始对话", use_container_width=True, type="primary"):
            st.session_state.started = True
            st.rerun()
    st.stop()

# ============ 三栏布局 ============
col_left, col_center, col_right = st.columns([1.2, 4, 1.6])

# 左栏：总控台（可点击切换角色，带头像色块）
if "current_ip" not in st.session_state:
    st.session_state.current_ip = "master"

with col_left:
    for group_name, items in IPS:
        st.markdown(f'<div class="ip-group-label">{group_name}</div>', unsafe_allow_html=True)
        for ip_id, avatar_char, color, name, title in items:
            is_active = (ip_id == st.session_state.current_ip)
            # 按钮文字：色块emoji + 角色名 + 头衔
            btn_label = f"🟦 {name}" if is_active else f"⬜ {name}"
            if st.button(
                btn_label,
                key=f"ip_{ip_id}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
                help=title,
            ):
                st.session_state.current_ip = ip_id
                # 切换角色时清空对话，开始新人设
                st.session_state.messages = []
                st.session_state.agent_session.reset()
                st.rerun()

# 中栏：对话区
current_ip = st.session_state.current_ip
current_name, current_title = IP_NAME_MAP.get(current_ip, ("小知·总控官", "全局调度"))

with col_center:
    if not st.session_state.messages:
        st.markdown(f"""
        <div class="welcome">
          <div style="font-size:48px;margin-bottom:16px">🏔️</div>
          <h2>你好，我是{current_name}</h2>
          <p>{current_title}，你的专属文旅接待官。<br>
          告诉我你在哪个城市、想玩几天，我来帮你安排。<br><br>
          <span style="color:#aaa;font-size:13px">例如："重庆3天2晚带老人"或"成都到西安怎么走"</span></p>
        </div>
        """, unsafe_allow_html=True)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 右栏：非遗文化墙（可点击展开）
with col_right:
    st.markdown('<div class="hr-title">🎭 非遗文化墙</div>', unsafe_allow_html=True)
    st.markdown('<div class="hr-sub">指尖上的中国 · 点开任意一项听故事</div>', unsafe_allow_html=True)
    for emoji, name, city, desc in HERITAGE:
        with st.expander(f"{emoji} {name} {city}"):
            st.markdown(desc)

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
                    # 注入当前角色人设
                    persona = IP_PERSONAS.get(current_ip, "")
                    enhanced_input = f"{persona}\n\n用户需求：{user_input}" if persona else user_input
                    draft = run_agent(enhanced_input, st.session_state.agent_session)
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
