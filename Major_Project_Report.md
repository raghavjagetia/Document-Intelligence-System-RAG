# B.TECH CSE MAJOR PROJECT REPORT

# DocuMind: AI-Powered Document Intelligence with Hybrid Retrieval-Augmented Generation

---

## Abstract

Organisations keep critical knowledge in PDFs, Word files, spreadsheets, slide decks and scanned images. Keyword search cannot answer questions about these files, and large language models (LLMs) used on their own hallucinate and cannot cite their sources. Retrieval-Augmented Generation (RAG) grounds answers in retrieved passages. However, naive RAG pipelines lose document structure, miss exact identifiers such as invoice numbers, cannot read scanned pages, and answer even when no evidence exists.

This project presents **DocuMind**, an end-to-end document intelligence system. Its main components are:

- **Ingestion** of eight file formats, with OCR for scanned pages and images.
- **Structure-aware chunking** with contextual chunk headers.
- **Hybrid retrieval**, combining dense Sentence-BERT embeddings in a FAISS index with ID-aware BM25 search, merged by Reciprocal Rank Fusion.
- **Cross-encoder reranking.**
- **Conversational query rewriting** for follow-up questions.
- **Evidence-based abstention.**
- **Two answer generators:** LLM generation with citations, or an offline neural extractive QA mode, in three answer styles (quick, detailed, exact quote).
- **Sentence-level grounding verification**, and a source viewer that opens the cited PDF page with the supporting sentence highlighted.
- **Questions in other languages** (Hindi, Hinglish and others), answered by translating the question, verifying the answer in English and translating it back.

The system also provides summarisation, named-entity recognition, contract/invoice/resume field extraction that never invents values, and version comparison with numeric change detection. Every user's data is isolated, accounts are protected against password guessing, and the web application is built in React.

The system is evaluated on a new benchmark of **156 questions over a 200-document corpus** from ten fictional organisations, covering factual, paraphrased, exact-identifier, tabular, multi-document, follow-up, OCR and unanswerable questions. Five incremental system configurations and six ablations are compared on Recall@k, MRR, nDCG@5, answer correctness, faithfulness, citation accuracy, abstention accuracy and latency. Without any LLM, the full system reaches 97.6% Recall@1 and 90.4% answer correctness (83.3% on held-out questions not used for tuning), against 74.4% for naive RAG. With an LLM it reaches **95.5% (95% CI 91.0–97.8%), against 82.7% for a standard LangChain RAG pipeline using the same LLM and 9.6% for the LLM without documents**; the difference from LangChain is statistically significant (exact McNemar test, p = 0.0003). An error analysis shows that every remaining error of the system is an over-cautious refusal, never a wrong or invented answer. Thirty benchmark questions re-asked in Hindi and Hinglish were all answered correctly (95% CI 88.6–100%).

---

## 1. Introduction
Knowledge workers spend a large share of their time searching for information buried in documents: HR policies, contracts, invoices, clinical records and financial reports. LLMs can answer questions fluently but are unreliable on private data. They have never seen it, they cannot cite where an answer came from, and they produce confident fabrications. RAG addresses this by retrieving relevant passages at question time and conditioning the answer on them.

This project builds a practical RAG system for mixed-format document collections. It emphasises three properties: **retrieval quality** (finding the right passage, including for exact IDs and paraphrased questions), **trustworthiness** (citations, grounding checks and refusing to answer without evidence), and **usability** (a modern web interface with streaming answers, analytics and evaluation dashboards).

## 2. Background
- **Dense retrieval** encodes text into vectors so that semantically similar passages lie close together. This works well for paraphrases but can miss rare tokens and identifiers.
- **Sparse retrieval** (BM25) scores exact term overlap weighted by rarity. It is excellent for identifiers and rare terms, but blind to synonyms.
- **Reranking** with a cross-encoder reads the query and passage *together*, which is more accurate than either first-stage retriever but too slow to run over a whole corpus. It is therefore applied to the top candidates only.
- **Grounding and abstention** check whether an answer is supported by the evidence, and decline to answer when it is not.

## 3. Problem Statement
Design and implement a system that ingests heterogeneous documents, answers natural-language questions about them with verifiable page-level citations, refuses to answer when the documents do not contain the answer, and provides document analytics. Then evaluate it quantitatively against simpler RAG designs.

The specific problems addressed are:
1. **Format fragmentation:** PDF, DOCX, HTML, TXT/Markdown, CSV, XLSX, PPTX and scanned images.
2. **Context fragmentation:** fixed-size chunking splits sentences and tables and loses section context.
3. **Retrieval blind spots:** dense embeddings confuse near-identical identifiers (`INV-2026-8842` vs `INV-2026-8824`); keyword search misses paraphrases.
4. **Hallucination:** naive RAG always produces an answer, even for questions the corpus cannot answer.
5. **Provenance:** answers must be traceable to a document, page and passage.
6. **Privacy:** each user's documents and conversations must be invisible to other users.

## 4. Existing Systems
- **Enterprise keyword search** (e.g. SharePoint search, Elasticsearch): returns documents, not answers, and has no semantic matching.
- **Cloud "chat with your PDF" tools:** usually single-format with fixed-size chunking and dense-only retrieval. They rarely abstain, and they send private data to third-party services.
- **Framework demos** (LangChain/LlamaIndex quick-starts): `RecursiveCharacterTextSplitter`, a single vector store and direct LLM generation, with no grounding check and no evaluation.

## 5. Limitations of Existing Systems
- Poor recall of exact identifiers and of table cells.
- No OCR for scanned pages; tables flattened into unreadable text.
- No abstention, so confident wrong answers on out-of-scope questions.
- Citations missing or limited to the file name.
- No measurement of retrieval or answer quality.

## 6. Proposed System
DocuMind combines:
1. A **multi-format ingestion engine** with OCR, table extraction, header/footer removal, duplicate detection and versioning.
2. **Structure-aware chunking** with **contextual chunk headers** (document title + section).
3. **Hybrid retrieval**: FAISS dense search + ID-aware BM25, fused by Reciprocal Rank Fusion.
4. A **cross-encoder reranker**.
5. **Conversational query rewriting.**
6. **Evidence-based abstention.**
7. **Answer generation** by an LLM (Groq, Gemini or Claude) or by offline **neural extractive QA**.
8. **Grounding verification**, **citations** and a **confidence score**.
9. **Document intelligence**: summaries, entities, key-field extraction and version comparison.
10. **Multi-user web application** with authentication, isolation, analytics and a built-in evaluation dashboard.
11. **Answer styles, multilingual questions, a highlighted source viewer and answer feedback** (sections 24–26 and 34).

## 7. Objectives
1. Ingest at least seven document formats, including OCR for scanned content.
2. Implement structure-aware chunking that preserves sections, pages and tables.
3. Implement hybrid dense + sparse retrieval with rank fusion and cross-encoder reranking.
4. Provide page-level citations, grounding verification and abstention on unanswerable questions.
5. Provide summarisation, entity extraction, structured extraction and version comparison.
6. Build a secure, multi-user, modern web interface.
7. Build a benchmark and quantitatively compare the proposed system against baselines and ablations.

