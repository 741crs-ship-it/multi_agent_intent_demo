"""统一模型调用入口（内网版本）。

注意：
1. 全项目所有模型调用只能通过 call_llm(prompt: str) -> str。
2. 本文件仅使用 Python 标准库 urllib.request。
3. 敏感信息通过环境变量传入，避免写死到代码中。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict


def _get_env(name: str, default: str = "") -> str:
    """读取环境变量并去掉首尾空格。"""
    return os.getenv(name, default).strip()


def _build_payload(prompt: str) -> bytes:
    """构造 chat/completions 请求体。"""
    model = _get_env("LLM_MODEL", "deepseek-v4-flash")
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _extract_text(response_text: str) -> str:
    """从网关响应中提取模型文本。"""
    data = json.loads(response_text)

    # 兼容 OpenAI Chat Completions 风格：
    # {"choices":[{"message":{"role":"assistant","content":"..."}}]}
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
            # 兼容部分网关返回 {"choices":[{"text":"..."}]}
            text = first.get("text")
            if isinstance(text, str):
                return text

    # 常见兜底字段
    for key in ("text", "output", "answer", "content"):
        value = data.get(key)
        if isinstance(value, str):
            return value

    return str(data)


def call_llm(prompt: str) -> str:
    """统一模型调用函数。

    返回约定：
    - 成功：返回模型文本（str）
    - 失败：返回带前缀的错误文本（str），避免主流程中断
    """
    if not isinstance(prompt, str) or not prompt.strip():
        return "[LLM_ERROR] prompt 不能为空"

    llm_url = _get_env("LLM_API_URL")
    llm_token = _get_env("LLM_API_TOKEN")
    timeout_seconds = float(_get_env("LLM_TIMEOUT_SECONDS", "12"))
    max_retries = int(_get_env("LLM_MAX_RETRIES", "2"))

    if not llm_url:
        return "[LLM_ERROR] 未配置 LLM_API_URL"
    if not llm_token:
        return "[LLM_ERROR] 未配置 LLM_API_TOKEN"

    body = _build_payload(prompt)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {llm_token}",
    }
    last_error = "unknown"

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                llm_url,
                data=body,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                response_text = response.read().decode("utf-8", errors="replace")
                return _extract_text(response_text)
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(exc.reason)
            last_error = f"HTTP {exc.code}: {detail}"
        except urllib.error.URLError as exc:
            last_error = f"URL_ERROR: {exc.reason}"
        except json.JSONDecodeError as exc:
            last_error = f"JSON_DECODE_ERROR: {exc}"
        except Exception as exc:
            last_error = f"UNEXPECTED_ERROR: {exc}"

        if attempt < max_retries:
            # 简单指数退避，减少瞬时抖动影响。
            time.sleep(0.5 * (2 ** (attempt - 1)))

    return f"[LLM_ERROR] 调用失败，重试{max_retries}次后仍失败，最后错误：{last_error}"

