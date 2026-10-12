"""
Reflector：反思校验器
检查攻略是否有事实错误、时间冲突、逻辑问题
"""
from app.llm import chat


REFLECT_SYSTEM = """你是旅游攻略审核员，只抓「硬错误」，不吹毛求疵。

只检查这几类硬问题：
1. 时间冲突：同日两个地点距离过远、时间明显冲突
2. 天气矛盾：明显的户外行程排在明确降雨且无备选
3. 事实错误：把景点/地名/城市张冠李戴（如把沈阳故宫说成北京故宫）
4. 明显逻辑错误：交通方式自相矛盾

【不要当成问题的情况】
- 用户没给日期/人数/预算 —— 这不算错误，不要报
- 措辞、语气、排版可以更好 —— 不要报
- 行程"不够完美" —— 不要报

输出JSON：
{
  "issues": ["具体硬问题1", ...],
  "has_problem": true/false,
  "corrected_draft": ""
}

规则：
- 没有硬问题 → issues 为空，has_problem=false，corrected_draft 为空字符串
- 有硬问题 → has_problem=true，issues 列具体问题；corrected_draft 必须是**直接可用的完整旅游回答**（像正常给游客的攻略/路线），
  绝对不要写"由于原文缺少XX""建议补充""审核如下"这类元话术。
只输出JSON。"""


def reflect(draft: str) -> dict:
    """审核攻略初稿，返回问题列表和修正版本"""
    try:
        result = chat(
            [
                {"role": "system", "content": REFLECT_SYSTEM},
                {"role": "user", "content": f"请审核以下攻略：\n\n{draft}"},
            ],
            temperature=0.1,
            response_format="json",
            max_tokens=4096,
        )
        import json
        return json.loads(result)
    except Exception as e:
        return {"issues": [], "has_problem": False, "corrected_draft": draft, "error": str(e)}
