"""
LLM 客户端：统一封装 OpenAI 兼容接口（DeepSeek/通义/智谱等都支持）
带指数退避重试，应对限流/超时/5xx。
"""
import os
import json
import time
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agent.llm")

_client = None

# 可重试的临时性异常
_RETRYABLE_STATUS = (429, 500, 502, 503, 504)
MAX_RETRIES = 3
BASE_WAIT = 1.5  # 秒，指数退避：1.5 / 3 / 6


def _is_retryable(exc) -> bool:
    """判断是否为瞬时错误，值得重试。"""
    name = type(exc).__name__
    if name in ("RateLimitError", "APITimeoutError", "APIConnectionError",
                "InternalServerError", "APIError", "Timeout"):
        return True
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if status in _RETRYABLE_STATUS:
        return True
    msg = str(exc)
    return "timed out" in msg.lower() or "connection" in msg.lower() or "429" in msg


def _with_retry(fn, tag="llm"):
    """对一次 LLM 调用做指数退避重试。"""
    last = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt >= MAX_RETRIES or not _is_retryable(e):
                raise
            wait = BASE_WAIT * (2 ** attempt)
            logger.warning(json.dumps({
                "ev": "llm_retry", "tag": tag, "attempt": attempt + 1,
                "wait_s": wait, "err": str(e)[:160],
            }, ensure_ascii=False))
            time.sleep(wait)
    raise last


def _log_usage(tag, resp):
    """结构化记录 token 用量（一行 JSON）。"""
    try:
        u = getattr(resp, "usage", None)
        if u is not None:
            logger.info(json.dumps({
                "ev": "llm_usage", "call": tag,
                "prompt_tokens": getattr(u, "prompt_tokens", None),
                "completion_tokens": getattr(u, "completion_tokens", None),
                "total_tokens": getattr(u, "total_tokens", None),
            }, ensure_ascii=False))
    except Exception:
        pass

def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("LLM_API_KEY", "sk-placeholder"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
            timeout=60.0,
        )
    return _client

def chat(messages, temperature=0.3, max_tokens=4096, response_format=None):
    """普通对话补全（带重试）"""
    kwargs = {
        "model": os.getenv("LLM_MODEL", "deepseek-chat"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}
    def _call():
        resp = get_client().chat.completions.create(**kwargs)
        _log_usage("chat", resp)
        return resp.choices[0].message.content
    return _with_retry(_call, "chat")

def chat_with_tools(messages, tools, temperature=0.1):
    """带 Function Calling 的对话，返回 message 对象（带重试）"""
    def _call():
        resp = get_client().chat.completions.create(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            messages=messages,
            tools=tools,
            temperature=temperature,
            tool_choice="auto",
        )
        _log_usage("chat_with_tools", resp)
        return resp.choices[0].message
    return _with_retry(_call, "chat_with_tools")


def chat_stream(messages, temperature=0.5, max_tokens=4096):
    """流式对话，yield 每个文本片段。连接建立阶段失败会重试，开始吐字后不中断。"""
    def _build():
        return get_client().chat.completions.create(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
    stream = _with_retry(_build, "chat_stream_open")
    final_usage = None
    for chunk in stream:
        if getattr(chunk, "usage", None):
            final_usage = chunk.usage
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
    if final_usage:
        logger.info(json.dumps({
            "ev": "llm_usage", "call": "chat_stream",
            "prompt_tokens": getattr(final_usage, "prompt_tokens", None),
            "completion_tokens": getattr(final_usage, "completion_tokens", None),
            "total_tokens": getattr(final_usage, "total_tokens", None),
        }, ensure_ascii=False))

def chat_flash(messages, temperature=0.3, max_tokens=4096, response_format=None):
    """DeepSeek V4.1 Flash 快速接口（轻量/低成本场景用）。
    模型名通过环境变量 DEEPSEEK_FLASH_MODEL 配置，默认 deepseek-v4.1-flash。"""
    model = os.getenv("DEEPSEEK_FLASH_MODEL", "deepseek-v4.1-flash")
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}
    def _call():
        resp = get_client().chat.completions.create(**kwargs)
        _log_usage("chat_flash", resp)
        return resp.choices[0].message.content
    return _with_retry(_call, "chat_flash")


def chat_stream_flash(messages, temperature=0.5, max_tokens=4096):
    """DeepSeek V4.1 Flash 流式接口。"""
    model = os.getenv("DEEPSEEK_FLASH_MODEL", "deepseek-v4.1-flash")
    def _build():
        return get_client().chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
    stream = _with_retry(_build, "chat_stream_flash_open")
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def embed(texts):
    """调用 Embedding 接口，返回向量列表"""
    from openai import OpenAI as _OpenAI
    client = _OpenAI(
        api_key=os.getenv("EMBEDDING_API_KEY", os.getenv("LLM_API_KEY", "")),
        base_url=os.getenv("EMBEDDING_BASE_URL", os.getenv("LLM_BASE_URL", "")),
    )
    resp = client.embeddings.create(
        model=os.getenv("EMBEDDING_MODEL", "embedding-3"),
        input=texts,
    )
    return [d.embedding for d in resp.data]
