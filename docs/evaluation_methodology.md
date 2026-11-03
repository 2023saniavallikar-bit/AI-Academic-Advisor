# Evaluation methodology (Phases 4, 5 and 9)

## 1. What is compared

The same test set is run through five versions of the advisor (`eval/run_eval.py`):

| Version | What the model gets | Assignment |
|---|---|---|
| `basic` | The question and a one-line role prompt. No documents, no student data. | Baseline |
| `prompting` | Structured prompt (prompt version B): role, constraints, delimiters, output rules, follow-up questioning. No documents. | A1 Phase 3 |
| `rag` | Prompt + retrieved Handbook/SOP/curriculum passages (Chroma, Gemini embeddings). No student data. | A1 Phase 1 |
| `rag_student` | RAG + the logged-in student's minimised structured profile. | A1 final |
| `agentic` | Intake → structured rules + RAG → deterministic eligibility and credit tools → recommendation → verification. | A2 Phase 9 |

All versions use the same chat model (set `CHAT_MODEL`), temperature 0 where the model allows it, and the same security layer.

## 2. Test set (`eval/test_cases.json`, 42 cases)

Built by `eval/build_test_cases.py`. Every case stores the verified expected outcome and where it comes from.

| Category | Cases | Example |
|---|---|---|
| General information | T01–T12 | Minimum attendance; B+ grade points; summer credit limit |
| Missing information | M01–M06 | Maximum credits per regular semester (not in the documents) |
| Conflicting rules / source-data conflicts | C01–C05 | Late registration: Handbook 2.7 vs SOP; ECON316 lists ECON201 but 2025 offers ECON208 |
| Student eligibility / progress | E01–E13 | STU_017 asks for DATA301 with MATH301 failed |
| Ambiguous / follow-up | A01–A03 | "Can I take Machine Learning next semester?" with no record |
| Unavailable courses | U01–U02 | MATH201 for batch 2026; a Quantum Computing minor |
| Off-topic | O01 | IPL prediction |

Ground truth for student cases is produced by `academic_tools.py` from the synthetic record. `tests/test_ground_truth.py` re-checks every expected decision against the tools, so the test set cannot drift from the data.

## 3. Scoring

Each response is classified into one of four labels:

| Label | Rule |
|---|---|
| **Correct** | All required content groups are present, the expected behaviour is shown, and the eligibility decision (if any) matches. |
| **Partially correct** | At least half of the checks pass and the eligibility decision is not wrong. |
| **Unsupported / hallucinated** | The answer contains a forbidden claim (e.g. invents a credit limit, a fee amount, a professor's name, or says "you are eligible" when the student is not), or mentions a course code that does not exist in the catalogue. |
| **Incorrect** | Everything else. |

Behaviour checks:
- `say_insufficient` needs an explicit statement that the documents do not contain the information.
- `flag_conflict` needs an explicit conflict or confirmation statement.
- `needs_login` / `ask_follow_up` needs a question or a login request.
- `refuse` needs a short redirect to academic topics.

The marker lists are stored in `test_cases.json`.

### Metrics reported (`eval/results/summary.md`)

| Metric | Definition |
|---|---|
| Accuracy | % of cases labelled correct |
| Hallucination rate | % labelled unsupported/hallucinated |
| Correct eligibility decisions | % of cases with an expected decision where the decision matches. The agentic version must state `Decision: X`; other versions are parsed from the text. |
| Source/evidence correctness | % of cases with expected sources where an acceptable source is cited in the answer (or, for the agentic version, is in the evidence it cited) |
| Response time | Median and mean seconds per answer, **excluding** free-tier throttling waits |
| Missing-information handling | % of `say_insufficient` cases handled correctly |
| Conflicting-rule handling | % of `flag_conflict` cases where the conflict is flagged |
| Incorrect recommendations | Count of cases where the student would be told something unsafe: wrong eligibility decision, or a forbidden "you can / you will" claim on progress, graduation or missing-information questions |
| Tokens | Mean total tokens per answer, as reported by the API |

**Correctness vs reliability.** Accuracy and eligibility decisions measure correctness. Hallucination rate, missing-information handling, conflict handling and incorrect recommendations measure reliability: whether the system stays grounded and admits uncertainty.

### Limits of automatic scoring

Keyword and regex scoring is transparent and repeatable, but it can miss a correct answer phrased in an unexpected way, or reward one that mentions the right words for the wrong reason.

To check for this, we hand-review every case where versions disagree and record any overrides in the report. An optional LLM-as-judge was left out to save free-tier quota.

## 4. How to run

```bash
cp .env.example .env   # add GOOGLE_API_KEY
python eval/run_eval.py --modes agentic --limit 5           # smoke test
python eval/run_eval.py --modes basic,prompting,rag,rag_student,agentic
python eval/run_eval.py --report-only                        # rebuild tables
python eval/run_security.py --live                           # Phase 10 with the real model
python eval/run_multimodal.py vision                         # Phase 8 image extraction
```

Results are cached per case in `eval/results/raw_<mode>.jsonl`, so an interrupted run (free-tier quota) resumes where it stopped.

**Free-tier budget.** A full run is about 42 × (1 + 1 + 1 + 1 + ~3.5) ≈ 320 model calls plus embedding calls. With the default 4-second spacing that is roughly 25–40 minutes. If the daily quota runs out, continue the next day; nothing is lost.

## 5. Phase 5 analysis questions the results answer

1. Basic → prompting: do role, constraints and delimiters reduce hallucination (M01–M03, U02) even without documents?
2. Prompting → RAG: how much accuracy comes from grounding (T01–T12)? Note that T04 (grade points) depends on Table 2, which is an image the text index never saw.
3. RAG → RAG + student data: do student-specific cases (E01–E13) become answerable?
4. RAG + student data → agentic: do the deterministic tools fix eligibility, CGPA and credit arithmetic? Does the verifier reduce unsupported claims? What does it cost in calls, latency and tokens?
5. Where every version still fails, and why.
