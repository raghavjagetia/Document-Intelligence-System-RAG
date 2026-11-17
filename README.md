# DocuMind — AI Document Intelligence & Hybrid RAG System

> **B.Tech CSE Major Project.** Upload documents in 8 formats, ask questions in English, Hindi, Hinglish
> or other languages, and get answers that cite the exact page and section they came from — click a
> citation to see the supporting sentence highlighted on the original page. If the documents don't
> contain the answer, the system says so.

**Stack:** FastAPI · React + TypeScript · Sentence-BERT · FAISS · BM25 · Cross-encoder reranking · RapidOCR · spaCy · SQLite

---

## Features

| Area | What it does |
|---|---|
| **Ingestion** | PDF, DOCX, TXT/Markdown, HTML, CSV, XLSX, PPTX, plus PNG/JPG images. Scanned PDF pages and images go through **OCR** (RapidOCR). Tables are extracted to Markdown, and each spreadsheet row is also stored as a sentence so table questions can be answered. Repeated PDF headers and footers are removed. Uploading an identical file is detected as a duplicate (SHA-256). Uploading a changed file with the same name creates **version 2, 3, …** |
| **Chunking** | Chunks follow the document's structure. A new chunk starts at every heading, tables are never split, sentence boundaries are kept, and page and section numbers are recorded. Each chunk is stored with its document title and section as a header ("contextual retrieval"). |
| **Retrieval** | **Hybrid search.** Dense search uses MiniLM embeddings in a **FAISS** index, filtered to the current user. Keyword search uses **BM25** with a tokenizer that keeps IDs like `INV-2026-8842` intact. The two result lists are merged with **Reciprocal Rank Fusion**. |
| **Reranking** | The **cross-encoder** `ms-marco-MiniLM-L-6-v2` re-scores the top 20 candidates. |
| **Answering** | **With an LLM** (Groq / Gemini / Claude): answers are generated with numbered source citations and stream token by token. **Offline, with no key:** *neural extractive QA*. The cross-encoder scores every sentence, then adjusts for the expected answer type (money, date or number), exact-ID matching and novelty. |
| **Trust** | **Abstention** when evidence is weak, or when the question names a year or ID that isn't in the evidence. **Grounding check:** every answer sentence must be semantically supported by a retrieved sentence. A **confidence score** is shown, and each citation chip shows a page-level snippet. |
| **See the source** | Clicking a citation opens the **original PDF page with the supporting sentence highlighted** (page rendered with pypdfium2; the sentence is located in the page's text layer and outlined). Word, HTML, slides, spreadsheets and text files open as the cited passage with the sentence marked. Each source also shows how it was found (by meaning, by exact words, or both). |
| **Answer styles** | **Quick answer** (one or two cited sentences), **Detailed answer** (a bold direct answer plus bullet points with conditions, limits and differences between document versions) or **Exact quote** (sentences copied word-for-word from the documents, with document and page — quoted from several documents when more than one is relevant). |
| **Other languages** | Questions in Hindi, Hinglish (Hindi in Latin letters) or other languages are translated to English for search, answered and **grounding-checked in English**, then translated back into the asker's language with citations, numbers and IDs kept unchanged. Requires an LLM key; without one the user is asked to write in English. |
| **Conversations** | Follow-up questions ("What about sick leave?", "Who approved it?") are rewritten into standalone questions using the previous questions **and the previous answer**, so "it" or "they" is resolved to the right invoice, person or policy. Chat history is saved per user. |
| **Feedback** | Thumbs up / down on every answer (only by the person who asked). The Dashboard shows the share of helpful answers per answer style. |
| **Document intelligence** | Summaries: an LLM summary, or an offline one that picks the most central sentences by embedding similarity. Named entities: spaCy plus patterns for IDs, money, phone numbers and emails. Contract, invoice and resume field extraction that returns **"not found" instead of inventing values**. Version comparison shows added, removed and modified clauses, with number changes like `18 → 20 (+2, +11%)`. |
| **Security** | PBKDF2-SHA256 password hashing with 200,000 iterations; passwords of at least 8 characters. Session tokens are random and stored only as SHA-256 hashes. **No built-in passwords**: automatically created accounts take their password from the environment or get a random one on first start. **Brute-force protection**: an account is locked for 15 minutes after 5 wrong passwords, and sign-ups are rate-limited per network address. Every query is filtered by user, so users can never see each other's documents or chats. Uploads are checked for file type and size. Security headers (no-sniff, no framing). Only administrators can start the benchmark. |
| **Evaluation** | A 156-question benchmark runs 5 progressively more complete systems and 6 ablations (Recall@k, MRR, nDCG@5, answer correctness, faithfulness, citation accuracy, abstention accuracy, latency). An **advanced evaluation** compares DocuMind with an **LLM-only** baseline and a **standard LangChain RAG** pipeline, adds **95% confidence intervals** (error bars) and **significance tests**, sorts every wrong answer into a **failure category**, and measures **Hindi/Hinglish** accuracy against the same questions in English. The comparison is shown first on the Evaluation page and summarised on the Dashboard; the full error analysis and multilingual results are in `evaluation/results/advanced_eval.md` and the report. |
| **UI** | Modern React single-page app with dark/light themes, a command palette (Ctrl+K), drag-and-drop uploads with progress, streaming chat with citation pop-ups, analytics charts and the evaluation dashboard. Works on phones. |

## Architecture

```
 React SPA (Vite, Tailwind, React Query)          FastAPI  /api/*
 ┌─────────────────────────────────────┐     ┌──────────────────────────────────────────────────────┐
 │ Login · Dashboard · Documents · Chat │ ──► │ auth.py ─ sessions/users (SQLite, per-user isolation) │
 │ Insights · Evaluation · Settings     │ ◄── │ services.py ─ ingestion · chat · index sync           │
 └─────────────────────────────────────┘ SSE └──────────────────────────────────────────────────────┘
                                                        │
   Upload ─► document_processor (parse + OCR + tables) ─► intelligent_chunking (structure-aware)
                                                        │
                    ┌──────────── vector_store (MiniLM → FAISS, filtered by user)
   Question ─► rewrite ─┤                                         ├─► RRF fusion ─► cross-encoder rerank
                    └──────────── BM25 (ID-aware tokenizer) ─────┘
                                                        │
              abstain?  ─► LLM / neural extractive answer ─► grounding check ─► citations + confidence
```

| File | Responsibility |
|---|---|
| `backend/app.py` | REST API and server-sent-events (SSE) streaming; also serves the built frontend |
| `backend/services.py` | Connects the components: ingestion, deletion, chat saving, index rebuild |
| `backend/document_processor.py` | Parses all formats, runs OCR, extracts tables, removes headers and footers |
| `backend/intelligent_chunking.py` | Structure-aware chunking, plus the fixed-size baseline used in the benchmark |
| `backend/vector_store.py` | FAISS `IndexIDMap2(IndexFlatIP)` with filtered search and deletion |
| `backend/hybrid_retriever.py` | BM25 and Reciprocal Rank Fusion |
| `backend/reranker.py` | Cross-encoder reranking (with a lexical fallback) |
| `backend/rag_pipeline.py` | Query rewriting, abstention, answer generation, grounding, citations |
| `backend/document_intelligence.py` | Summaries, named entities, field extraction, comparison |
| `backend/llm.py` | Groq / Gemini / Claude clients with streaming |
| `backend/evaluation.py` | The benchmark runner and all metric calculations |
| `backend/advanced_eval.py` | Baselines (LLM only, standard LangChain RAG), confidence intervals, significance tests, error analysis, multilingual benchmark, Groq quota guard |
| `backend/source_view.py` | Renders the cited PDF page and locates the supporting sentence for highlighting |
| `frontend/src` | React app (pages, components, typed API client) |

The full API reference is in [docs/API.md](docs/API.md). Interactive API docs are at `http://localhost:8000/api/docs`.

## Quick start

**Requirements:** Python 3.10+ and Node 18+.

```powershell
# Windows: one command does everything (venv, dependencies, UI build, demo data, server)
./run.ps1
```
```bash
# macOS / Linux / Git Bash
./run.sh
```

Then open **http://localhost:8000** and sign in. The project contains **no built-in passwords**: set
`ADMIN_PASSWORD`, `DEMO_PASSWORD` and `SEED_USER_PASSWORD` in `.env` before the first start, or leave them
empty and random passwords are generated and written to `data/initial_credentials.txt` (a private file that is
never committed). You can also create your own account on the sign-up page.

<details><summary>Manual setup</summary>

```bash
python -m venv .venv && .venv\Scripts\activate            # source .venv/bin/activate on Linux/macOS
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cd frontend && npm install && npm run build && cd ..
python scripts/seed_demo.py                                 # 50 users + admin, 445 documents, 246 chat questions
python -m uvicorn backend.app:app --port 8000
```
For frontend development with hot reload, run `cd frontend && npm run dev` and open http://localhost:5173. Requests to `/api` are forwarded to port 8000.
</details>

**Docker:** `docker compose up --build`

### Optional: LLM answers
The system works fully offline. To get written answers, detailed answers, summaries and other-language
questions, copy `.env.example` to `.env` and fill in the API key of **one** provider: Groq (free tier,
https://console.groq.com/keys, default model `qwen/qwen3.8-27b`), Google Gemini or Anthropic Claude. Keep
`.env` private — it is listed in `.gitignore` and must never be committed or shared.
The Settings page shows which LLM, embedding model, reranker and OCR engine are active.

## Demo data

| Data | Count | Source |
|---|---|---|
| Users | 50 + administrator | A demo account, 49 sample accounts and one administrator (who sees all users, documents and questions on the Admin page). Passwords: see *Quick start* |
| Documents | 200 in the demo account | 10 fictional organisations x 20 documents each (HR, legal, healthcare, finance and general); every company has its own colour theme. 49 PDF (1 scanned), 53 DOCX, 11 TXT, 15 MD, 16 HTML, 19 CSV, 14 XLSX, 23 PPTX. Generated by `scripts/generate_sample_data.py` + `scripts/corpus_expansion.py`. Every sample account also has 5 unique documents of its own (`scripts/generate_user_documents.py`) |
| Chat questions | 246 | 50 in the demo account plus 4 per sample user, asked through the real pipeline during seeding |
| Answer feedback | ~430 sample ratings | **Sample data, not real users.** `scripts/seed_feedback.py` rates existing answers (helpful more often for confident, well-supported answers) and asks every account a few questions in the Detailed and Exact-quote styles (offline, no API quota), so the Dashboard's feedback chart has data. Administrators see all accounts' ratings, everyone else only their own |
| Benchmark questions | 156 | `evaluation/eval_dataset.json`: 52 factual, 24 paraphrase, 32 exact_id, 28 tabular, 3 multi_doc, 4 followup, 1 ocr, 12 unanswerable (50 hand-written + 106 generated with their documents) |

The corpus includes version pairs (Leave Policy 2025 → 2026, MSA v1 → v2) for the comparison feature. It also includes near-duplicate IDs, such as `INV-2026-8842` vs `INV-2026-8824`, which make retrieval harder.

Three of the sample accounts each own one private document. Sign in as one of them to see that the demo account's documents are invisible to them.

## Evaluation

```bash
python evaluation/run_benchmark.py      # or use "Run Benchmark" on the Evaluation page
```
Results are written to `evaluation/results/latest.md` and `latest.json`.

### Results (156 questions, 200 documents, CPU, no LLM)

| Configuration | R@1 | R@5 | MRR | nDCG@5 | Answer correct | Correct (held-out test) | Citation acc. | Abstention acc. | Median latency |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1. Naive RAG | 80.9% | 93.8% | 0.874 | 89.0% | 74.4% | 67.9% | 91.7% | 92.3% | 0.807s |
| 2. + Structure-aware chunking | 83.0% | 93.8% | 0.883 | 89.7% | 69.9% | 70.5% | 88.2% | 92.3% | 0.177s |
| 3. + Hybrid retrieval | 92.0% | 97.9% | 0.954 | 96.0% | 80.1% | 75.6% | 95.1% | 92.3% | 0.188s |
| 4. + Cross-encoder reranking | 95.5% | 99.3% | 0.978 | 98.2% | 84.0% | 79.5% | 97.2% | 92.3% | 0.915s |
| **5. Full system** | 97.6% | 100.0% | 0.992 | 99.4% | 90.4% | 83.3% | 99.3% | 95.5% | 0.906s |

**Ablations** (one component removed from the full system):

| Configuration | R@1 | R@5 | MRR | nDCG@5 | Answer correct | Correct (held-out test) | Citation acc. | Abstention acc. | Median latency |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Full system** | 97.6% | 100.0% | 0.992 | 99.4% | 90.4% | 83.3% | 99.3% | 95.5% | 0.906s |
| w/o BM25 | 96.2% | 99.3% | 0.981 | 98.4% | 85.9% | 79.5% | 99.3% | 93.6% | 0.865s |
| w/o dense retrieval | 97.6% | 99.3% | 0.99 | 99.0% | 86.5% | 80.8% | 100.0% | 92.3% | 0.801s |
| w/o reranker | 94.1% | 99.3% | 0.971 | 97.7% | 80.8% | 75.6% | 97.2% | 92.3% | 0.191s |
| w/o query rewriting | 95.5% | 99.3% | 0.978 | 98.2% | 89.1% | 82.1% | 97.1% | 95.5% | 0.884s |
| w/o abstention | 97.6% | 100.0% | 0.992 | 99.4% | 85.3% | 80.8% | 99.3% | 92.3% | 0.901s |
| w/o structure-aware chunking | 96.9% | 100.0% | 0.99 | 99.2% | 84.0% | 78.2% | 99.3% | 93.6% | 1.602s |

- **Held-out score.** Odd-numbered questions (dev) were used to tune the answer-selection and abstention rules; even-numbered questions (test) were never inspected while tuning. The full system scores **83.3% on the held-out test half** (97.4% on dev, 90.4% overall).
- Retrieval is close to perfect (Recall@5 100.0%, MRR 0.992); the remaining errors are in choosing the answer sentence, mostly for paraphrased questions. An LLM is the next step for those (see the results with an LLM below).
- Faithfulness is 100% in every row, because extractive answers are copied from retrieved text, so it is not shown. Full analysis: report section 39.


<!-- llm-comparison:start -->
### With an LLM (2026-10-24)

Same full system and the same 156 questions, but the answer is written by `qwen/qwen3.8-27b` on Groq instead of the offline extractive generator (`python evaluation/run_benchmark.py --llm`; results in `evaluation/results/llm_comparison.md`):

| Answer generator | Correct answers | Correct (held-out test) | Faithfulness | Citation acc. | Abstention acc. | Recall@1 | Median latency |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Offline extractive (no LLM) | 90.4% | 83.3% | 100.0% | 99.3% | 95.5% | 97.6% | 1.461s |
| LLM: `qwen/qwen3.8-27b` on Groq | 95.5% | 93.6% | 98.5% | 100.0% | 95.5% | 96.9% | 2.892s |

- On held-out questions the LLM raises correctness from **83.3% to 93.6%**; the biggest gains are two-document comparisons, follow-ups, the scanned page and correctly refusing unanswerable questions.
- Faithfulness is checked claim by claim: every number, date and ID in an answer must appear in the retrieved sources. 98.5% of LLM answers pass; the few that fail were manually checked and are correct table look-ups.
- 96.4% of answers were written by the LLM; the remaining 3.6% fell back to the offline generator because the free Groq tier rate-limited the request, which is how the app behaves too.
<!-- llm-comparison:end -->

<!-- advanced-eval:start -->
### Compared with standard approaches (2026-11-16)

Same 156 questions, same documents and the same LLM (`qwen/qwen3.8-27b` on Groq). Error bars are 95% Wilson
confidence intervals; differences are tested with an exact McNemar test on the questions one system answered
correctly and the other did not. Run: `python evaluation/run_advanced.py` (resumable; results in
`evaluation/results/advanced_eval.md`, on the Evaluation page and on the Dashboard).

| System | Correct (95% CI) | Held-out test (95% CI) | Refuses correctly | Right document first | Backed by sources |
|---|:---:|:---:|:---:|:---:|:---:|
| LLM only (no documents) | 9.6% (5.9–15.3) | 9.0% (4.4–17.4) | 9.6% | – | – |
| Standard RAG (LangChain) | 82.7% (76.0–87.8) | 78.2% (67.8–85.9) | 84.0% | 77.4% | 91.3% |
| DocuMind, offline (no LLM) | 90.4% (84.7–94.1) | 83.3% (73.5–90.0) | 95.5% | 97.6% | 100.0% |
| **DocuMind + LLM** | **95.5% (91.0–97.8)** | **93.6% (85.9–97.2)** | 95.5% | 96.9% | 100.0% |

- **vs standard LangChain RAG:** DocuMind + LLM answered 25 questions correctly that LangChain got wrong, and
  LangChain 5 that DocuMind got wrong (McNemar p = 0.0003, significant). Same LLM and same extracted text, so the
  difference comes from the pipeline: structure-aware chunks, hybrid search, re-ranking, refusal rules and prompting.
- **vs the LLM alone:** without the documents the LLM correctly said "I don't know" to 141 of 144 answerable
  questions — it does not hallucinate, but it cannot know private documents (135 vs 1, p < 0.001).
- **LLM vs offline answers in DocuMind:** 9 vs 1 (p = 0.02).

**Error analysis** (every wrong answer put in one category):

| Failure type | DocuMind + LLM | DocuMind offline | LangChain |
|---|:---:|:---:|:---:|
| Wrong document found | 0 | 0 | 1 |
| Right document, wrong or incomplete answer | 0 | 8 | 1 |
| Wrongly refused | 7 | 5 | 25 |
| Answered when it should have refused | 0 | 2 | 0 |
| **Total wrong** | **7** | **15** | **27** |

All 7 errors of DocuMind + LLM are over-cautious refusals with the right document already found, so the refusal
rule is the one component left to improve. LangChain's refusals are mostly search failures: in 15 of its 25 the
right document was never retrieved (mainly table rows and exact IDs such as `EMP-2026-00421`), in the other 10 the
document was found but not the passage with the answer.

**Other languages** (30 benchmark questions re-asked in Hindi and Hinglish, scored with the English answer key):

| Language | Questions | Correct (95% CI) | Same questions in English | Replied in same language | Numbers kept exact |
|---|:---:|:---:|:---:|:---:|:---:|
| Hindi | 15 | 100% (79.6–100) | 93.3% | 100% | 100% |
| Hinglish | 15 | 100% (79.6–100) | 100% | 100% | 100% |
| All | 30 | 100% (88.6–100) | 96.7% | 100% | 100% |

With 15 questions per language the intervals are wide: the result shows the translate-verify-translate design
works, not that accuracy in Hindi is exactly 100%. The questions were translated for this project and should be
reviewed by a native speaker.
<!-- advanced-eval:end -->


## Tests

```bash
python -m pytest -q                              # 62 tests, fast fallback models (~20 s)
ENABLE_NEURAL_MODELS=true python -m pytest -q    # same tests with the real models
```
The tests cover:
- BM25, RRF fusion, chunking, query rewriting and the metric calculations (nDCG never exceeds 1.0);
- password hashing, extraction never inventing values, and the evaluation statistics (Wilson confidence intervals,
  McNemar test, failure categories, baseline refusal detection, the Groq quota guard and its cache);
- authentication (401 responses, login and logout), **account lock-out after repeated wrong passwords**,
  the 8-character password rule, security headers, administrator-only benchmark runs and **random initial
  passwords instead of built-in ones**;
- **user isolation** and **deletion removing a document from search**;
- ingestion of every format, including OCR;
- answer styles, quoting from several documents, language detection and translate-verify-translate answering,
  follow-up rewriting with the previous answer, **source highlighting on the PDF page** and in text formats,
  and owner-only answer feedback;
- versioning and comparison, streaming, document-scoped questions, abstention, and the dashboard endpoints.

## Limitations
- Without an LLM, answers are extracted sentences rather than written prose. Questions that need reasoning across sentences can fail, for example "Who is the CEO?" when the document only names a "Designated Partner".
- The answer-selection and abstention rules were tuned on the dev half of the benchmark. On the held-out test half the full system scores 83.3% versus 97.4% on dev; the gap (mainly paraphrased questions) shows some over-fitting of the coverage-based abstention rule.
- Other languages work only with an LLM key (translation is done by the LLM), and each such question uses three
  LLM calls. The 30 Hindi/Hinglish benchmark questions were written for this project and should be reviewed by
  a native speaker. Very poor-quality scans reduce OCR accuracy.
- The benchmark documents were generated for this project; results on real-world documents may be lower.
- Rate limits and failed-login counters are kept in memory, so they reset when the server restarts and do not
  span several server processes.

## Future scope
- Native multilingual embeddings, so other-language questions also work offline.
- Vision-language models for charts and figures.
- Knowledge-graph RAG (GraphRAG) for multi-hop questions.
- Background job queue for large uploads.
- Single sign-on (SSO / OAuth2).

## Project layout
```
backend/      FastAPI app and all AI/RAG modules
frontend/     React + TypeScript single-page app
scripts/      generate_sample_data.py, corpus_expansion.py, generate_user_documents.py, seed_demo.py, seed_feedback.py
evaluation/   eval_dataset.json, multilingual_dataset.json, run_benchmark.py, run_advanced.py, results/
tests/        pytest suite (unit + API)
docs/         API reference
data/         sample_documents/ (committed) + runtime data (app.db, index/, uploads/ - ignored)
legacy/       previous Streamlit version, kept for reference
```
