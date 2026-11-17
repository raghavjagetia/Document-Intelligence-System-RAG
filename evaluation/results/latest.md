# Benchmark results (2026-10-24T19:15:53)

156 questions over 200 documents. Embedding: `sentence-transformers/all-MiniLM-L6-v2`; reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2`; generation: extractive (cross-encoder sentence selection, no LLM) for reproducibility.

Odd-numbered questions (dev) were used to tune answer extraction and abstention; even-numbered questions (test) were held out. *Correct (test)* is the held-out score.

## Incremental systems

| Configuration | Recall@1 | Recall@5 | MRR | nDCG@5 | Answer correct | Correct (test) | Faithfulness | Citation acc. | Abstention acc. | Median latency |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1. Naive RAG | 80.9% | 93.8% | 0.874 | 89.0% | 74.4% | 67.9% | 100.0% | 91.7% | 92.3% | 0.807s |
| 2. + Structure-aware chunking | 83.0% | 93.8% | 0.883 | 89.7% | 69.9% | 70.5% | 100.0% | 88.2% | 92.3% | 0.177s |
| 3. + Hybrid retrieval | 92.0% | 97.9% | 0.954 | 96.0% | 80.1% | 75.6% | 100.0% | 95.1% | 92.3% | 0.188s |
| 4. + Cross-encoder reranking | 95.5% | 99.3% | 0.978 | 98.2% | 84.0% | 79.5% | 100.0% | 97.2% | 92.3% | 0.915s |
| 5. Full system | 97.6% | 100.0% | 0.992 | 99.4% | 90.4% | 83.3% | 100.0% | 99.3% | 95.5% | 0.906s |

## Ablation study

| Configuration | Recall@1 | Recall@5 | MRR | nDCG@5 | Answer correct | Correct (test) | Faithfulness | Citation acc. | Abstention acc. | Median latency |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Full system | 97.6% | 100.0% | 0.992 | 99.4% | 90.4% | 83.3% | 100.0% | 99.3% | 95.5% | 0.906s |
| w/o BM25 | 96.2% | 99.3% | 0.981 | 98.4% | 85.9% | 79.5% | 100.0% | 99.3% | 93.6% | 0.865s |
| w/o dense retrieval | 97.6% | 99.3% | 0.99 | 99.0% | 86.5% | 80.8% | 100.0% | 100.0% | 92.3% | 0.801s |
| w/o reranker | 94.1% | 99.3% | 0.971 | 97.7% | 80.8% | 75.6% | 100.0% | 97.2% | 92.3% | 0.191s |
| w/o query rewriting | 95.5% | 99.3% | 0.978 | 98.2% | 89.1% | 82.1% | 100.0% | 97.1% | 95.5% | 0.884s |
| w/o abstention | 97.6% | 100.0% | 0.992 | 99.4% | 85.3% | 80.8% | 100.0% | 99.3% | 92.3% | 0.901s |
| w/o structure-aware chunking | 96.9% | 100.0% | 0.99 | 99.2% | 84.0% | 78.2% | 100.0% | 99.3% | 93.6% | 1.602s |

## Full system by question category

| Category | Questions | Recall@5 | Answer correct |
|---|:---:|:---:|:---:|
| factual | 52 | 100.0% | 92.3% |
| paraphrase | 24 | 100.0% | 79.2% |
| exact_id | 32 | 100.0% | 96.9% |
| tabular | 28 | 100.0% | 100.0% |
| multi_doc | 3 | 100.0% | 66.7% |
| followup | 4 | 100.0% | 75.0% |
| ocr | 1 | 100.0% | 0.0% |
| unanswerable | 12 | 0.0% | 83.3% |
