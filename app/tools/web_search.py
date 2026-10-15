"""
联网搜索工具：调用博查搜索 API（或其他搜索API）
文档：https://api.bochaai.com/
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SEARCH_URL = "https://api.bochaai.com/v1/web-search"


from app.tools.sanitize import sanitize_external


def web_search(query: str, count: int = 5) -> str:
    """
    联网搜索：查网红打卡点、近期活动、游客评价。
    入参：搜索关键词
    返回：相关标题、摘要、来源
    """
    key = os.getenv("SEARCH_API_KEY")
    if not key or key == "your-bocha-key":
        return (
            f"[联网搜索未配置API密钥] 模拟结果：关于「{query}」的热门信息包括——"
            "李子坝轻轨穿楼（网红打卡，建议上午去人少）、"
            "鹅岭二厂文创园（拍照出片）、"
            "观音桥好吃街（本地小吃集中）。"
            "以上为模拟数据，请配置真实搜索API。"
        )

    try:
        r = requests.post(
            SEARCH_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={"query": query, "count": count},
            timeout=15,
        )
        data = r.json()
        # 错误处理
        if r.status_code != 200 or data.get("code") not in (200, None, 0):
            err_msg = data.get("message", "") or data.get("msg", "")
            return f"[联网搜索暂不可用] {err_msg}。请基于已有知识库回答，并提示用户信息可能不是最新。"

        items = data.get("data", {}).get("webPages", {}).get("value", [])
        if not items:
            return f"[联网搜索] 关于「{query}」未找到有效结果，请基于已有知识回答。"
        blocks = []
        for it in items[:count]:
            blocks.append(
                f"标题：{it.get('name', '')}\n"
                f"摘要：{it.get('snippet', '')}\n"
                f"来源：{it.get('url', '')}"
            )
        return sanitize_external("\n---\n".join(blocks), max_keep=count)
    except Exception as e:
        return f"[联网搜索失败] {e}。请基于已有知识回答。"
