"""
预算计算工具：按城市/人数/天数/档次，输出门票/餐饮/住宿/交通明细。
纯本地计算，不调外部 API。价格为经验区间，标注"仅供参考，以实际为准"。
"""

# 城市消费档：1=低 2=中 3=高
_CITY_TIER = {
    "北京": 3, "上海": 3, "广州": 3, "深圳": 3, "杭州": 3, "苏州": 3,
    "厦门": 2, "南京": 2, "成都": 2, "重庆": 2, "西安": 2, "武汉": 2,
    "长沙": 2, "青岛": 2, "天津": 2, "大连": 2, "丽江": 2, "三亚": 3,
    "哈尔滨": 2, "洛阳": 1, "开封": 1, "乐山": 1, "宜宾": 1, "绵阳": 1,
    "南充": 1, "自贡": 1, "眉山": 1, "敦煌": 2, "拉萨": 2,
}

# 每档人均/天（元）：餐饮、住宿、门票、市内交通
_PER_DAY = {
    1: {"food": 60, "hotel": 120, "ticket": 60, "local_traffic": 25},
    2: {"food": 100, "hotel": 220, "ticket": 100, "local_traffic": 40},
    3: {"food": 160, "hotel": 380, "ticket": 150, "local_traffic": 60},
}
_LEVEL_NAME = {1: "经济", 2: "舒适", 3: "品质"}


def calc_budget(city: str, people: int = 2, days: int = 2, level: str = "舒适") -> dict:
    """返回预算明细 dict。"""
    city = (city or "").strip()
    try:
        people = max(1, int(people))
        days = max(1, int(days))
    except Exception:
        people, days = 2, 2
    lv = {"经济": 1, "舒适": 2, "品质": 3}.get(level, 2)
    tier = _CITY_TIER.get(city, 2)
    # 城市档与消费档取较高者
    eff = max(lv, tier)
    base = _PER_DAY[eff]

    food = round(base["food"] * days)
    hotel = round(base["hotel"] * (days - 1) / (1 if people == 1 else min(people, 4)))
    # 多人拼房：按每2人一间粗算
    hotel = round(base["hotel"] * (days - 1) * max(1, people // 2) / people) if people > 1 else round(base["hotel"] * (days - 1))
    ticket = round(base["ticket"] * days)
    local_traffic = round(base["local_traffic"] * days)
    per_person = food + hotel + ticket + local_traffic
    total = per_person * people

    return {
        "city": city,
        "people": people,
        "days": days,
        "level": _LEVEL_NAME[eff],
        "per_person_breakdown": {
            "餐饮": food, "住宿": hotel, "门票": ticket, "市内交通": local_traffic,
        },
        "per_person_total": per_person,
        "group_total": total,
        "note": "以上为按城市消费档估算的经验区间，不含大交通（往返机票/高铁）；实际以预订时为准。",
    }


def query_budget(city: str, people: int = 2, days: int = 2, level: str = "舒适") -> str:
    """工具入口（给 LLM 调用）"""
    r = calc_budget(city, people, days, level)
    lines = [
        f"{r['city']} {r['days']}天{people}人（{r['level']}档）预算估算：",
    ]
    for k, v in r["per_person_breakdown"].items():
        lines.append(f"  {k}：人均约 {v} 元")
    lines.append(f"  人均合计：约 {r['per_person_total']} 元")
    lines.append(f"  {r['people']}人总计：约 {r['group_total']} 元")
    lines.append(r["note"])
    return "\n".join(lines)
