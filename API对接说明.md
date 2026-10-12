# 城知文旅 Agent 对外接口说明

## 1. OpenAI 兼容接口（外部应用调用大模型）

**地址**：`POST http://localhost:8000/v1/chat/completions`

跟 OpenAI 官方接口格式完全一样，用 openai-python SDK 直接改 base_url 就能接入：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"
)

resp = client.chat.completions.create(
    model="chengzhi-travel-agent",
    messages=[{"role": "user", "content": "重庆3天怎么玩"}],
    extra_body={"session_id": "user_123"}  # 可选，不传则每次独立
)
print(resp.choices[0].message.content)
```

**请求体**：
```json
{
  "messages": [{"role": "user", "content": "重庆有什么好吃的"}],
  "session_id": "test_001",
  "current_ip": "master"
}
```

**返回**：标准 OpenAI 格式
```json
{
  "id": "chatcmpl-xxx",
  "choices": [{"message": {"role": "assistant", "content": "..."}}]
}
```

---

## 2. Harness 评测接口（批量跑测试用例）

**地址**：`POST http://localhost:8000/harness/eval`

给评测框架用的：批量传测试问题，自动跑 Agent，返回回答和自动评分结果。

```python
import requests

cases = [
    {"id": "t1", "input": "重庆有什么好玩的", "expect": "洪崖洞,火锅"},
    {"id": "t2", "input": "成都熊猫基地怎么去", "expect": "熊猫,地铁"},
]

resp = requests.post("http://localhost:8000/harness/eval", json={
    "cases": cases,
    "reset": True
})
print(resp.json())
```

**请求体**：
```json
{
  "cases": [
    {"id": "用例编号", "input": "用户问题", "expect": "期望出现的关键词，逗号分隔"}
  ],
  "reset": true
}
```

**返回**：
```json
{
  "total": 2,
  "passed": 1,
  "results": [
    {
      "id": "t1",
      "input": "重庆有什么好玩的",
      "output": "Agent 的完整回答",
      "pass": true,
      "reason": "关键词全部命中"
    }
  ]
}
```

---

## 3. 健康检查

`GET http://localhost:8000/api/health` → 返回服务状态和运行时间。
