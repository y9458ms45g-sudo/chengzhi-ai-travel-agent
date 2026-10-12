"""
天气查询工具：调用和风天气 API
支持新版专属API Host
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def _get_base_url():
    host = os.getenv("WEATHER_API_HOST", "")
    if host:
        return f"https://{host}"
    return "https://geoapi.qweather.com"


def _get_location_id(city: str):
    """返回 (location_id, 实际匹配到的城市名)；失败返回 (None, None)"""
    key = os.getenv("WEATHER_API_KEY", "")
    if not key or key == "your-qweather-key":
        return None, None
    try:
        base = _get_base_url()
        r = requests.get(f"{base}/geo/v2/city/lookup", params={"location": city, "key": key}, timeout=10)
        data = r.json()
        if data.get("location"):
            loc = data["location"][0]
            return loc["id"], loc.get("name", city)
    except Exception as e:
        print(f"[weather] geo error: {e}")
    return None, None


def query_weather(city: str) -> str:
    """
    查询某城市未来3天天气。
    入参：城市名，如"重庆"
    """
    key = os.getenv("WEATHER_API_KEY", "")
    if not key or key == "your-qweather-key":
        return f"[天气工具未配置] 模拟数据：{city} 未来3天多云，气温22-30°C，适宜出行。"

    loc_id, resolved = _get_location_id(city)
    if not loc_id:
        return f"未找到城市：{city}"

    try:
        base = _get_base_url()
        # 新版host下天气接口路径
        r = requests.get(f"{base}/v7/weather/3d", params={"location": loc_id, "key": key}, timeout=10)
        data = r.json()
        if data.get("code") != "200":
            return f"天气API返回错误：{data.get('code')}"
        lines = []
        for day in data.get("daily", []):
            lines.append(
                f"{day['fxDate']}: {day['textDay']}，"
                f"气温 {day['tempMin']}~{day['tempMax']}°C，"
                f"降水概率 {day.get('precip', 'N/A')}%，"
                f"风向 {day.get('windDirDay', '')} {day.get('windScaleDay', '')}级"
            )
        # 以实际匹配到的城市名为准，避免张冠李戴
        return f"{resolved}未来3天天气：\n" + "\n".join(lines)
    except Exception as e:
        return f"天气查询失败：{e}"
