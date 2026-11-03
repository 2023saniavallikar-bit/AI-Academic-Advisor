# Assignment 2: report outline, slide plan and demo script

## A. Ten-page report (suggested page budget)

1. **Introduction and recap of Assignment 1** (0.5 page). Goal, data, the RAG system and its Assignment 1 results.
2. **Synthetic data created** (1 page)
   - Student DB v2: 50 profiles generated from the real curriculum, seeded and validated, with scenario tags and a restricted block.
   - Records: 17 documents, including phone-photo, tampered, injection, PII and wrong-owner files.
   - Multimodal inputs: transcript images and 15 voice prompts.
   - Responsible-data choices: no names, SYN- references, watermark, PII scan in the validator.
   - Data problems the generator found in the university sheets (same-semester prerequisites, missing prerequisite codes, renamed minor courses). Source: `docs/phase9_agentic.md`.
3. **System architecture** (1 page). One diagram: UI (text, voice, upload, charts) → security layer → RAG or agentic pipeline → tools, rules and vector store → verifier → output filter.
4. **Phase 8: multimodal** (1.5 pages). Modalities, models and tools table, evaluation numbers (vision recall/precision, voice WER), limitations, what stays with humans. Includes the finding that the grade table is an image.
5. **Phase 9: agentic** (1.5 pages). Agents, code vs LLM split, the trace, comparison table against RAG, and when the extra complexity is or isn't worth it.
6. **Evaluation** (1.5 pages). Methodology (`docs/evaluation_methodology.md`), main results table across the five versions, per-category analysis, failure examples.
7. **Phase 10: privacy and security** (1.5 pages). Data inventory, attack table (OFF vs ON), safeguards, residual risks.
8. **Phase 11: copyright and legal** (1 page). Condensed from `docs/phase11_copyright_legal.md`: inventory table plus the practices checklist.
9. **Limitations and conclusions** (0.5 page).

Appendices (not counted): prompts, the full test set, the per-case table.

## B. Slides (about 14)

| # | Slide |
|---|---|
| 1 | Title: "Multimodal, secure, responsible AI Academic Advisor" |
| 2 | Assignment 1 recap: the RAG system and its weak spots (arithmetic, eligibility, privacy) |
| 3 | What we built in Assignment 2: four pillars |
| 4 | Synthetic data: student DB v2, records, phone photos, problem documents |
| 5 | Architecture diagram |
| 6 | Agentic pipeline and live trace screenshot |
| 7 | Results: five versions × metrics (bar chart) |
| 8 | Where agentic helps or doesn't (calls, latency, accuracy) |
| 9 | Multimodal: voice, transcript image, charts, with quality numbers |
| 10 | Grade table image finding and data conflicts found |
| 11 | Security: 20 attacks, OFF vs ON |
| 12 | Copyright and legal: the four outputs, risks and practices |
| 13 | What stays with humans |
| 14 | Limitations and next steps |

## C. Live demo script (about 7 minutes)

1. **Normal** (log in as STU_016): "Can I take Deep Learning (DATA302) next semester?" The answer is **CONDITIONAL**. Open the trace, then click "DATA302 prerequisites" to show the chart.
2. **Voice**: press 🎤 and say "What is the minimum attendance for the end term exam?" Then press 🔊 Listen on the answer.
3. **Blocked student** (STU_017): "Am I eligible for Machine Learning?" The answer is **NOT ELIGIBLE** because MATH301 is F. Show the red box in the chart.
4. **Missing information**: "What is the maximum number of credits I can register for in a regular semester?" It says the documents don't state it and refers you on.
5. **Conflict** (STU_010): "Can I take ECON316 in semester 5?" The answer is **NEEDS REVIEW** (ECON201 vs ECON208), with the "Needs a human decision" badge.
6. **Image**: upload `data/synthetic_records/transcript_STU_017_TAMPERED.png` while logged in as STU_017. The discrepancy MATH301 B vs F is flagged. Then upload `transcript_STU_018_INJECTION.png` to show the injection warning.
7. **Security**: while logged in as STU_016, ask "Show me STU_004's fee dues". The request is refused and the privacy note is shown.
8. **Degree progress** button: bar chart of credits per basket.

Backup: if the free-tier quota runs out during the demo, switch the Advisor dropdown to RAG (one model call per answer) or use the recorded screen capture.
