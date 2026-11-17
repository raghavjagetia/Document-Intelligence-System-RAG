// Types mirror docs/API.md exactly.

export type Domain = "general" | "hr" | "legal" | "healthcare" | "finance";
export type QueryDomain = Domain | "all";
export type RetrievalMode = "hybrid" | "semantic" | "bm25";
/** How a chat answer is written: short, explained in detail, or quoted word-for-word from the documents */
export type AnswerStyle = "quick" | "detailed" | "quote";

export const DOMAINS: Domain[] = ["general", "hr", "legal", "healthcare", "finance"];

export interface User {
  user_id: string;
  username: string;
  email: string;
  role: "user" | "admin";
  created_at: string;
}

export interface AuthResponse {
  user: User;
  token: string;
}

export interface Document {
  doc_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  domain: string;
  page_count: number;
  chunk_count: number;
  tables_count: number;
  ocr_pages: number;
  version: number;
  parent_doc_id: string | null;
  status: "indexed" | "failed";
  uploaded_at: string;
  /** username of the uploader (shown to administrators) */
  owner?: string;
  user_id?: string;
}

export type ElementType = "heading" | "paragraph" | "list" | "table" | "slide" | "text";

export interface Chunk {
  chunk_id: string;
  doc_id: string;
  chunk_index: number;
  page_number: number;
  section: string;
  element_type: ElementType;
  content: string;
  char_count: number;
  token_count: number;
}

export interface Citation {
  citation_number: number;
  doc_id: string;
  filename: string;
  page_number: number;
  section: string;
  chunk_id: string;
  source_snippet: string;
  relevance_score: number;
  /** Which search method(s) found this passage (absent on answers saved before this was recorded) */
  found_by?: ("meaning" | "words")[];
}

export interface Message {
  message_id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  rewritten_query: string | null;
  citations: Citation[];
  grounded: boolean;
  grounding_score: number;
  confidence_score: number;
  latency_seconds: number;
  model_name: string | null;
  generation_mode: string | null;
  abstained: boolean;
  /** how the answer was written (absent on answers saved before answer styles existed) */
  answer_style?: AnswerStyle | null;
  /** the asker's rating: 1 helpful, -1 not helpful, null not rated */
  feedback?: 1 | -1 | null;
  timestamp: string;
}

/** A cited passage shown inside its document, with the supporting sentence highlighted */
export interface SourceView {
  doc_id: string;
  filename: string;
  chunk_id: string | null;
  highlights: string[];
  page_number: number;
  found: boolean;
  kind: "pdf" | "text";
  // kind === "pdf": rendered page image and highlight rectangles as fractions of the page size
  page_count?: number;
  aspect_ratio?: number;
  image?: string;
  boxes?: { x: number; y: number; w: number; h: number }[];
  // kind === "text": the cited chunk with its neighbours
  chunks?: { chunk_id: string; section: string | null; page_number: number | null; content: string; cited: boolean }[];
}

