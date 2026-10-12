"""
工具注册表：统一管理 Agent 可调用的工具
"""
from app.tools.weather import query_weather
from app.tools.traffic import query_traffic
from app.tools.knowledge import search_knowledge
from app.tools.web_search import web_search
from app.tools.scenic import query_scenic
from app.tools.budget import query_budget, calc_budget

# 工具名 → 函数映射
TOOLS = {
    "weather": query_weather,
    "traffic": query_traffic,
    "knowledge": search_knowledge,
    "web_search": web_search,
    "scenic": query_scenic,
    "budget": query_budget,
}

# 给大模型看的工具描述（Planner 用）
TOOL_DESCRIPTIONS = """
可用工具列表：
1. weather(城市名)：查询未来3天天气、温度、降水、风力。当需要了解出行期间天气时调用。
2. traffic(城市, 起点, 终点)：查询两点间驾车距离与耗时。当需要规划行程交通时调用。
3. knowledge(查询问题)：检索文旅知识库（民俗、文化、历史、景点介绍）。当需要了解当地风俗习惯、文化背景、官方景点介绍时调用。
4. web_search(搜索关键词)：联网搜索景点信息、近期活动、游客评价、避雷信息。当需要找最新景点、商业活动、网友真实体验时调用。
5. scenic(景点名称)：查询主要旅游城市景点的开放时间、门票、地址、注意事项。当用户问到具体景点名、需要确认门票/开放时间时调用；查不到时会提示改用 web_search。
6. budget(城市, 人数, 天数, 档次)：按城市消费档估算门票/餐饮/住宿/交通明细，输出人均与总额。当用户问"预算多少/大概花多少钱/人均多少"时调用。
"""

# Function Calling 格式的工具定义（OpenAI tools 格式）
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_weather",
            "description": "查询城市未来3天天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "城市名，如重庆"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_traffic",
            "description": "查询两点间驾车路线与耗时",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                },
                "required": ["city", "origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "检索文旅知识库（民俗、文化、景点官方介绍）",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "联网搜索网红打卡点、近期活动、游客评价",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_scenic",
            "description": "查询景点开放时间、门票、地址",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_budget",
            "description": "按城市/人数/天数/档次估算旅行预算明细",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如成都"},
                    "people": {"type": "integer", "description": "人数，默认2"},
                    "days": {"type": "integer", "description": "天数，默认2"},
                    "level": {"type": "string", "enum": ["经济", "舒适", "品质"], "description": "消费档次"},
                },
                "required": ["city"],
            },
        },
    },
]

# 工具函数映射（Function Calling 调用时用）
FUNC_MAP = {
    "query_weather": query_weather,
    "query_traffic": query_traffic,
    "search_knowledge": search_knowledge,
    "web_search": web_search,
    "query_scenic": query_scenic,
    "query_budget": query_budget,
}


def execute_tool(tool_name: str, args: dict, timeout: float = 10.0) -> str:
    """统一执行入口：try/except + 硬超时 + 友好失败提示"""
    func = FUNC_MAP.get(tool_name)
    if not func:
        return f"未知工具：{tool_name}，已跳过。"
    import concurrent.futures
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(func, **(args or {}))
            return fut.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return f"[工具超时] {tool_name} 在 {timeout:.0f}s 内未返回，已跳过，请基于已有信息回答。"
    except TypeError as e:
        return f"[参数有误] {tool_name} 参数不匹配：{e}。请用正确参数重试或换用其他工具。"
    except Exception as e:
        return f"[工具失败] {tool_name} 执行出错：{e}。请基于已有信息回答，不要编造。"
