"""
Planner：分析用户需求，提取参数，拆解任务
"""
import json
from app.llm import chat
from app.tools import TOOL_DESCRIPTIONS


SYSTEM_PROMPT = f"""你是一个旅游规划任务拆解专家。请分析用户的旅游需求，输出JSON格式：
{{
  "user_params": {{
    "destination": "目的地",
    "days": 天数（整数）,
    "budget": "预算描述",
    "preferences": ["偏好1", "偏好2"],
    "special_notes": "其他特殊要求"
  }},
  "tasks": [
    {{"tool": "工具名", "query": "查询内容"}}
  ]
}}

{TOOL_DESCRIPTIONS}

规则：
1. 根据用户需求决定需要调用哪些工具
2. 每个任务指定一个工具和具体查询内容
3. 必须包含天气查询
4. 如果用户提到民俗/文化/风俗，必须调用knowledge
5. 如果用户提到网红/打卡/活动/最新，必须调用web_search
6. **意图短路**：如果用户问题与旅游/出行/景点/美食/天气完全无关（如股票、编程、日常闲聊、打招呼），tasks 返回空数组 []，user_params 填 null。
7. 不要输出JSON以外的内容
"""


def plan(user_input: str) -> dict:
    """接收用户需求，返回任务规划"""
    try:
        result = chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            temperature=0.2,
            response_format="json",
        )
        return json.loads(result)
    except Exception as e:
        # 解析失败时给一个默认任务清单
        return {
            "user_params": {"destination": "重庆", "days": 3, "budget": "中等",
                            "preferences": ["美食", "打卡"], "special_notes": ""},
            "tasks": [
                {"tool": "weather", "query": "重庆"},
                {"tool": "knowledge", "query": "重庆旅游民俗文化特色"},
                {"tool": "web_search", "query": "重庆最新网红打卡点推荐"},
            ],
            "_parse_error": str(e),
        }