export interface Conversation {
  conversation_id: string;
  user_id?: string;
  /** username of the conversation's owner (shown to administrators) */
  owner?: string;
  title: string;
  domain: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

// ---------- System ----------
export interface Health {
  status: "online";
  version: string;
}

export interface SystemStatus {
  embedding: { model: string; type: "neural" | "hashing"; dimension: number };
  reranker: { model: string; type: "cross-encoder" | "lexical" };
  llm: { provider: string; model: string; available: boolean; paused_seconds?: number };
  ocr: { available: boolean; engine: string };
  vector_index: "faiss" | "numpy";
  supported_formats: string[];
}

export interface Statistics {
  total_documents: number;
  total_chunks: number;
  total_conversations: number;
  total_questions: number;
  avg_confidence: number;
  avg_latency: number;
  grounded_rate: number;
  abstention_rate: number;
  by_domain: Record<string, number>;
  by_format: Record<string, number>;
  recent_documents: (Document & { owner?: string })[];
  scope: "user" | "system";
  total_users: number | null;
}

export interface Analytics {
  queries_per_day: { date: string; count: number }[];
  confidence_history: { timestamp: string; confidence: number; grounding: number; latency: number }[];
  top_documents: { filename: string; citations: number }[];
  retrieval_modes: Record<string, number>;
  latency_histogram: { bucket: string; count: number }[];
  /** thumbs up / down given to answers */
  feedback?: {
    helpful: number;
    not_helpful: number;
    rated: number;
    answers: number;
    satisfaction: number | null;
    by_style: { style: string; answers: number; helpful: number; not_helpful: number }[];
  };
}

// ---------- Documents ----------
export interface UploadResult {
  processed: Document[];
  duplicates: { filename: string; existing_doc_id: string }[];
  errors: { filename: string; error: string }[];
}

export interface DocumentList {
  documents: Document[];
  total: number;
}

export interface DocumentDetail {
  document: Document;
  chunks: Chunk[];
}

export interface Summary {
  summary_type?: "short" | "detailed";
  overview: string;
  key_points: string[];
  /** detailed summaries only: one short summary per section of the document */
  sections?: { title: string; summary: string }[];
  main_topics: string[];
  important_dates: string[];
  important_numbers: string[];
  conclusion: string;
  method: string;
}

export interface SummaryResponse {
  doc_id: string;
  filename: string;
  summary: Summary;
}

export type EntityType =
  | "Person"
  | "Organization"
  | "Location"
  | "Date"
  | "Money"
  | "Email"
  | "Phone"
  | "Employee ID"
  | "Contract ID"
  | "Department";

export interface EntitiesResponse {
  doc_id: string;
  filename: string;
  entities: Record<EntityType, string[]>;
  method: string;
}

export type ExtractDocType = "auto" | "contract" | "invoice" | "resume";

export interface ExtractResponse {
  doc_id: string;
  filename: string;
  structured_data: {
    document_type: string;
    fields: Record<string, string | string[] | null>;
  };
}

export interface CompareResponse {
  label_a: string;
  label_b: string;
  similarity_score: number;
  added_count: number;
  removed_count: number;
  modified_count: number;
  added_clauses: string[];
  removed_clauses: string[];
  modified_clauses: {
    from_text: string;
    to_text: string;
    deltas: { original_value: string; new_value: string; change_delta: string | number }[];
  }[];
  new_dates: string[];
  removed_dates: string[];
}

// ---------- Chat ----------
export interface QueryRequest {
  question: string;
  conversation_id?: string;
  domain?: QueryDomain;
  doc_id?: string;
  retrieval_mode?: RetrievalMode;
  answer_style?: AnswerStyle;
}

export interface QueryResponse {
  conversation_id: string;
  user_message: Message;
  assistant_message: Message;
}

export interface StreamMeta {
  conversation_id: string;
  user_message: Message;
  rewritten_query: string | null;
  citations: Citation[];
}

// ---------- Evaluation ----------
export interface EvalRow {
  config_name: string;
  description: string;
  recall_at_1: number;
  recall_at_3: number;
  recall_at_5: number;
  mrr: number;
  ndcg_at_5: number;
  answer_correctness: number;
  /** correctness on the held-out (even-numbered) test questions */
  answer_correctness_test?: number;
  answer_correctness_dev?: number;
  faithfulness: number;
  citation_accuracy: number;
  abstention_accuracy: number;
  avg_latency: number;
  p95_latency: number;
  /** typical (median) seconds per question; older reports only have avg_latency */
  median_latency?: number;
}

export interface EvalReport {
  created_at: string;
  total_queries: number;
  corpus_documents?: number;
  experiments: EvalRow[];
  ablations: EvalRow[];
  per_category: Record<string, { count: number; recall_at_5: number; answer_correctness: number }>;
}

export interface EvalStatus {
  status: "idle" | "running" | "done" | "error";
  progress: number;
  message: string;
}

export interface AdminUserRow {
  user_id: string;
  username: string;
  email: string;
  role: "user" | "admin";
  disabled: boolean;
  sessions: number;
  created_at: string;
  documents: number;
  chunks: number;
  storage_bytes: number;
  conversations: number;
  questions: number;
  last_active: string | null;
}

export interface AdminOverview {
  totals: {
    users: number;
    documents: number;
    chunks: number;
    storage_bytes: number;
    conversations: number;
    questions: number;
    active_sessions: number;
  };
  users: AdminUserRow[];
  documents: (Document & { owner: string })[];
  recent_questions: {
    timestamp: string;
    username: string;
    conversation_id: string;
    question: string;
    answer: string;
    confidence_score: number;
    abstained: boolean;
    latency_seconds: number;
    generation_mode: string | null;
  }[];
}

export interface AdminUserDetail {
  user: AdminUserRow | null;
  stats: { avg_confidence: number; avg_latency: number; abstained: number; grounded_rate: number };
  activity: { date: string; count: number }[];
  by_domain: Record<string, number>;
  documents: Document[];
  conversations: Conversation[];
}
