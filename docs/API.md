# REST API Reference

Base URL: `http://localhost:8000/api` (the built frontend is served from `http://localhost:8000/`).

All endpoints except `/auth/register`, `/auth/login`, `/health` and `/system/status`
require `Authorization: Bearer <token>`. Missing/invalid tokens return **401**. Accessing another
user's document or conversation returns **404**.

Domains: `general`, `hr`, `legal`, `healthcare`, `finance`. Query endpoints also accept `all`.

## Shared shapes

```ts
User = { user_id: string; username: string; email: string; role: "user" | "admin"; created_at: string }

Document = {
  doc_id: string; filename: string; file_type: string /* ".pdf" */; file_size: number;
  domain: string; page_count: number; chunk_count: number; tables_count: number; ocr_pages: number;
  version: number; parent_doc_id: string | null; status: "indexed" | "failed";
  uploaded_at: string /* ISO */
}

Chunk = {
  chunk_id: string; doc_id: string; chunk_index: number; page_number: number;
  section: string; element_type: "heading" | "paragraph" | "list" | "table" | "slide" | "text";
  content: string; char_count: number; token_count: number
}

Citation = {
  citation_number: number; doc_id: string; filename: string; page_number: number;
  section: string; chunk_id: string; source_snippet: string; relevance_score: number /* 0..1 */
}

Message = {
  message_id: string; conversation_id: string; role: "user" | "assistant";
  content: string;                    // question text for user, answer text (markdown, with [n] markers) for assistant
  rewritten_query: string | null; citations: Citation[];
  grounded: boolean; grounding_score: number; confidence_score: number;
  latency_seconds: number; model_name: string | null;
  generation_mode: string | null;     // e.g. "llm:groq/qwen/qwen3.8-27b" or "extractive:cross-encoder"
  abstained: boolean; timestamp: string
}

Conversation = { conversation_id: string; title: string; domain: string; created_at: string; updated_at: string; message_count: number }
```

## Auth
| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/register` | `{username, email, password}` (password ≥ 8 chars; 429 after repeated sign-ups from one address) | `{user, token}` · 400 if taken |
| POST | `/auth/login` | `{username, password}` (username or email) | `{user, token}` · 401 · 403 if suspended · 429 (with `Retry-After`) for 15 min after 5 wrong passwords |
| POST | `/auth/logout` | – | `{ok: true}` |
| GET | `/auth/me` | – | `{user}` |

## System
| Method | Path | Response |
|---|---|---|
| GET | `/health` | `{status: "online", version}` |
| GET | `/system/status` | `{embedding: {model, type: "neural"\|"hashing", dimension}, reranker: {model, type: "cross-encoder"\|"lexical"}, llm: {provider, model, available}, ocr: {available, engine}, vector_index: "faiss"\|"numpy", supported_formats: string[]}` |
| GET | `/statistics` | `{total_documents, total_chunks, total_conversations, total_questions, avg_confidence, avg_latency, grounded_rate, abstention_rate, by_domain: {[d]: n}, by_format: {[ext]: n}, recent_documents: Document[]}` |
| GET | `/analytics` | `{queries_per_day: [{date, count}], confidence_history: [{timestamp, confidence, grounding, latency}], top_documents: [{filename, citations}], retrieval_modes: {[mode]: n}, latency_histogram: [{bucket, count}], feedback: {helpful, not_helpful, rated, answers, satisfaction, by_style: [{style, answers, helpful, not_helpful}]}}` |

## Documents
| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/documents/upload` | multipart: `files` (1..n), `domain` | `{processed: Document[], duplicates: [{filename, existing_doc_id}], errors: [{filename, error}]}` |
| GET | `/documents?domain=&search=` | – | `{documents: Document[], total}` |
| GET | `/documents/{id}` | – | `{document, chunks: Chunk[]}` |
| GET | `/documents/{id}/file` | – | original file (download) |
| GET | `/documents/{id}/versions` | – | `{versions: Document[]}` (same filename, oldest first) |
| DELETE | `/documents/{id}` | – | `{ok: true}` (removed from DB, vector index and BM25 index) |
| POST | `/documents/{id}/summarize` | `{summary_type: "short"\|"detailed"}` | `{doc_id, filename, summary: {overview, key_points: string[], main_topics: string[], important_dates: string[], important_numbers: string[], conclusion, method}}` |
| POST | `/documents/{id}/entities` | – | `{doc_id, filename, entities: {Person, Organization, Location, Date, Money, Email, Phone, "Employee ID", "Contract ID", Department: string[]}, method}` |
| POST | `/documents/{id}/extract` | `{document_type: "auto"\|"contract"\|"invoice"\|"resume"}` | `{doc_id, filename, structured_data: {document_type, fields: {[name]: string \| string[] \| null}, method}}` — `null` means not found (never invented) |
| POST | `/documents/{id}/source-view` | `{chunk_id?, page_number?, focus /* answer text citing it */}` | PDF: `{kind: "pdf", page_number, page_count, aspect_ratio, image /* PNG data URL */, boxes: [{x, y, w, h} /* fractions of the page */], highlights: string[], found}`; other formats: `{kind: "text", chunks: [{chunk_id, section, page_number, content, cited}], highlights, found}` |
| POST | `/documents/compare` | `{doc_id_a, doc_id_b}` | `{label_a, label_b, similarity_score /* 0..100 */, added_count, removed_count, modified_count, added_clauses: string[], removed_clauses: string[], modified_clauses: [{from_text, to_text, deltas: [{original_value, new_value, change_delta}]}], new_dates: string[], removed_dates: string[]}` |

