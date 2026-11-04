# Evaluation results (live run, 4 November 2026)

- **Model:** `gemini-3.5-flash-lite` (Gemini API free tier) for all versions.
- **Embeddings:** `gemini-embedding-001`.
- **Test set:** 42 cases (`eval/test_cases.json`).
- **Scoring:** rules in `docs/evaluation_methodology.md`.
- **Raw outputs:** `eval/results/raw_<mode>.jsonl`. Tables are regenerated with `python eval/run_eval.py --report-only`.

## 1. Main comparison (Phase 4 / 5 / 9)

| Metric | Basic LLM | Structured prompt | RAG | RAG + student data (A1) | Agentic (A2) |
|---|---|---|---|---|---|
| Correct | 16.7% | 7.1% | 42.9% | 61.9% | **81.0%** |
| Partially correct | 38.1% | 52.4% | 26.2% | 19.0% | 16.7% |
| Unsupported / hallucinated | 7.1% | 0.0% | 2.4% | 2.4% | **0.0%** |
| Incorrect | 38.1% | 40.5% | 28.6% | 16.7% | 2.4% |
| Correct eligibility decisions (11 cases) | 9.1% | 0.0% | 9.1% | 54.5% | **100%** |
| Source/evidence correct (14 cases) | 35.7% | 85.7%¹ | 92.9% | 92.9% | 100% |
| Missing information handled (7 cases) | 14.3% | 0.0% | 71.4% | 71.4% | 85.7% |
| Conflicts flagged (5 cases) | 60.0% | 0.0% | 20.0% | 20.0% | 80.0% |
| Incorrect recommendations (count) | 11 | 11 | 10 | 5 | **0** |
| Median response time (s)² | 1.1 | 0.8 | 1.4 | 1.7 | 3.3 (see §3) |
| Mean tokens per answer | 236 | 1,240 | 2,288 | 3,632 | 5,054 |

¹ Inflated by the keyword check. 37 of 42 structured-prompt answers ask for a Student ID with phrases like "which university academic *regulations* apply to you?", and that wording matches the source keywords although nothing is cited. Source correctness must be read together with accuracy.
² Excludes free-tier throttling waits.

## 2. Correct answers by category

| Category | n | Basic LLM | Structured prompt | RAG | RAG + student data | Agentic |
|---|---|---|---|---|---|---|
| General information (T01–T12) | 12 | 8% | 0% | 83% | 83% | 92% |
| Missing information (M01–M06) | 6 | 17% | 0% | 50% | 50% | 83% |
| Conflicting rules (C01–C05) | 5 | 20% | 0% | 20% | 20% | 80% |
| Student-specific (E01–E13) | 13 | 8% | 0% | 8% | 62% | 77% |
| Ambiguous / unavailable / off-topic | 6 | 50% | 50% | 50% | 67% | 67% |

## 3. Response time and cost

| | RAG | RAG + student data | Agentic |
|---|---|---|---|
| Median latency (s) | 1.4 | 1.7 | 3.3 |
| Model calls per answer | 1 | 1 | 3 (median; up to 5 with a repair) |
| Mean tokens per answer | 2,288 | 3,632 | 5,054 |

- **Agentic latency:** median over the 33 answers that went through the full pipeline in the first agentic run (p90 4.0 s). That run used the API one request at a time.
- **Not representative:** the final agentic re-run shared the API with the security and vision runs and hit Google 503/429 errors, so its 14.4 s median is inflated.
- **Abandoned:** a separate 10-case timing sample was stopped by free-tier quota limits.

## 4. What each stage added (Phase 5)

- **Basic → structured prompt.** Hallucination fell from 7.1% to 0%: the prompt's constraints stopped it inventing course codes such as COMP101, STAT101 and MATH101. But accuracy did not improve. Without documents, the structured prompt asks for a Student ID in 37 of 42 answers, even for general rule questions. Prompting makes the model *safer*, not *more knowledgeable*.
- **Structured prompt → RAG.** This is the largest jump on rule questions: general information went from 0% to 83% and missing-information handling from 0% to 71%. Grounding is what makes the answers correct.
- **RAG → RAG + student data.** Student-specific accuracy went from 8% to 62% and correct eligibility decisions from 9% to 55%. Without a record, RAG cannot decide eligibility at all.
- **RAG + student data → agentic.** Eligibility decisions went from 55% to 100%, conflicts flagged from 20% to 80%, and incorrect recommendations from 5 to 0. The gains come from the deterministic tools (prerequisites, credits, CGPA) and from structured rules that surface source-data conflicts. Plain RAG cannot see these conflicts, because a conflict spans two documents or two rows.

