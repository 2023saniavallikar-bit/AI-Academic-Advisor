import llm


class Resp:
    content = "ok"
    usage_metadata = {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}


def test_falls_back_when_model_overloaded(monkeypatch):
    calls = []

    class Client:
        def __init__(self, m): self.m = m
        def invoke(self, msgs):
            calls.append(self.m)
            if self.m == "busy-model":
                raise RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand. generateContent")
            return Resp()

    llm.set_backend(None)
    monkeypatch.setattr(llm, "_client", lambda m: Client(m))
    monkeypatch.setattr(llm, "FALLBACK_MODELS", ["backup-model"])
    monkeypatch.setattr(llm, "MIN_SECONDS_BETWEEN_CALLS", 0)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    text, usage = llm.call_llm("sys", "hi", model="busy-model")
    assert text == "ok" and usage["model"] == "backup-model" and usage["fallback_from"] == "busy-model"
    assert calls == ["busy-model", "busy-model", "backup-model"]


def test_other_errors_are_not_swallowed(monkeypatch):
    class Client:
        def __init__(self, m): pass
        def invoke(self, msgs): raise ValueError("400 INVALID_ARGUMENT bad request to generateContent")
    llm.set_backend(None)
    monkeypatch.setattr(llm, "_client", lambda m: Client(m))
    monkeypatch.setattr(llm, "MIN_SECONDS_BETWEEN_CALLS", 0)
    import pytest
    with pytest.raises(ValueError):
        llm.call_llm("sys", "hi", model="x")