## 8. Scope
**In scope:** English documents up to 25 MB each; questions in English, and in Hindi, Hinglish and other languages when an LLM is configured; single-server deployment (local, or Docker); offline operation without an LLM; optional LLM providers.
**Out of scope:** documents in languages other than English, handwriting recognition, image or chart understanding, and distributed indexing.

---

## 9. Literature Review
| Work | Contribution | Use in this project |
|---|---|---|
| Lewis et al., 2020, *RAG for Knowledge-Intensive NLP* | Combines a retriever with a generator to ground answers | Overall architecture |
| Robertson & Zaragoza, 2009, *BM25 and Beyond* | Probabilistic relevance framework, BM25 | Sparse retriever |
| Reimers & Gurevych, 2019, *Sentence-BERT* | Efficient sentence embeddings with siamese BERT | Dense retriever (`all-MiniLM-L6-v2`) |
| Johnson, Douze & Jégou, 2019, *Billion-scale similarity search with GPUs* (FAISS) | Efficient vector indexes | Vector index |
| Cormack, Clarke & Büttcher, 2009, *Reciprocal Rank Fusion* | Score-free fusion of ranked lists | Hybrid fusion |
| Nogueira & Cho, 2019, *Passage Re-ranking with BERT* | Cross-encoders for reranking | Reranker (`ms-marco-MiniLM-L-6-v2`) |
| Gao et al., 2023, *RAG for LLMs: A Survey* | Taxonomy of naive / advanced / modular RAG | Design of the incremental experiments |
| Es et al., 2023, *RAGAS* | Faithfulness and answer-relevance metrics for RAG | Faithfulness / grounding metric design |
| Järvelin & Kekäläinen, 2002, *Cumulated gain-based evaluation* | nDCG | Ranking metric |
| Anthropic, 2024, *Contextual Retrieval* | Adding document context to chunks before indexing | Contextual chunk headers |

---

## 10. System Requirements
| | Minimum | Recommended |
|---|---|---|
| OS | Windows 10/11, Ubuntu 20.04+, macOS 12+ | — |
| CPU / RAM | 4 cores / 8 GB | 8 cores / 16 GB |
| Disk | 4 GB (models and dependencies) | 10 GB |
| Software | Python 3.10–3.13, Node.js 18+ | Docker (optional) |
| GPU | Not required | — |

## 11. Functional Requirements
- **FR1** Register, log in and log out; use a one-click demo account.
- **FR2** Upload one or more files in 8 formats; reject unsupported, empty, oversized and duplicate files; version files that are re-uploaded under the same name.
- **FR3** List, search, filter, inspect (chunks, metadata, versions), download and delete documents.
- **FR4** Ask questions across all documents, one domain or one document, in hybrid, semantic or BM25 mode, with answers streamed as they are produced.
- **FR5** Show citations (file, page, section, snippet, relevance), a confidence score and a grounding score; abstain when evidence is insufficient.
- **FR6** Rewrite follow-up questions using the conversation history; keep and manage conversations.
- **FR7** Summarise documents, extract entities and key fields, and compare two documents or versions.
- **FR8** Show usage analytics and run the benchmark from the UI.
- **FR9** Administrators (role `admin`) see a system-wide overview of all users, documents and recent questions; the endpoint returns 403 for normal users.

## 12. Non-Functional Requirements
- **Security:** salted PBKDF2 password hashes (minimum 8 characters), hashed session tokens, per-user data isolation enforced in every database query and vector search, upload validation. No passwords are built into the code or documentation: automatically created accounts take their password from the environment, or get a random one written to a private file on first start. An account is locked for 15 minutes after 5 wrong passwords, sign-ups are rate-limited per network address, security headers forbid content sniffing and framing, and only administrators can start the (CPU-heavy) benchmark.
- **Reliability:** works fully offline; each model has a fallback; the search index rebuilds itself from the database if it is missing or out of date.
- **Performance:** answers in about 1–3 s on a laptop CPU without an LLM.
- **Usability:** responsive UI (desktop and mobile), dark/light themes, keyboard command palette.
- **Maintainability:** modular backend, typed frontend, 62 automated tests, documented API.

---

