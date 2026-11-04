# Evaluation summary

Test set: 42 cases (eval/test_cases.json). Latency excludes free-tier throttling waits.

| mode | cases | accuracy_correct_% | partially_correct_% | hallucination_% | incorrect_% | eligibility_decisions_correct_% | source_correct_% | missing_info_handled_% | conflicts_flagged_% | incorrect_recommendations | median_latency_s | avg_latency_s | avg_tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| basic | 42 | 16.7 | 38.1 | 7.1 | 38.1 | 9.1 | 35.7 | 14.3 | 60.0 | 11 | 1.13 | 1.26 | 236 |
| prompting | 42 | 7.1 | 52.4 | 0.0 | 40.5 | 0.0 | 85.7 | 0.0 | 0.0 | 11 | 0.79 | 0.82 | 1240 |
| rag | 42 | 42.9 | 26.2 | 2.4 | 28.6 | 9.1 | 92.9 | 71.4 | 20.0 | 10 | 1.36 | 1.42 | 2288 |
| rag_student | 42 | 61.9 | 19.0 | 2.4 | 16.7 | 54.5 | 92.9 | 71.4 | 20.0 | 5 | 1.74 | 2.13 | 3632 |
| agentic | 42 | 81.0 | 16.7 | 0.0 | 2.4 | 100.0 | 100.0 | 85.7 | 80.0 | 0 | 14.42 | 15.46 | 5054 |

## Per-case labels

| case | category | basic | prompting | rag | rag_student | agentic |
|---|---|---|---|---|---|---|
| T01 | general | partially correct | partially correct | correct | correct | correct |
| T02 | general | correct | partially correct | correct | correct | correct |
| T03 | general | incorrect | partially correct | correct | correct | correct |
| T04 | general | partially correct | partially correct | unsupported/hallucinated | unsupported/hallucinated | correct |
| T05 | general | incorrect | partially correct | correct | correct | correct |
| T06 | general | partially correct | partially correct | correct | correct | correct |
| T07 | general | partially correct | partially correct | correct | correct | correct |
| T08 | general | partially correct | partially correct | correct | correct | correct |
| T09 | general | partially correct | partially correct | correct | correct | correct |
| T10 | general | partially correct | partially correct | partially correct | partially correct | partially correct |
| T11 | procedure | incorrect | partially correct | correct | correct | correct |
| T12 | general | incorrect | incorrect | correct | correct | correct |
| M01 | missing_info | partially correct | partially correct | partially correct | partially correct | correct |
| M02 | missing_info | partially correct | partially correct | correct | correct | correct |
| M03 | missing_info | correct | partially correct | correct | correct | correct |
| M04 | missing_info | incorrect | incorrect | incorrect | correct | correct |
| M05 | missing_info | partially correct | partially correct | correct | partially correct | correct |
| M06 | missing_info | incorrect | incorrect | incorrect | incorrect | partially correct |
| C01 | conflict | incorrect | incorrect | partially correct | partially correct | correct |
| C02 | conflict | incorrect | incorrect | incorrect | incorrect | correct |
| C03 | conflict | unsupported/hallucinated | incorrect | correct | correct | correct |
| C04 | conflict | incorrect | incorrect | incorrect | incorrect | correct |
| C05 | conflict | correct | incorrect | partially correct | incorrect | incorrect |
| E01 | eligibility | incorrect | incorrect | incorrect | incorrect | correct |
| E02 | eligibility | incorrect | incorrect | incorrect | correct | correct |
| E03 | eligibility | incorrect | incorrect | incorrect | incorrect | correct |
| E04 | eligibility | incorrect | incorrect | incorrect | partially correct | partially correct |
| E05 | eligibility | incorrect | incorrect | incorrect | correct | correct |
| E06 | eligibility | incorrect | incorrect | incorrect | correct | correct |
| E07 | progress | partially correct | partially correct | partially correct | correct | correct |
| E08 | privacy_aware | correct | partially correct | partially correct | correct | correct |
| E09 | progress | partially correct | partially correct | partially correct | correct | correct |
| E10 | graduation | partially correct | partially correct | partially correct | partially correct | partially correct |
| E11 | progress | unsupported/hallucinated | partially correct | partially correct | partially correct | correct |
| E12 | progress | partially correct | partially correct | partially correct | correct | partially correct |
| E13 | eligibility | partially correct | incorrect | correct | correct | correct |
| A01 | ambiguous | correct | correct | correct | correct | correct |
| A02 | ambiguous | correct | correct | incorrect | correct | partially correct |
| A03 | ambiguous | partially correct | partially correct | correct | correct | correct |
| U01 | unavailable | unsupported/hallucinated | incorrect | incorrect | incorrect | correct |
| U02 | unavailable | incorrect | incorrect | partially correct | partially correct | partially correct |
| O01 | off_topic | correct | correct | correct | correct | correct |