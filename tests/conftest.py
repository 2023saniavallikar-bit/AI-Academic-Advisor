import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pytest
import llm


def fake_backend(system, user, model, json_mode):
    if "Intake agent" in system:
        msg = user.split("Message:")[-1]
        codes = re.findall(r"[A-Z]{4}\d{3}", msg.upper())
        off = "cricket" in msg.lower() or "poem" in msg.lower()
        personal = bool(re.search(r"\b(i|my|me)\b", msg.lower())) and bool(codes or "credit" in msg.lower() or "graduat" in msg.lower())
        intent = "off_topic" if off else ("eligibility" if codes and personal else "course_info" if codes else
                  "graduation" if "graduat" in msg.lower() else "regulation")
        return json.dumps({"intent": intent, "course_codes": codes, "needs_student_record": personal,
                           "off_topic": off, "missing_information": [], "follow_up_question": None}), None
    if "Recommendation agent" in system:
        m = re.search(r'"decision": "([A-Z_]+)"', user)
        head = f"**Decision: {m.group(1).replace('_', ' ')}**\n" if m else ""
        return head + "Based on the records [E1].", None
    if "Verification agent" in system:
        return '{"supported": true, "contradicts_tools": false}', None
    return "ok", None


@pytest.fixture(autouse=True)
def stub_llm():
    llm.set_backend(fake_backend)
    yield
    llm.set_backend(None)


@pytest.fixture
def students():
    return {s["student_id"]: s for s in json.loads((ROOT / "synthetic_students.json").read_text())}
