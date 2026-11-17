# Extractive vs LLM generation (2026-10-24T17:47:52)

Full system, 156 questions. LLM: `groq/qwen/qwen3.8-27b`.

| Generator | Answer correct | Correct (held-out test) | Written by LLM | Abstention acc. | Faithfulness | Citation acc. | Recall@1 | Median latency | P95 latency |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Extractive (no LLM) | 90.4% | 83.3% | 0.0% | 95.5% | 100.0% | 99.3% | 97.6% | 1.461s | 6.863s |
| LLM: groq/qwen/qwen3.8-27b | 95.5% | 93.6% | 96.4% | 95.5% | 98.5% | 100.0% | 96.9% | 2.892s | 16.22s |

| Category | Extractive (no LLM) | LLM: groq/qwen/qwen3.8-27b |
|---|:---:|:---:|
| factual | 92.3% | 100.0% |
| paraphrase | 79.2% | 79.2% |
| exact_id | 96.9% | 96.9% |
| tabular | 100.0% | 96.4% |
| multi_doc | 66.7% | 100.0% |
| followup | 75.0% | 100.0% |
| ocr | 0.0% | 100.0% |
| unanswerable | 83.3% | 100.0% |
