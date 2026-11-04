import os
os.environ.setdefault("GOOGLE_API_KEY", "dummy-key-for-tests")
os.environ["CHAT_RATE_LIMIT"] = "1000"
import pytest


@pytest.fixture(scope="module")
def appmod(tmp_path_factory):
    os.environ["CHAT_HISTORY_DB_PATH"] = str(tmp_path_factory.mktemp("db") / "m.sqlite3")
    import app as appmod
    appmod.agentic.vectorstore = None
    return appmod


def test_agentic_uses_selected_model(appmod, monkeypatch):
    import llm
    seen = []
    def backend(system, user, model, json_mode):
        seen.append(model)
        return ("{}" if json_mode else "Based on the records [E1]."), {"total_tokens": 1, "model": model}
    llm.set_backend(backend)
    c = appmod.app.test_client()
    r = c.post("/api/chat", json={"message": "What is the minimum attendance?", "mode": "agentic",
                                  "model": "gemini-3.6-flash"}).get_json()
    assert seen and set(seen) == {"gemini-3.6-flash"}
    assert r["meta"]["model"] == "gemini-3.6-flash" and not r["meta"]["fallback_from"]


def test_rag_uses_selected_model_and_falls_back(appmod, monkeypatch):
    from langchain_google_genai.chat_models import GoogleRateLimitError
    used = []
    def fake_answer(message, model=None, **kw):
        used.append(model)
        if model == "gemini-3.5-flash-lite":
            raise GoogleRateLimitError("429 RESOURCE_EXHAUSTED")
        return {"answer": "ok", "student_id": None, "model": model, "period": {}, "usage": None, "cost": None}
    monkeypatch.setattr(appmod.advisor, "answer_question", fake_answer)
    c = appmod.app.test_client()
    r = c.post("/api/chat", json={"message": "What is the minimum attendance?", "mode": "rag",
                                  "model": "gemini-3.8-flash"}).get_json()
    assert used == ["gemini-3.8-flash"] and r["meta"]["model"] == "gemini-3.8-flash"
    used.clear()
    r = c.post("/api/chat", json={"message": "What is the minimum attendance?", "mode": "rag",
                                  "model": "gemini-3.5-flash-lite"}).get_json()
    assert used[0] == "gemini-3.5-flash-lite" and r["meta"]["model"] != "gemini-3.5-flash-lite"
    assert r["meta"]["fallback_from"] == "Gemini 3.5 Flash-Lite"