## 13. System Architecture
```
 ┌──────────────────────── React SPA (TypeScript, Tailwind, React Query) ────────────────────────┐
 │  Login │ Dashboard │ Documents │ Chat (SSE streaming) │ Insights │ Evaluation │ Settings        │
 └───────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                             │ REST + Server-Sent Events  (/api/*)
 ┌───────────────────────────────────────────┴────────────────────────────────────────────────────┐
 │ FastAPI  ── auth (PBKDF2, hashed sessions) ── services (ingest · chat · index sync)               │
 │                                                                                                   │
 │  INGESTION                         RETRIEVAL                          ANSWERING                   │
 │  parse 8 formats ─► OCR ─►         query ─► rewrite ─┬─► FAISS dense ─┐                          │
 │  tables ─► header/footer strip     (follow-ups)      └─► BM25 sparse ─┴─► RRF ─► cross-encoder    │
 │  ─► structure-aware chunks                                                    │                   │
 │  ─► contextual headers ─► embed                       abstain? ◄──────────────┘                   │
 │                                                        │ no                                       │
 │  INTELLIGENCE                                          ▼                                          │
 │  summary · NER · key fields · diff        LLM (Groq / Gemini / Claude) or neural extractive QA      │
 │                                                        ▼                                          │
 │                                      grounding check ─► citations ─► confidence                   │
 │                                                                                                   │
 │  SQLite (users, sessions, documents, chunks, conversations, messages, citations, eval runs)      │
 │  FAISS IndexIDMap2(IndexFlatIP) + BM25 inverted index (in memory, persisted to disk)              │
 └───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 14. Technology Stack
| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, Uvicorn, Pydantic |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (384-d) on PyTorch (CPU) |
| Vector index | FAISS `IndexIDMap2(IndexFlatIP)` with `IDSelectorBatch` filtering |
| Sparse retrieval | BM25 (own implementation, Lucene IDF, ID-aware tokenizer, light stemmer) |
| Reranker | cross-encoder `ms-marco-MiniLM-L-6-v2` |
| OCR | RapidOCR (ONNX Runtime) + pypdfium2 page rendering |
| NLP | spaCy `en_core_web_sm` (NER) |
| Parsers | pypdf, python-docx, python-pptx, BeautifulSoup, pandas, openpyxl |
| LLM (optional) | Groq (Llama 3.1), Google Gemini, Anthropic Claude, with streaming |
| Database | SQLite (WAL mode) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Framer Motion, Recharts |
| Testing | pytest, FastAPI TestClient, Playwright (UI smoke test) |
| Deployment | Docker multi-stage build, docker-compose, one-command scripts |

---

## 15. Methodology
The work followed an iterative, measurement-driven cycle: **build → benchmark → analyse failures → fix the root cause → re-benchmark.**

Several design decisions in this report came directly from failure analysis on the benchmark:
- **Contextual chunk headers** fixed invoice line-item chunks that never mention the invoice number.
- **ID-family penalties** fixed confusion between near-duplicate IDs.
- **Two-signal abstention** fixed refusals of correctly retrieved paraphrased questions.
- **Header/footer removal** fixed answers polluted by running page headers.

## 16. Document Processing
Each file is converted into a list of typed *elements* (heading, paragraph, list, table, slide), each with a page number and a section:
- **PDF:** text per page via pypdf. Headings are detected with layout heuristics (numbered clauses, title/upper case; data rows and wrapped lines are rejected). Running headers and footers (lines repeated across pages, "Page N") are removed. Key-value lines are kept as separate lines while wrapped prose is re-flowed.
- **DOCX:** the document body is walked in order, so tables stay beside their section. Heading styles and bold-only paragraphs become headings.
- **HTML:** h1–h6, paragraphs, lists and tables; scripts, navigation and footers are removed.
- **CSV/XLSX:** a Markdown preview table, plus one natural-language *record* per row ("Record 3: SKU: NIM-SKU-1048; Quantity On Hand: 83; …"), grouped 5 records per chunk. XLSX sheets map to pages.
- **PPTX:** slide title, body text, tables and speaker notes; slide number becomes the page number.
- **Images:** OCR.
- **Integrity:** SHA-256 hash for duplicate detection. Re-uploading a changed file under the same name creates a new **version** linked to its parent.

## 17. OCR Pipeline
A PDF page with fewer than 30 characters of extractable text is treated as scanned. It is rendered at 2× scale with pypdfium2 and passed to RapidOCR (text detection → angle classification → CRNN recognition, all ONNX). The detected text boxes are sorted top-to-bottom and left-to-right and merged into lines. The benchmark contains an image-only PDF (IT security and visitor policy) whose question can only be answered through OCR.

## 18. Structure-Aware Chunking
- A new chunk starts at every heading, so a chunk never mixes two sections. Consecutive headings are merged instead of producing heading-only fragments.
- Tables are never split; a heading directly above a table becomes its caption.
- Text is packed sentence by sentence (abbreviation-aware splitting: "Pvt. Ltd.", "Rs. 500" and "3." do not end a sentence) up to 700 characters, with a 100-character overlap at word boundaries.
- Each chunk records its page, section and element type.
- **Contextual chunk header:** the embedding, BM25 and reranker inputs are prefixed with `"<document title> | <section>"`. Without this, a chunk such as an invoice's "Line Items" table (which never repeats the invoice number) cannot be found by an ID query.

The naive baseline used in the experiments cuts the concatenated text into fixed 700-character windows.

## 19. Embedding Generation
`all-MiniLM-L6-v2` maps text to 384-dimensional L2-normalised vectors, so the inner product equals cosine similarity. Chunks are encoded in batches of 32 on the CPU. A hashing-based fallback (word and character n-gram feature hashing) is used only if the model cannot load, and the UI labels it as such.

## 20. Vector Retrieval
FAISS `IndexIDMap2(IndexFlatIP)` gives exact search. Isolation is enforced *inside* the search: the IDs of the current user's chunks (optionally restricted to one domain or document) are passed as a FAISS `IDSelectorBatch`, so filtered search remains exact and another user's chunks can never be returned. Deleting a document removes its vectors with `remove_ids`. The index is persisted with a format version and rebuilt from SQLite if it is out of date.

## 21. BM25 Keyword Retrieval
$$\text{score}(q,d)=\sum_{t\in q}\text{idf}(t)\cdot\frac{tf_{t,d}(k_1+1)}{tf_{t,d}+k_1\left(1-b+b\frac{|d|}{\text{avgdl}}\right)},\quad \text{idf}(t)=\ln\!\left(1+\frac{N-df_t+0.5}{df_t+0.5}\right)$$
with $k_1=1.5$ and $b=0.75$.

The tokenizer keeps compound identifiers whole (`inv-2026-8842`) and also emits their parts. It removes stop words and applies a light suffix stemmer ("declaring/declared → declar"). An inverted index (postings lists) means only documents containing a query term are scored.

## 22. Hybrid Retrieval and Reciprocal Rank Fusion
The top 30 dense and top 30 BM25 results are fused:
$$\text{RRF}(d)=\sum_{r\in\{\text{dense},\,\text{bm25}\}}\frac{1}{k+\text{rank}_r(d)},\quad k=60$$
RRF uses only ranks, so the incompatible score scales of cosine similarity and BM25 need no normalisation. The fused score is divided by its maximum, $2/(k+1)$, to give a value in [0, 1].

## 23. Cross-Encoder Reranking
The top 20 fused candidates are scored by `ms-marco-MiniLM-L-6-v2`, which reads the (query, passage) pair jointly. The logit is mapped to [0, 1] with a sigmoid, and the top 5 passages are kept. A transparent lexical scorer (IDF-weighted query-term coverage) is the fallback.

## 24. Conversational Query Rewriting
For a follow-up question (pronouns, "what about…", "and for…", or very short questions), the previous user questions are used to build a standalone query:
- **With an LLM**, the LLM rewrites it, given the previous questions **and the previous answer** (citation markers removed, at most 600 characters). The answer is what pronouns usually refer to: after "Which vendor issued invoice INV-2026-8842?", the follow-up "What services did they provide?" becomes "What services did the vendor who issued invoice INV-2026-8842 provide?".
- **Offline**, a rule replaces the head noun phrase: "What about sick leave?" after "How many days of annual leave do employees get under the 2026 policy?" becomes "How many days of sick leave do employees get under the 2026 policy?". Other follow-ups get the previous question appended as context.

The rewritten query is stored and shown in the UI.

## 25. Answer Generation
**LLM mode.** The top 5 passages are numbered `[1]…[5]`, with file, page and section. The system prompt requires every statement to be cited, numbers and IDs to be quoted exactly, and the reply `INSUFFICIENT_EVIDENCE` when the answer is not in the sources. Tokens stream to the browser over Server-Sent Events.

**Offline neural extractive QA.** Every sentence (or table record) of the top 5 passages is scored by the cross-encoder, and the score is then adjusted:
1. **Expected answer type.** "How much / total / fee" questions expect money, "when / due date" questions expect a date, and "how many / how long / term" questions expect a number. Sentences without that type are down-weighted.
2. **Novelty.** Sentences that only repeat the question's own words are down-weighted.
3. **Identifier matching.** Sentences mentioning a *different* ID of the same family (`PO-2026-3371` when asked about `PO-2026-3317`) are strongly penalised.
4. **Passage rank prior.**

Comparison questions take the best sentence from each of the two most relevant documents. Up to three sentences are returned, each with its citation marker.

**Answer styles.** The user chooses how the answer is written; retrieval is identical in every style.
- **Quick answer** (default, and the style used by the benchmark): the prompt above, one to four cited sentences.
- **Detailed answer:** a second prompt asks for a one-sentence answer in bold followed by two to five bullet points with conditions, limits, exceptions and differences between documents or versions, using all retrieved passages; the same citation and refusal rules apply.
- **Exact quote:** the LLM is not used. The extractive selector returns the best sentences word for word as block quotes, each followed by its file and page. Because quotes cannot mix up documents, up to three documents that score within 60% of the best one are quoted (the 2025 *and* 2026 leave policies), with the best sentence of each document first.

**Questions in other languages.** A question is treated as non-English when it contains non-Latin letters (Devanagari, Tamil, …), several accented letters, or at least two distinctly Hindi words written in Latin letters (Hinglish: "chhutti kitne din milti hai?"). The LLM then translates it into a standalone English question (shown in the UI as "Understood as"); retrieval, answer generation, grounding verification and citation selection run unchanged in English; and finally the verified English answer is translated into the language and script of the question, keeping citation markers, numbers, names and IDs unchanged. Exact quotes stay word for word, with a translation underneath. This design keeps the English models (embeddings, cross-encoder, grounding check) valid instead of replacing them with weaker multilingual ones, at the cost of two extra LLM calls per question. Without an LLM such questions receive a message asking for English.

## 26. Citation System
Each citation records the document, file name, page, section, chunk ID, a snippet of up to 420 characters, the relevance score, and which search found it (by meaning, by exact words, or both). Only sources actually referenced by `[n]` markers in the answer are returned. In the UI, inline markers become chips; hovering a chip shows the snippet, and the source cards show relevance bars.

**Source viewer.** Clicking a citation opens the passage inside its original document (`backend/source_view.py`):
1. The supporting sentence is chosen among the sentences (or table rows) of the cited chunk: the one sharing the most words, and every number, with the answer sentences that cite this source.
2. For a PDF, the page is rendered to an image with pypdfium2, and the sentence is searched in the page's text layer after normalising whitespace, quotes and dashes (falling back to anchoring on its first or last five words). The boxes of the matched characters are merged into one rectangle per text line and returned as fractions of the page size, so the browser draws the highlight over the image at any zoom level. The cited page is searched first, then its neighbours.
3. For other formats (and scanned pages without a text layer) the cited chunk and its neighbours are shown as text with the sentence marked.

## 27. Grounding, Abstention and Confidence
- **Abstention (before generation)**, used when either condition holds:
  1. **Both** the top cross-encoder score is below 0.05 **and** the top dense similarity is below 0.40. Requiring both prevents refusing paraphrased questions that the cross-encoder under-scores.
  2. The question names a specific identifier, year or code (any token containing a digit, at least 3 characters long) that occurs nowhere in the retrieved passages or their titles. For example, "the 2027 leave policy" when only 2026 exists, or "Q4 FY2024-25".
- **Grounding (after generation):** each answer sentence is embedded and compared with every sentence of the retrieved passages. It counts as supported if the maximum cosine similarity is at least 0.72, or if lexical coverage is at least 0.8. The grounding score is the fraction of supported sentences; an answer is marked *grounded* if that fraction is at least 0.7.
- **Confidence** = 0.55 × top reranker score + 0.45 × grounding score.

## 28. Document Summarisation
- **With an LLM:** an abstractive JSON summary (overview, key points, conclusion).
- **Offline:** *centroid extractive summarisation*. Sentences are embedded; each is scored by cosine similarity to the document centroid plus a small lead bias; and Maximal Marginal Relevance (MMR, λ = 0.7) removes redundancy.

Section headings become the main topics. Dates and quantities with units or currency are extracted with patterns.

## 29. Named Entity Extraction
spaCy `en_core_web_sm` provides PERSON, ORG and GPE/LOC entities. Regular expressions provide dates, money (₹/Rs./INR/$), emails, Indian phone numbers, employee and contract IDs, and departments.

A cleaning step removes common statistical-NER errors: section headings detected as names, bare abbreviations (RCA, ECG) and generic nouns.

## 30. Key-Information Extraction
Contract, invoice and resume templates are filled by line-anchored patterns that tolerate labels with or without colons (as in PDF tables). The document type is detected automatically from keyword evidence.

**Fields that are not found are returned as `null`; values are never invented.** The previous version of this project returned placeholder values such as "INV-2026-001", which this design eliminates. When an LLM is configured, it fills only the missing fields, and each value is accepted **only if it occurs verbatim in the document**.

## 31. Document Comparison and Versioning
Both texts are split into sentences and aligned with `difflib.SequenceMatcher`. In replaced blocks, each old sentence is paired with its most similar new sentence (similarity ratio ≥ 0.55) to form a *modified clause*. Numbers in paired sentences are aligned to compute deltas, for example "18 → 20: +2 (+11%)". Year-only changes are ignored as noise, and clauses with substantive numeric changes are listed first. Added and removed clauses and dates are reported, together with an overall similarity percentage.

## 32. Database Design
| Table | Key columns |
|---|---|
| users | user_id (PK), username (unique), email (unique), password_hash, role |
| sessions | token_hash (PK), user_id (FK), expires_at |
| documents | doc_id (PK), user_id (FK), filename, file_type, file_hash, domain, page_count, chunk_count, tables_count, ocr_pages, version, parent_doc_id |
| chunks | chunk_id (PK), doc_id (FK, cascade), page_number, section, element_type, content |
| conversations | conversation_id (PK), user_id (FK), title, domain |
| messages | message_id (PK), conversation_id (FK), role (user/assistant), content, rewritten_query, retrieval_mode, grounded, grounding_score, confidence_score, latency_seconds, generation_mode, abstained, answer_style, feedback (1 helpful / −1 not helpful) |
| citations | citation_id (PK), message_id (FK), citation_number, doc_id, filename, page_number, section, source_snippet, relevance_score, found_by |
| evaluation_runs | run_id (PK), created_at, report_json |

Every user-data query includes `user_id` in its `WHERE` clause. Foreign keys cascade on delete.

## 33. API Design
The REST API is under `/api`, and the full specification is in `docs/API.md`. Interactive OpenAPI documentation is at `/api/docs`. Main groups:
- **Auth:** register, login (HTTP 429 with `Retry-After` while an account is locked), logout, me.
- **Documents:** upload, list, get, file download, versions, delete, summarize, entities, extract, compare, source-view.
- **Chat:** conversations CRUD, suggestions, query and query/stream (SSE) with an answer style, answer feedback.
- **System:** health, status, statistics, analytics (including answer feedback per style).
- **Evaluation:** dataset, run (administrators only), status, results, advanced results (baselines, confidence intervals, error analysis, multilingual).

Requests without a valid token receive 401. Accessing another user's resources returns 404, which avoids revealing that the resource exists.

## 34. User Interface Design
A single-page React application:
- **Login/Register:** split-screen hero and password strength meter. No credentials or password-less shortcut are shown; every account, including the demo account, signs in with its password.
- **Dashboard:** animated KPI tiles; charts for queries per day, confidence and grounding over time, documents by domain and format, and most-cited documents; live AI-component status; a "How DocuMind compares" card (the four systems' scores as bars with their 95% ranges, and DocuMind's lead over LangChain); and an answer-feedback card (share of helpful answers per answer style — administrators see all accounts, other users only their own). In the demo installation the feedback chart is filled with **sample ratings generated by `scripts/seed_feedback.py`**, not opinions of real users; they are therefore not reported as results.
- **Documents:** drag-and-drop multi-upload with per-file progress, grid/table views, filters, and a detail drawer with chunk explorer, version history, download and delete.
- **Chat:** conversation list (search, rename, delete), token streaming, citation chips with hover pop-ups, source cards that open the **source viewer** (the PDF page with the supporting sentence highlighted), confidence/grounding/latency badges, the rewritten or translated query ("Understood as"), scope selector (all, domain or single document), an **answer-style** selector (Quick answer, Detailed answer, Exact quote) with a one-line explanation of the chosen style, thumbs up/down, stop/regenerate/copy, and starter questions drawn from different documents. The placeholder invites questions "in any language".
- **Insights:** a short or detailed summary (the detailed one adds a section-by-section breakdown and a conclusion), entities ("People & places"), structured fields ("Key fields") and a comparison view with numeric-delta pills.
- **Evaluation:** opens with the comparison with standard approaches (three headline tiles — DocuMind's score, its lead over LangChain and whether the difference is significant — bars with 95% ranges switchable between all and held-out questions, and colour-scaled refusal, retrieval and source-backing scores); then the benchmark with live progress (run by administrators), comparison table, grouped bars, radar, ablation deltas and per-category charts. The error analysis and the multilingual results (sections 38.6–38.7) are kept in this report and in `evaluation/results/advanced_eval.md` rather than in the interface.
- **Settings:** account, theme and an animated pipeline diagram.
- **Administration** (admin role only): system-wide dashboard, user management (roles, suspension, password reset, sign-out, deletion), every document and a read-only view of every conversation.

The app has dark and light themes, a Ctrl+K command palette and a mobile drawer layout.

**Plain-language labels.** The interface is written for non-specialists: metrics and components are named by what they mean ("Found in top 5", "Backed by sources", "Without keyword search", "Found by meaning / exact match", "Written by AI" or "Quoted from your documents"), and the technical term (Recall@5, grounding score, BM25 ablation, dense/BM25 retrieval, LLM or extractive generation) is shown on hover. This report uses the technical terms.

**Why answer styles instead of search modes in the chat.** An earlier version let users pick the retrieval method (hybrid, dense or BM25). In practice all three gave the same answer to most questions, because every mode passes its top 20 candidates to the same cross-encoder: on 12 random benchmark questions, 8 produced identical answers and the other 4 differed only where dense search alone missed an exact ID. The control looked broken to users, so the chat now always uses hybrid search and offers answer styles, which visibly change the answer while keeping it accurate. The retrieval comparison remains available as the ablation study.

## 35. Testing
| Suite | Tests | Covers |
|---|---|---|
| `tests/test_unit.py` | 32 | Tokenizer, BM25 exact-ID ranking, RRF bounds, vector-store isolation and deletion, section-bounded chunking, intact tables, fixed-size baseline, table-row sentences, query rewriting (including with the previous answer), password hashing, extraction returning null (no invention), numeric deltas, dates, metric arithmetic (MRR, nDCG ≤ 1), keyword matching; language detection and translate–verify–translate answering (with a fake LLM); answer styles and quoting several documents; which search found each citation; diverse starter questions; Wilson intervals, the McNemar test, failure categories, baseline refusal detection, Hinglish reply detection, and the Groq quota guard and its cache |
| `tests/test_api.py` | 30 | 401s; registration validation; login/logout invalidation; no password-less login; ingestion of all 8 formats; OCR of an image; PDF page and section tracking; duplicate, unsupported, empty and corrupt uploads; versioning and comparison; cited answers; follow-up rewriting; tabular QA; abstention; document-scoped QA; SSE streaming; **cross-user isolation**; **deletion removes a document from search**; intelligence endpoints; analytics; **administrator role**; source viewer (PDF highlight boxes, text formats, other users get 404); owner-only answer feedback; **account lock-out**, the 8-character rule, security headers, administrator-only benchmark runs and **random initial passwords** |

**Result: 62 of 62 tests pass** with the lightweight fallback models (about 20 s), and **62 of 62 pass with the real neural models** (`ENABLE_NEURAL_MODELS=true`, about 90 s). The new features were additionally checked end to end against the running application with the real models and LLM (15 of 15 live checks). A Playwright script additionally drives the built UI in Microsoft Edge against the real backend (login, dashboard, documents drawer, insights, evaluation, settings, and a streamed chat answer with citations) and records zero console errors and zero failed API calls.

## 36. Evaluation Dataset
**Corpus:** 200 synthetic but realistic documents from ten fictional Indian organisations, **20 per organisation**: Helix Systems (a software company with its contracts, HelixDesk product documents and financial reports), Silverleaf Multispeciality Hospital (healthcare), Tejas Infrastructure, Orion Softworks, Brightpath Consulting, Zenith Retail, Aster Logistics, Meridian Capital, Cobalt Cloud Services and Lumen Insurtech.
- 50 hand-written documents (`scripts/generate_sample_data.py`) plus 150 generated ones (`scripts/corpus_expansion.py`): invoices, purchase orders, offer letters, payslips, HR policies, NDAs, service agreements, leases, meeting minutes, project decks, stock registers, incident reports, revenue sheets, training decks, and discharge summaries, lab reports, prescriptions, radiology reports, OPD rosters and SOPs for the hospital.
- Formats: 49 PDF (1 scanned image-only), 53 DOCX, 11 TXT, 15 Markdown, 16 HTML, 19 CSV, 14 XLSX, 23 PPTX. Each organisation's files are rendered in its own colour theme.
- Related documents always belong to the same organisation. Every generated document has unique identifiers and people, so each generated question has exactly one correct source, while the many look-alike documents (about 18 invoices, 10 NDAs, 9 payslips...) act as realistic retrieval distractors.

The corpus deliberately contains **version pairs** (Leave Policy 2025/2026, MSA v1/v2) and **near-duplicate identifiers** (INV-2026-8842/8824, CNT-2026-9941/9914/9491, PO-2026-3317/3371, PAT-55102/55120).

**Questions (156):** 50 hand-written plus 106 generated together with their documents.

| Category | Count | What it tests |
|---|---|---|
| factual | 52 | direct look-ups |
| paraphrase | 24 | the question avoids the document's words (semantic retrieval) |
| exact_id | 32 | the question hinges on an identifier among many look-alike documents |
| tabular | 28 | the answer is a table cell (CSV/XLSX/PDF table) |
| multi_doc | 3 | the answer needs two documents |
| followup | 4 | an elliptical question that needs the conversation history |
| ocr | 1 | the answer exists only in a scanned page |
| unanswerable | 12 | plausible but not in the corpus |

Each question lists its expected documents, expected page, required answer keywords and a reference answer. Automated checks confirmed that every keyword appears in an expected document, that every identifier in a generated question occurs in exactly one document, and that the distinctive phrase of every unanswerable question occurs in no document.

**Dev / test split.** Odd-numbered questions form the *dev* set used to tune the answer-selection and abstention rules; even-numbered questions form the *test* set, which was never inspected during tuning. Both scores are reported.

## 37. Evaluation Metrics
For each answerable question, let $R$ be the set of relevant documents and $D=(d_1,\dots,d_n)$ the de-duplicated documents of the top 5 retrieved chunks.
- **Recall@k** $=|R\cap D_{1..k}|/|R|$
- **MRR** $=1/\text{rank of the first relevant document}$ (0 if none)
- **nDCG@5** $=\dfrac{\sum_{i\le5,\,d_i\in R}1/\log_2(i+1)}{\sum_{i\le\min(|R|,5)}1/\log_2(i+1)}$. Each document counts once, so the value is always ≤ 1. The previous report's value of 123% came from counting the same document several times, and is fixed here.
- **Answer correctness:** answerable questions are correct if the system did not abstain and all reference keywords appear in the answer; unanswerable questions are correct if the system abstained.
- **Faithfulness:** mean grounding score of non-abstained answers.
- **Citation accuracy:** fraction of non-abstained answers that cite at least one relevant document.
- **Abstention accuracy:** fraction of all questions where *abstained* equals *unanswerable*.
- **Latency:** median and 95th-percentile end-to-end time per question on a laptop CPU, measured on a fixed sample of 24 questions per configuration. To keep the benchmark fast, cross-encoder scores and embeddings are remembered between configurations (both models are deterministic, so no accuracy figure changes); the latency sample is therefore timed separately with this memory switched off. The search index is cached on disk and rebuilt only when a document or the chunking code changes. A full run takes about 15 minutes instead of about an hour.

For reproducibility and fair comparison, all configurations use the deterministic offline extractive generator (no LLM).

## 38. Experimental Results

Run: 2026-10-24T19:15:53 · 156 questions · 200 documents · embedding `all-MiniLM-L6-v2` · reranker `ms-marco-MiniLM-L-6-v2` · CPU only · generation: deterministic extractive (no LLM). *Correct (held-out test)* is answer correctness on the even-numbered questions that were not used for tuning.

### 38.1 Incremental systems

| Configuration | R@1 | R@5 | MRR | nDCG@5 | Answer correct | Correct (held-out test) | Citation acc. | Abstention acc. | Median latency |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1. Naive RAG | 80.9% | 93.8% | 0.874 | 89.0% | 74.4% | 67.9% | 91.7% | 92.3% | 0.807s |
| 2. + Structure-aware chunking | 83.0% | 93.8% | 0.883 | 89.7% | 69.9% | 70.5% | 88.2% | 92.3% | 0.177s |
| 3. + Hybrid retrieval | 92.0% | 97.9% | 0.954 | 96.0% | 80.1% | 75.6% | 95.1% | 92.3% | 0.188s |
| 4. + Cross-encoder reranking | 95.5% | 99.3% | 0.978 | 98.2% | 84.0% | 79.5% | 97.2% | 92.3% | 0.915s |
| **5. Full system** | 97.6% | 100.0% | 0.992 | 99.4% | 90.4% | 83.3% | 99.3% | 95.5% | 0.906s |

### 38.2 Ablation study (one component removed from the full system)

| Configuration | R@1 | R@5 | MRR | nDCG@5 | Answer correct | Correct (held-out test) | Citation acc. | Abstention acc. | Median latency |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Full system** | 97.6% | 100.0% | 0.992 | 99.4% | 90.4% | 83.3% | 99.3% | 95.5% | 0.906s |
| w/o BM25 | 96.2% | 99.3% | 0.981 | 98.4% | 85.9% | 79.5% | 99.3% | 93.6% | 0.865s |
| w/o dense retrieval | 97.6% | 99.3% | 0.99 | 99.0% | 86.5% | 80.8% | 100.0% | 92.3% | 0.801s |
| w/o reranker | 94.1% | 99.3% | 0.971 | 97.7% | 80.8% | 75.6% | 97.2% | 92.3% | 0.191s |
| w/o query rewriting | 95.5% | 99.3% | 0.978 | 98.2% | 89.1% | 82.1% | 97.1% | 95.5% | 0.884s |
| w/o abstention | 97.6% | 100.0% | 0.992 | 99.4% | 85.3% | 80.8% | 99.3% | 92.3% | 0.901s |
| w/o structure-aware chunking | 96.9% | 100.0% | 0.99 | 99.2% | 84.0% | 78.2% | 99.3% | 93.6% | 1.602s |

### 38.3 Full system by question category

| Category | Questions | Recall@5 | Answer correct |
|---|:---:|:---:|:---:|
| factual | 52 | 100.0% | 92.3% |
| paraphrase | 24 | 100.0% | 79.2% |
| exact_id | 32 | 100.0% | 96.9% |
| tabular | 28 | 100.0% | 100.0% |
| multi_doc | 3 | 100.0% | 66.7% |
| followup | 4 | 100.0% | 75.0% |
| ocr | 1 | 100.0% | 0.0% |
| unanswerable | 12 | n/a | 83.3% |

*Recall is not defined for unanswerable questions, because they have no relevant document. Faithfulness was 100.0% in every configuration and is omitted from the tables (see 39.7). Raw per-question output, including every answer, is in `evaluation/results/latest.json`.*


<!-- llm-comparison:start -->
### 38.4 Offline extractive answers vs an LLM

Run: 2026-10-24T17:47:52 · full system · 156 questions · answers written by `qwen/qwen3.8-27b` (Groq) instead of the extractive generator.

| Answer generator | Correct answers | Correct (held-out test) | Faithfulness | Citation acc. | Abstention acc. | Recall@1 | Median latency |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Offline extractive (no LLM) | 90.4% | 83.3% | 100.0% | 99.3% | 95.5% | 97.6% | 1.461s |
| LLM: `qwen/qwen3.8-27b` on Groq | 95.5% | 93.6% | 98.5% | 100.0% | 95.5% | 96.9% | 2.892s |

| Question type | Questions | Offline | With LLM |
|---|:---:|:---:|:---:|
| Direct facts | 52 | 92.3% | 100.0% |
| Reworded questions | 24 | 79.2% | 79.2% |
| ID look-ups | 32 | 96.9% | 96.9% |
| Table values | 28 | 100.0% | 96.4% |
| Two documents | 3 | 66.7% | 100.0% |
| Follow-ups | 4 | 75.0% | 100.0% |
| Scanned page (OCR) | 1 | 0.0% | 100.0% |
| Not in documents (refused) | 12 | 83.3% | 100.0% |

<!-- llm-comparison:end -->

### 38.5 Comparison with standard approaches

Run: 2026-11-16 · `python evaluation/run_advanced.py` · the same 156 questions and 200 documents · every system that uses an LLM uses the same one (`qwen/qwen3.8-27b` on Groq, temperature 0.1). Raw output: `evaluation/results/advanced_eval.json`.

Baselines:
- **LLM only:** the question alone, with the instruction to answer concisely or say it does not know.
- **Standard RAG (LangChain):** the textbook pipeline — LangChain `RecursiveCharacterTextSplitter` (1,000 characters, 200 overlap), the same MiniLM embeddings, top-4 cosine retrieval and LangChain's standard RAG prompt (`rlm/rag-prompt`). It reads exactly the same extracted text as DocuMind, so the comparison isolates the pipeline (chunking, hybrid search, reranking, refusal rules, prompting and verification) from document parsing.

A baseline answer that says it does not know is counted as a refusal. Intervals are 95% Wilson score intervals.

| System | Correct (95% CI) | Held-out test (95% CI) | Abstention acc. | Recall@1 | Faithfulness |
|---|:---:|:---:|:---:|:---:|:---:|
| LLM only (no documents) | 9.6% (5.9–15.3) | 9.0% (4.4–17.4) | 9.6% | – | – |
| Standard RAG (LangChain) | 82.7% (76.0–87.8) | 78.2% (67.8–85.9) | 84.0% | 77.4% | 91.3% |
| DocuMind, offline (no LLM) | 90.4% (84.7–94.1) | 83.3% (73.5–90.0) | 95.5% | 97.6% | 100.0% |
| **DocuMind + LLM** | **95.5% (91.0–97.8)** | **93.6% (85.9–97.2)** | 95.5% | 96.9% | 100.0% |

Paired significance (exact McNemar test on the questions one system answered correctly and the other did not):

| Comparison | Only DocuMind + LLM correct | Only the other correct | p |
|---|:---:|:---:|:---:|
| vs Standard RAG (LangChain) | 25 | 5 | 0.0003 |
| vs LLM only | 135 | 1 | < 0.001 |
| vs DocuMind offline | 9 | 1 | 0.021 |

(Recall for LangChain is measured over its 4 retrieved passages, for DocuMind over 5. The DocuMind offline row reproduces section 38.1 exactly, and the DocuMind + LLM row has the same correctness as section 38.4, this time with every answer written by the LLM — a quota guard waited out rate limits instead of falling back to the offline generator.)

### 38.6 Error analysis

Every wrong answer is assigned to exactly one cause: the right document was not among the retrieved passages; the right document was found but the answer was wrong or incomplete; the system refused although the documents contain the answer; or it answered a question the documents cannot answer.

| Failure type | DocuMind + LLM | DocuMind offline | Standard RAG (LangChain) |
|---|:---:|:---:|:---:|
| Wrong document found | 0 | 0 | 1 |
| Right document, wrong or incomplete answer | 0 | 8 | 1 |
| Wrongly refused | 7 | 5 | 25 |
| — of which the right document had been found | 7 | 5 | 10 |
| Answered when it should have refused | 0 | 2 | 0 |
| **Total wrong (of 156)** | **7** | **15** | **27** |

### 38.7 Questions in other languages

Thirty benchmark questions (`evaluation/multilingual_dataset.json`) were re-asked in Hindi (15, Devanagari script) and Hinglish (15, Hindi in Latin letters): 26 answerable ones spanning facts, paraphrases, exact IDs, tables and a two-document comparison, and 4 that must be refused. Each is scored with the reference keywords of its English original, on the verified English answer; the answer shown to the user is additionally checked for being in the question's language and for keeping every number unchanged.

| Language | Questions | Correct (95% CI) | Same questions in English | Replied in same language | Numbers kept exact |
|---|:---:|:---:|:---:|:---:|:---:|
| Hindi | 15 | 100% (79.6–100) | 93.3% | 100% | 100% |
| Hinglish | 15 | 100% (79.6–100) | 100% | 100% | 100% |
| All | 30 | 100% (88.6–100) | 96.7% | 100% | 100% |

## 39. Discussion and Performance Analysis

**39.1 Overall.** Going from naive RAG to the full system raised answer correctness from **74.4% to 90.4%** (+16.0 points) and, on the held-out test half, from 67.9% to **83.3%**. Recall@1 rose from 80.9% to 97.6%, MRR from 0.874 to 0.992, and nDCG@5 from 89.0% to 99.4%. All ranking metrics are correctly bounded at 100%.

**39.2 Answer selection was the bottleneck.** The first run on the 200-document corpus (before the changes below) already had Recall@5 of 100% and MRR of 0.992, yet only **64.1%** of answers were correct. Error analysis showed that the extractive generator mixed sentences from look-alike documents (the "Total amount payable" lines of three *other* invoices), preferred fluent sentences that restate the question over terse table rows ("Total net pay 129,560" scored 0.017 by the cross-encoder against 0.98 for the payslip's title), and treated the digits of identifiers as amounts. Four changes, tuned on the dev half only, fixed this:
1. **Document anchoring:** a non-comparative question is answered from one document, the one containing the identifier the question names, otherwise the top-ranked one.
2. **Type-first selection:** when the question expects an amount, a date, a company or a cause, only sentences containing one are considered (identifiers are stripped first).
3. **Field matching:** sentences sharing the question's content words are preferred ("billed" matches "Bill to"), and lines that only restate the question or the document title are penalised.
4. **Coverage-based abstention:** the system abstains when at least two key terms of the question (at least 40% of them) are absent from the evidence and the best dense similarity is below 0.60.

Together they raised the full system from 64.1% to 90.4% overall and 83.3% on held-out questions, and citation accuracy from 86.8% to 99.3%. Because they act at the answer stage, they also help the simpler configurations (naive RAG went from 44.2% to 74.4%).

**39.3 Hybrid retrieval.** Adding BM25 with RRF to dense retrieval (system 2 → 3) improved Recall@1 by +9.0 points and answer correctness by +10.2. Each retriever covers the other's blind spot:
- Removing BM25 from the full system costs 4.5 points of answer correctness, because identifiers such as INV-ORN-4198 need exact token matching among many look-alike documents.
- Removing dense retrieval costs 3.9 points and lowers abstention accuracy to 92.3%, because the abstention rules lose their semantic signal.

**39.4 Cross-encoder reranking** (system 3 → 4) lifts Recall@1 from 92.0% to 95.5% and answer correctness by +3.9 points. Removing it from the full system is the **most damaging ablation** (9.6 points), because the reranker scores both passages and candidate answer sentences. It is also the main latency cost on CPU.

**39.5 Structure-aware chunking.** On its own with dense-only retrieval (system 1 → 2) it improves Recall@1 (80.9% → 83.0%) but lowers answer correctness (74.4% → 69.9%), because small section-bounded chunks give the naive extractor less surrounding text. Inside the full pipeline, however, removing it costs 6.4 points: clean, section-labelled chunks give the reranker and the answer selector coherent units, whereas fixed windows cut sentences and table records in half. **The value of a component depends on the rest of the pipeline**, which is why ablations from the full system are reported alongside the incremental build-up.

**39.6 Query rewriting and abstention.**
- Without rewriting, answer correctness drops 1.3 points and Recall@1 falls to 95.5%: elliptical follow-ups such as "What about sick leave?" retrieve the wrong context.
- Abstention adds 5.1 points. 83.3% of unanswerable questions are now refused (the missing-identifier check catches "2027 policy"-style questions; the coverage rule catches "pets", "canteen menu", "share price"), at the cost of refusing a few paraphrased answerable questions whose wording differs from the documents.

**39.7 Faithfulness** is 100% in every configuration because the offline generator *extracts* sentences from the retrieved passages, so every answer sentence is supported by construction. The metric becomes informative when an LLM generates free text. The grounding check is designed for that case, and the LLM path was verified separately with a mock LLM server.

**39.8 Error analysis by category.**
- Retrieval reached 100% Recall@5 in every answerable category, so **the remaining errors are in answer selection and abstention, not retrieval.**
- Tabular (100.0%), exact-ID (96.9%) and factual (92.3%) questions are now answered reliably.
- Paraphrased questions (79.2%) remain the hardest: either the coverage rule refuses them because their words are not in the document, or the selector picks a neighbouring tier ("below 99%" instead of "below 95%"). These need semantic reasoning, which is the strongest case for adding an LLM.
- The dev/test gap (97.4% vs 83.3%) is concentrated in paraphrases and shows that the coverage rule is somewhat fitted to the dev questions; the held-out figure is the one to quote.

**39.9 Latency.** The full system answers in 0.906 s typically (median; 4.091 s at the 95th percentile) on a laptop CPU, with no GPU. Most of the time is cross-encoder inference over 20 passages plus the candidate sentences. A GPU, or a smaller reranking pool, would cut this substantially.


<!-- llm-comparison:start -->
**39.10 Adding an LLM.** With the same retrieval, letting `qwen/qwen3.8-27b` write the answer raises correctness on the held-out questions from 83.3% to **93.6%** (90.4% to 95.5% overall). The extractive generator can only quote one sentence, so it fails when the answer must be assembled from two documents, a follow-up, an OCR page, or when a passage is related but does not actually answer the question; the LLM handles all of these, and correctly refused every unanswerable question. Reworded questions do not improve (79.2%) because the coverage rule refuses some of them before the LLM is called. Faithfulness is 98.5% under a claim-level check (every number, date and identifier in the answer must occur in the sources); an earlier sentence-similarity check reported only 71.9% because it rejected correct answers that restate a table row as prose, which manual inspection of all 39 flagged answers confirmed. The LLM roughly doubles the median latency (1.461 s to 2.892 s) and needs an internet connection; without one the system falls back to the offline generator automatically (3.6% of answers did so here because of free-tier rate limits).

<!-- llm-comparison:end -->

**39.11 Against standard approaches.** With the same LLM and the same extracted text, DocuMind is right on 25 questions the standard LangChain pipeline gets wrong and wrong on only 5 it gets right (p = 0.0003), so the improvement comes from the pipeline and is not chance. The error analysis shows where LangChain loses: almost every one of its 27 errors is a refusal, and in 15 of them the right document was never retrieved — mainly table rows and exact identifiers (11 tabular and 6 exact-ID questions among its 25 refusals), which fixed-size character chunks and dense-only search handle poorly and which DocuMind's row-level records, ID-aware BM25 and reranking were designed for. Its Recall@1 is 77.4% against DocuMind's 96.9%. To LangChain's credit, its LLM refused rather than invented an answer when the context lacked one, so its errors are safe ones.

**39.12 The LLM alone.** Without documents the LLM answered only 9.6% correctly, almost entirely the questions that should be refused: it said it did not know for 141 of the 144 answerable questions and invented no answers. This is the expected result for private documents and is the clearest argument for retrieval; it also shows that the model used is honest rather than hallucination-prone, so DocuMind's measured faithfulness is not an artefact of a careless generator.

**39.13 What remains.** All 7 errors of DocuMind + LLM are refusals of answerable questions where the right document *had* been found. The system never found a wrong document, never gave a wrong answer and never answered an unanswerable question. Its weaknesses are therefore all on the side of caution, and the refusal rule (section 27, mainly the coverage check on reworded questions) is the single component to improve next — for example by letting the LLM, which already refuses on its own with `INSUFFICIENT_EVIDENCE`, take over the borderline cases.

**39.14 Other languages.** All 30 Hindi and Hinglish questions were answered correctly — one more than their English originals, because the translation produced clearer wording for one question: the English original "How much refundable money did we hand over to the landlord…?" is refused, while its Hindi version was understood as "How much refundable amount did we pay to the landlord…?" and answered correctly — a reminder that the remaining refusals are sensitive to wording. Every answer came back in the language and script of the question with all numbers intact. With 15 questions per language the 95% intervals are wide (79.6–100%), so the result shows that the translate–verify–translate design works, not that its accuracy is exactly 100%; the questions were translated for this project and should be reviewed by a native speaker before being cited.

## 40. Limitations
- **Offline, answers are extracted sentences.** Questions requiring inference across sentences fail. For example, "Who is the CEO of Zenvia?" retrieves a sentence naming a "Designated Partner", and "current share price" retrieves related financial text. These are also the unanswerable questions the system cannot detect without semantic reasoning.
- **Rule tuning.** The answer-selection and abstention rules were tuned on the dev half of the benchmark; the held-out test half scores 83.3% versus 97.4% on dev, so some over-fitting remains (mainly the coverage-based abstention on paraphrased questions).
- **Synthetic corpus.** The benchmark corpus is synthetic (though realistic) and 106 of the 156 questions are template-generated; with 78 held-out questions, one question is about 1.3 percentage points.
- **Language and OCR.** Documents must be in English. Questions in other languages need an LLM (it does the translation) and cost three LLM calls instead of one; the 30-question multilingual benchmark is small and its translations are not yet reviewed by a native speaker. OCR quality drops on low-resolution or handwritten scans.
- **Free-tier LLM limits.** The free Groq tier allows 1,000 requests and 200,000 tokens per day; the advanced evaluation needed two days, and heavy use of the live system makes it fall back to offline answers until the allowance frees up.
- **In-memory protection.** Login lock-outs and sign-up limits are kept in memory, so they reset on restart and do not span several server processes.
- **Single-node deployment.** The FAISS flat index is exact but scales linearly; very large corpora would need an IVF/HNSW index.

## 41. Future Scope
- Let the LLM decide borderline refusals, the only remaining error type (section 39.13), and add an LLM judge (RAGAS-style) for faithfulness.
- Evaluate on real-world documents with questions written by people who have not seen the system.
- Multilingual embeddings (e.g. `multilingual-e5`) so questions in Hindi and other Indian languages also work offline, and support for non-English documents.
- Vision-language models for charts, figures and handwriting.
- GraphRAG (entity graphs) for multi-hop questions.
- Approximate-nearest-neighbour indexes (HNSW), background ingestion queues and horizontal scaling.
- SSO/OAuth2, role-based sharing of document collections, and audit logs.

## 42. Conclusion
DocuMind is a complete, tested and measured document intelligence system.
- **Ingestion:** eight formats, including scanned documents.
- **Retrieval:** structure-aware, contextual chunks; hybrid dense + sparse search with rank fusion and cross-encoder reranking.
- **Answers:** citations to the page and passage, sentence-level grounding checks, and abstention when evidence is missing or the question asks about something not in the corpus.
- **Intelligence:** summaries, entities, key fields and version comparison, delivered through a secure multi-user web application.

- **Usability:** answer styles, questions in Hindi, Hinglish and other languages, a source viewer that highlights the supporting sentence on the original page, and answer feedback.

The benchmark shows quantitatively how each design choice contributes, and the failure analysis drove several of the most effective techniques. With the same LLM, DocuMind answers 95.5% of the benchmark correctly against 82.7% for a standard LangChain pipeline (p = 0.0003), and all of its remaining errors are cautious refusals rather than wrong answers. The system runs entirely on a laptop CPU without any paid service, and switches to LLM-generated answers when an API key is provided.

## 43. References
1. P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," *NeurIPS*, 2020.
2. S. Robertson and H. Zaragoza, "The Probabilistic Relevance Framework: BM25 and Beyond," *Foundations and Trends in IR*, 3(4), 2009.
3. N. Reimers and I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," *EMNLP*, 2019.
4. J. Johnson, M. Douze and H. Jégou, "Billion-scale similarity search with GPUs," *IEEE Trans. Big Data*, 2019.
5. G. V. Cormack, C. L. A. Clarke and S. Büttcher, "Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods," *SIGIR*, 2009.
6. R. Nogueira and K. Cho, "Passage Re-ranking with BERT," arXiv:1901.04085, 2019.
7. Y. Gao et al., "Retrieval-Augmented Generation for Large Language Models: A Survey," arXiv:2312.10997, 2023.
8. S. Es et al., "RAGAS: Automated Evaluation of Retrieval Augmented Generation," arXiv:2309.15217, 2023.
9. K. Järvelin and J. Kekäläinen, "Cumulated Gain-Based Evaluation of IR Techniques," *ACM TOIS*, 20(4), 2002.
10. J. Carbonell and J. Goldstein, "The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries," *SIGIR*, 1998.
11. Anthropic, "Introducing Contextual Retrieval," 2024.
12. M. Honnibal et al., "spaCy: Industrial-strength Natural Language Processing in Python," 2020.
