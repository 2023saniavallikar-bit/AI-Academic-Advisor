"""One small wrapper around the chat model, shared by the agents and the
evaluation, with free-tier friendly throttling and retry.

``call_llm(system, user, model)`` returns (text, usage). Tests and offline
runs can swap the backend with ``set_backend(fn)``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time

from models import default_model_id, extract_usage, get_spec

logger = logging.getLogger(__name__)

# Free tier: requests per minute are low, so space calls out process-wide.
MIN_SECONDS_BETWEEN_CALLS = float(os.getenv("LLM_MIN_INTERVAL_SECONDS", "4"))
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
_lock = threading.Lock()
_last_call = [0.0]
_clients: dict[str, object] = {}
_backend = None


def set_backend(fn):
    """fn(system, user, model, json_mode) -> (text, usage). None restores Gemini."""
    global _backend
    _backend = fn


def _client(model_id: str):
    if model_id not in _clients:
        from langchain_google_genai import ChatGoogleGenerativeAI
        spec = get_spec(model_id)
        kwargs = {"model": model_id, "retries": 1}
        if spec.temperature is not None:
            kwargs["temperature"] = spec.temperature
        _clients[model_id] = ChatGoogleGenerativeAI(**kwargs)
    return _clients[model_id]


def _throttle():
    with _lock:
        wait = MIN_SECONDS_BETWEEN_CALLS - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()


def _text_of(response) -> str:
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content or ""


def call_llm(system: str, user: str, model: str | None = None, json_mode: bool = False):
    model = model or default_model_id()
    if _backend is not None:
        return _backend(system, user, model, json_mode)
    last_error = None
    for attempt in range(MAX_RETRIES):
        _throttle()
        try:
            resp = _client(model).invoke([("system", system), ("human", user)])
            return _text_of(resp), extract_usage(resp)
        except Exception as e:  # rate limit / transient
            last_error = e
            text = str(e).lower()
            if "429" in text or "quota" in text or "resource" in text or "503" in text:
                delay = 15 * (attempt + 1)
                logger.warning("LLM rate-limited (%s); retrying in %ss", model, delay)
                time.sleep(delay)
                continue
            raise
    raise last_error


def call_llm_with_image(system: str, prompt: str, image_bytes: bytes, mime: str, model: str | None = None):
    """Vision call (transcript images). Returns (text, usage)."""
    import base64
    model = model or os.getenv("VISION_MODEL", default_model_id())
    if _backend is not None:
        return _backend(system, prompt + "\n[IMAGE ATTACHED]", model, True)
    from langchain_core.messages import HumanMessage, SystemMessage
    b64 = base64.b64encode(image_bytes).decode()
    msg = HumanMessage(content=[{"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": f"data:{mime};base64,{b64}"}])
    last_error = None
    for attempt in range(MAX_RETRIES):
        _throttle()
        try:
            resp = _client(model).invoke([SystemMessage(content=system), msg])
            return _text_of(resp), extract_usage(resp)
        except Exception as e:
            last_error = e
            if "429" in str(e) or "quota" in str(e).lower():
                time.sleep(15 * (attempt + 1))
                continue
            raise
    raise last_error


def parse_json(text: str) -> dict | None:
    """Best-effort JSON object from a model reply (handles ```json fences)."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def add_usage(total: dict | None, usage: dict | None) -> dict | None:
    if not usage:
        return total
    total = dict(total or {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0})
    for k in ("input_tokens", "output_tokens", "total_tokens"):
        total[k] = total.get(k, 0) + (usage.get(k) or 0)
    total["calls"] = total.get("calls", 0) + 1
    return total
