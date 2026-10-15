"""
交通路况工具：调用高德地图 API
文档：https://lbs.amap.com/api/webservice/guide/api/direction
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

GEO_CODE = "https://restapi.amap.com/v3/geocode/geo"
DRIVING = "https://restapi.amap.com/v3/direction/driving"


def _geo(city: str, keyword: str):
    """地址转经纬度"""
    key = os.getenv("AMAP_API_KEY")
    if not key or key == "your-amap-key":
        return None
    try:
        r = requests.get(GEO_CODE, params={"address": keyword, "city": city, "key": key}, timeout=10)
        data = r.json()
        if data.get("count", "0") != "0":
            return data["geocodes"][0]["location"]
    except Exception as e:
        print(f"[traffic] geo error: {e}")
    return None


def query_traffic(city: str, origin: str, destination: str) -> str:
    """
    查询两点间驾车路线与路况。
    入参：城市名、起点地点、终点地点
    返回：预估耗时、距离、主要路线
    """
    key = os.getenv("AMAP_API_KEY")
    if not key or key == "your-amap-key":
        return f"[路况工具未配置API密钥] 模拟数据：{origin}到{destination}约3.5公里，驾车15分钟，当前路况畅通。"

    o = _geo(city, origin)
    d = _geo(city, destination)
    if not o or not d:
        return f"未能定位：{origin} 或 {destination}"

    try:
        r = requests.get(DRIVING, params={"origin": o, "destination": d, "key": key}, timeout=15)
        data = r.json()
        if data.get("status") != "1":
            return f"路线规划失败：{data.get('info')}"
        path = data["route"]["paths"][0]
        distance_km = int(path["distance"]) / 1000
        duration_min = int(path["duration"]) / 60
        return (
            f"{origin} → {destination}：约{distance_km:.1f}公里，"
            f"驾车{duration_min:.0f}分钟"
        )
    except Exception as e:
        return f"路况查询失败：{e}"