## 5. Where systems still fail

- **T04, grade points.** RAG and RAG + student data say a **B+ carries 8 grade points** and cite "Table 2". The handbook value is 7. Table 2 is an *image* in the PDF, so text extraction never indexed it, and the model filled the gap with a plausible wrong number and a real-looking citation. The agentic version answers correctly only because we transcribed the table into `data/regulations.json`. This is the clearest example of the multimodal ingestion gap (Phase 8).
- **C05, ambiguous course title.** The agentic answer reports both titles but does not say they conflict. Its 80% conflict score is partly the structured rules, not the model reasoning about the conflict.
- **M06, will DATA406 run?** No version clearly says that offering depends on the 10-student minimum *and* that the actual timetable is not in the documents. Best result: partial (agentic).
- **E04, E10, E12 (partial).** The agentic answers are right on the decision but miss part of the expected content, e.g. make-up exam options or the remaining-credits figure.
- **A02 (partial).** Agentic lists the specialization options but does not ask the student about their interests first.
- **Cost.** Agentic uses about 1.4× the tokens of RAG + student data and about 3 model calls per answer. That uses up the free-tier daily quota roughly three times faster.

## 6. Problems the live evaluation found in our own system (fixed and re-measured)

Reported for transparency; the first-run outputs are kept as `raw_agentic_v1.jsonl` and `summary_v1.md`.

| Found | Effect in first run | Fix |
|---|---|---|
| The Intake step treated general rule questions phrased with "I" ("What CGPA do I need…") as personal and asked an anonymous user to log in | Agentic scored 66.7% and failed 5 general and conflict cases | Router field `answerable_without_record`, plus a code rule: an anonymous rule question with no course code gets the general answer |
| Eligibility "timing note" was written as if it were a second barrier ("scheduled for semester 5 rather than 6") | Confusing answers | Neutral wording, shown only when the student names a semester |
| Registration forms were compared with past history, so every current course was flagged | False "not in the official record" warnings | Forms are compared with the current registration |

## 7. Manual review of automatic labels

Every "unsupported/hallucinated" label was checked by hand. These scoring errors were corrected in the scorer and **all versions were rescored with the same rules**:

| Case(s) | Wrong automatic label | Correction |
|---|---|---|
| M03 (agentic, prompting) | "professor names" matched the fake-professor pattern | Pattern now requires `prof`/`dr` followed by a name |
| E02, E07, E10, E11 (RAG versions, basic) | "To determine **whether you are eligible**…" matched "you are eligible" | Patterns ignore "whether/if …" |
| E03, A01, M03 (RAG versions) | DATA206 counted as an invented code | DATA206 appears as a listed prerequisite in the source data, so it counts as known |
| T04 (agentic) | The list "B+, B, … carrying 10, 9, 8, 7" matched "B+ = 8" | Pattern now requires "B+ carries/is/= 8" |
| Free-text decisions | "Please confirm with your Faculty Advisor" was read as NEEDS REVIEW before "not eligible" | Explicit decisions are matched first |

Remaining limitation: the keyword scorer can still under-credit correct answers worded in an unexpected way. Partially correct answers should be read alongside the raw outputs.

## 8. Security and multimodal (summary; details in the Phase 8 and Phase 10 docs)

- **Security, live model:** 8/20 attacks succeeded with safeguards OFF, 0/20 with safeguards ON. Offline exposure measurement: 14/20 → 0/20.
- **Vision, 17 synthetic documents:**
  - course-code recall 98.5%, precision 96.9%, grade accuracy 97.9%
  - grades on phone photos only 88.2%, and every misread grade was flagged as a discrepancy
  - all four problem documents caught: tampered, injection, PII, wrong owner
- **Voice:** to be measured by the team (`eval/voice_prompts.csv`).
