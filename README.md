# Vidyashilp Guide: AI Academic Advisor (DATA308, Assignments 1 and 2)

This is a RAG-based academic advisor for Vidyashilp University. Assignment 2 extends it with:
- an agentic pipeline backed by deterministic rule checks,
- multimodal input and output (voice, transcript images, charts),
- a privacy and security layer,
- a full synthetic data set with an evaluation suite.

> All student data in this repository is **synthetic**. Answers are AI-generated guidance, not official university decisions.

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set GOOGLE_API_KEY (free tier works)
python app.py                   # http://localhost:5000
```

Demo accounts: `STU_001` … `STU_050`. The PIN is the last three digits followed by `9`, so `STU_016` uses `0169`. Faculty advisor: `ADVISOR_01` / `2468` (sees STU_001–STU_012).

Good demo students:

| Student | Scenario |
|---|---|
| STU_016 | Ready for ML, conditional for Deep Learning |
| STU_017 | Failed MATH301, so blocked from DATA301 |
| STU_010 | ECON316 prerequisite conflict |
| STU_022 | CGPA below 5.00, so Year 3 progression risk |
| STU_004 | Registration hold (privacy) |
| STU_043 | Batch with no curriculum data |

## What is where

| Path | Purpose |
|---|---|
| `app.py` | Flask app: chat (agentic / RAG), login, transcript upload, charts |
| `agents.py` | **Phase 9** pipeline: Intake → Regulation Retrieval → Eligibility → Credits → Recommendation → Verification |
| `academic_tools.py` | Deterministic tools: catalogue parsing, prerequisites, eligibility, credits per basket, CGPA, progression, graduation |
| `data/regulations.json` | Handbook/SOP rules as structured data with clause and page numbers |
| `advisor.py` | Assignment 1 RAG advisor (kept for comparison) |
| `multimodal.py` | **Phase 8**: transcript image extraction plus checks; SVG prerequisite and progress charts |
| `static/ui.js` | UI layer: sign-in dialog, settings sheet, answer cards (decision badges, citations, sources & steps), voice in/out, upload (drag-and-drop), charts, toasts. See `docs/frontend_audit.md` |
| `security.py` | **Phase 10** safeguards S1–S6; `SECURITY_MODE=off` reproduces Assignment 1 for the audit |
| `scripts/generate_students.py` | Synthetic student database v2 (seeded, catalogue-consistent, validated) |
| `scripts/generate_records.py` | Synthetic transcripts, registration and add/drop forms, phone-photo and problem documents |
| `eval/` | Test set (42 cases), evaluation runner (5 versions), security suite (21 attacks), multimodal evaluation |
| `docs/` | Phase 8–11 write-ups, evaluation methodology, report outline |
| `tests/` | Offline tests (stub model): `python -m pytest tests` |

## Rebuilding data

```bash
python scripts/generate_students.py   # writes synthetic_students.json + data/demo_users.json, then validates
python scripts/generate_records.py    # writes data/synthetic_records/
python eval/build_test_cases.py       # writes eval/test_cases.json
```

## Deploy (Render, Docker)

The Dockerfile copies the app, the pre-built Chroma index and `data/regulations.json` / `data/demo_users.json`. Set these environment variables:
- `GOOGLE_API_KEY`
- `FLASK_SECRET_KEY`
- `SESSION_COOKIE_SECURE=true`
- optionally `CHAT_MODEL` and `DEFAULT_MODE=agentic`

The free Render plan sleeps when idle, so open the site a minute before a demo.
