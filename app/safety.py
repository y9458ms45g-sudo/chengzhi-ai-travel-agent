"""
内容安全审核：政务/文旅场景的输入输出过滤。
- 输入：命中敏感类别直接拦截，返回合规话术，不进入 LLM。
- 输出：对 LLM 回答做二次过滤，命中敏感词替换为安全提示。
采用本地规则词表，不依赖外部审核服务，比赛 MVP 可离线运行。
"""
import re
import logging

logger = logging.getLogger("agent.safety")

# 敏感类别 → 词表。宁可漏过不可误伤正常文旅内容，词表保持克制。
_BLOCK_CATEGORIES = {
    "违法违禁": [
        "赌博", "博彩", "赌场", "下注", "赌球", "毒品", "吸毒", "冰毒", "海洛因",
        "枪支", "炸药", "雷管", "制作炸弹", "制毒", "贩毒", "走私", "嫖娼", "卖淫",
    ],
    "暴恐极端": [
        "恐怖袭击", "制造恐怖", "极端组织", "自杀式", "分裂国家", "武装暴动",
    ],
    "色情低俗": [
        "裸体", "色情视频", "AV", "成人网站", "裸聊",
    ],
}

# 合并成正则（按类别分组，便于日志标注）
_BLOCK_PATTERNS = {
    cat: re.compile("|".join(re.escape(w) for w in words))
    for cat, words in _BLOCK_CATEGORIES.items()
}

_SAFE_REPLY = (
    "抱歉，这个问题我无法回答。我是文旅助手，只能为你提供旅游、景点、美食、"
    "天气、交通和行程规划方面的帮助。如果你想了解某座城市怎么玩，告诉我城市名就好～"
)


def moderate_input(text: str):
    """审核用户输入。返回 (allowed, reason)。allowed=False 时调用方应直接返回 SAFE_REPLY。"""
    if not text:
        return True, ""
    for cat, pat in _BLOCK_PATTERNS.items():
        m = pat.search(text)
        if m:
            logger.info(f"[safety] input blocked: category={cat} hit={m.group(0)[:20]}")
            return False, cat
    return True, ""


def moderate_output(text: str) -> str:
    """审核 LLM 输出：命中敏感词则整段替换为安全提示（避免模型漏网）。"""
    if not text:
        return text
    for cat, pat in _BLOCK_PATTERNS.items():
        if pat.search(text):
            logger.info(f"[safety] output sanitized: category={cat}")
            return (
                "（系统安全提示：以上内容包含不适宜信息，已自动屏蔽。"
                "如需旅游规划帮助，请重新描述你的需求。）"
            )
    return text
