# Advanced evaluation (2026-11-16T19:13:02)

156 questions; LLM `groq/qwen/qwen3.8-27b`.

## Compared with standard approaches

| System | Answer correct (95% CI) | Held-out test (95% CI) | Abstention acc. | Recall@1 | Faithfulness |
|---|:---:|:---:|:---:|:---:|:---:|
| LLM only (no documents) | 9.6% (5.9–15.3) | 9.0% (4.4–17.4) | 9.6% | – | – |
| Standard RAG (LangChain) | 82.7% (76.0–87.8) | 78.2% (67.8–85.9) | 84.0% | 77.4% | 91.3% |
| DocuMind (offline, no LLM) | 90.4% (84.7–94.1) | 83.3% (73.5–90.0) | 95.5% | 97.6% | 100.0% |
| DocuMind + LLM | 95.5% (91.0–97.8) | 93.6% (85.9–97.2) | 95.5% | 96.9% | 100.0% |

| Comparison | Only first correct | Only second correct | McNemar p |
|---|:---:|:---:|:---:|
| DocuMind + LLM vs Standard RAG (LangChain) | 25 | 5 | 0.00032 |
| DocuMind + LLM vs LLM only (no documents) | 135 | 1 | 0.0 |
| DocuMind + LLM vs DocuMind (offline, no LLM) | 9 | 1 | 0.02148 |

## Error analysis - DocuMind + LLM (7 of 156 wrong)

| Failure type | Count | Share |
|---|:---:|:---:|
| Wrong document found | 0 | 0.0% |
| Right document, wrong or incomplete answer | 0 | 0.0% |
| Wrongly refused | 7 | 100.0% |
| Answered when it should have refused | 0 | 0.0% |

Of the 7 wrong refusals, the right document had been found in 7; in the other 0 search never found it.

## Error analysis - DocuMind (offline, no LLM) (15 of 156 wrong)

| Failure type | Count | Share |
|---|:---:|:---:|
| Wrong document found | 0 | 0.0% |
| Right document, wrong or incomplete answer | 8 | 53.3% |
| Wrongly refused | 5 | 33.3% |
| Answered when it should have refused | 2 | 13.3% |

Of the 5 wrong refusals, the right document had been found in 5; in the other 0 search never found it.

## Error analysis - Standard RAG (LangChain) (27 of 156 wrong)

| Failure type | Count | Share |
|---|:---:|:---:|
| Wrong document found | 1 | 3.7% |
| Right document, wrong or incomplete answer | 1 | 3.7% |
| Wrongly refused | 25 | 92.6% |
| Answered when it should have refused | 0 | 0.0% |

Of the 25 wrong refusals, the right document had been found in 10; in the other 15 search never found it.

## Multilingual benchmark

| Language | Questions | Accuracy (95% CI) | Same questions in English | Reply in same language | Numbers preserved |
|---|:---:|:---:|:---:|:---:|:---:|
| Hindi | 15 | 100.0% (79.6–100.0) | 93.3% | 100.0% | 100.0% |
| Hinglish | 15 | 100.0% (79.6–100.0) | 100.0% | 100.0% | 100.0% |
| All | 30 | 100.0% (88.6–100.0) | 96.7% | 100.0% | 100.0% |