## Chat
| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/conversations` | – | `{conversations: Conversation[]}` |
| POST | `/conversations` | `{title?, domain?}` | `Conversation` |
| GET | `/conversations/{id}` | – | `{conversation, messages: Message[]}` |
| PATCH | `/conversations/{id}` | `{title}` | `Conversation` |
| DELETE | `/conversations/{id}` | – | `{ok: true}` |
| GET | `/suggestions?domain=` | – | `{questions: string[]}` |
| POST | `/query` | `{question /* any language */, conversation_id?, domain = "all", doc_id?, retrieval_mode = "hybrid"\|"semantic"\|"bm25", answer_style = "quick"\|"detailed"\|"quote"}` | `{conversation_id, user_message: Message, assistant_message: Message}` |
| POST | `/messages/{id}/feedback` | `{rating: 1 \| -1 \| 0 /* clears */}` (only the person who asked) | `{message: Message}` · 404 otherwise |
| POST | `/query/stream` | same as `/query` | Server-Sent Events (see below) |

`/query/stream` emits, in order:
- `event: meta` · `data: {conversation_id, user_message: Message, rewritten_query, citations: Citation[]}`
- `event: token` · `data: {text}` (repeated; concatenate to build the answer)
- `event: done` · `data: {assistant_message: Message}` (final authoritative message)
- `event: error` · `data: {detail}` on failure

## Evaluation
| Method | Path | Response |
|---|---|---|
| GET | `/evaluation/dataset` | the benchmark JSON (`{benchmark_metadata, test_cases}`) |
| POST | `/evaluation/run` | `{status: "running"}` (administrators only, 403 otherwise; runs in background; 409 if already running) |
| GET | `/evaluation/status` | `{status: "idle"\|"running"\|"done"\|"error", progress: 0..1, message}` |
| GET | `/evaluation/results` | `{latest: EvalReport \| null}` |
| GET | `/evaluation/advanced` | `{report: AdvancedReport \| null}` — baselines, 95% confidence intervals, McNemar tests, error analysis and the multilingual benchmark (`python evaluation/run_advanced.py`) |

```ts
EvalRow = { config_name: string; description: string; recall_at_1: number; recall_at_3: number; recall_at_5: number;
            mrr: number; ndcg_at_5: number; answer_correctness: number; faithfulness: number;
            citation_accuracy: number; abstention_accuracy: number; avg_latency: number; p95_latency: number }
// all percentage metrics are 0..100; mrr is 0..1; latencies are seconds
EvalReport = { created_at: string; total_queries: number; experiments: EvalRow[]; ablations: EvalRow[];
               per_category: { [category: string]: { count: number; recall_at_5: number; answer_correctness: number } } }
```
