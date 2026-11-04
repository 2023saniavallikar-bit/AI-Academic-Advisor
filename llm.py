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
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))  # per model, before falling back
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


THROTTLE_WAITED = [0.0]  # seconds spent waiting for rate limits (subtracted in latency reports)


def _throttle():
    with _lock:
        wait = MIN_SECONDS_BETWEEN_CALLS - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
            THROTTLE_WAITED[0] += wait
        _last_call[0] = time.monotonic()


def _text_of(response) -> str:
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content or ""


PROMPT_CAPTURE: list | None = None  # security audit: set to [] to record every prompt sent


FALLBACK_MODELS = [m.strip() for m in os.getenv(
    "LLM_FALLBACK_MODELS", "gemini-3.5-flash-lite,gemini-3.6-flash,gemini-flash-lite-latest").split(",") if m.strip()]


def _is_overloaded(text: str) -> bool:
    return "503" in text or "unavailable" in text or "overloaded" in text or "high demand" in text


def _is_rate_limited(text: str) -> bool:
    return "429" in text or "quota" in text or "resource_exhausted" in text or "rate limit" in text


def call_llm(system: str, user: str, model: str | None = None, json_mode: bool = False):
    """Call the chosen model; if Google reports it overloaded (503) or out of
    quota (429), retry briefly and then fall back to the next model in
    LLM_FALLBACK_MODELS. usage["model"] records which model answered."""
    model = model or default_model_id()
    if PROMPT_CAPTURE is not None:
        PROMPT_CAPTURE.append(system + "\n" + user)
    if _backend is not None:
        return _backend(system, user, model, json_mode)
    chain = list(dict.fromkeys([model] + FALLBACK_MODELS))
    last_error = None
    for current in chain:
        for attempt in range(MAX_RETRIES):
            _throttle()
            try:
                resp = _client(current).invoke([("system", system), ("human", user)])
                usage = extract_usage(resp) or {}
                usage["model"] = current
                if current != model:
                    usage["fallback_from"] = model
                return _text_of(resp), usage
            except Exception as e:
                last_error = e
                text = str(e).lower()
                if _is_overloaded(text):
                    # overloaded: one short retry, then move on to the next model
                    if attempt == 0:
                        logger.warning("%s overloaded (503); retrying once in 3s", current)
                        time.sleep(3)
                        THROTTLE_WAITED[0] += 3
                        continue
                    logger.warning("%s still overloaded; falling back", current)
                    break
                if _is_rate_limited(text):
                    delay = 10 * (attempt + 1)
                    logger.warning("%s rate-limited (429); retrying in %ss", current, delay)
                    time.sleep(delay)
                    THROTTLE_WAITED[0] += delay
                    continue
                if "not_found" in text or "404" in text:
                    logger.warning("%s not available (404); falling back", current)
                    break
                raise
    raise last_error


def call_llm_with_image(system: str, prompt: str, image_bytes: bytes, mime: str, model: str | None = None):
    """Vision call (transcript images). Returns (text, usage).

    Model: the caller's choice, else VISION_MODEL, else CHAT_MODEL. An empty
    VISION_MODEL= line in .env counts as not set. Busy (503) or out-of-quota
    (429) models fall back along LLM_FALLBACK_MODELS, as for chat."""
    import base64
    model = model or (os.getenv("VISION_MODEL") or "").strip() or default_model_id()
    if _backend is not None:
        return _backend(system, prompt + "\n[IMAGE ATTACHED]", model, True)
    from langchain_core.messages import HumanMessage, SystemMessage
    b64 = base64.b64encode(image_bytes).decode()
    msg = HumanMessage(content=[{"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": f"data:{mime};base64,{b64}"}])
    last_error = None
    for current in list(dict.fromkeys([model] + FALLBACK_MODELS)):
        for attempt in range(MAX_RETRIES):
            _throttle()
            try:
                resp = _client(current).invoke([SystemMessage(content=system), msg])
                usage = extract_usage(resp) or {}
                usage["model"] = current
                if current != model:
                    usage["fallback_from"] = model
                return _text_of(resp), usage
            except Exception as e:
                last_error = e
                text = str(e).lower()
                if _is_overloaded(text):
                    if attempt == 0:
                        time.sleep(3)
                        continue
                    break
                if _is_rate_limited(text):
                    time.sleep(10 * (attempt + 1))
                    continue
                if "not_found" in text or "404" in text:
                    break
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
    if usage.get("model"):
        models = total.setdefault("models_used", [])
        if usage["model"] not in models:
            models.append(usage["model"])
    if usage.get("fallback_from"):
        total["fallback_from"] = usage["fallback_from"]
    return total
