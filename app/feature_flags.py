"""
灰度发布 Feature Flag
=====================
按 session_id hash 分流，不依赖外部配置中心。
生产环境可换成 etcd / 飞书多维表格配置。

用法：
    from app.feature_flags import is_enabled
    if is_enabled(session_id, "new_planner_prompt", rollout_pct=10):
        # 只对 10% 用户走新逻辑
"""
import hashlib


def is_enabled(session_id: str, flag_name: str, rollout_pct: int = 0) -> bool:
    """
    根据 session_id 决定是否命中灰度。
    同一 session 永远命中同一组 flag（不闪烁）。
    rollout_pct: 0=全关，100=全开
    """
    if rollout_pct <= 0:
        return False
    if rollout_pct >= 100:
        return True
    # hash(session_id + flag_name) % 100 < rollout_pct
    h = hashlib.md5(f"{session_id}:{flag_name}".encode()).hexdigest()
    bucket = int(h[:8], 16) % 100
    return bucket < rollout_pct


# 当前在灰度的功能列表（这里集中管理，方便面试讲）
FLAGS = {
    # "new_planner_prompt": 10,   # 新 Planner prompt 灰度 10%
    # "async_pref_extract": 100,  # 异步偏好抽取，已全量
    # "embedding_rag": 5,         # embedding RAG 灰度 5%
}


def get_flags_for(session_id: str) -> dict:
    """返回该 session 命中的所有 flag，可注入 system prompt 做 A/B。"""
    return {name: is_enabled(session_id, name, pct)
            for name, pct in FLAGS.items()}
