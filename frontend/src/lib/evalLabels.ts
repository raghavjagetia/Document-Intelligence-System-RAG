/**
 * Plain-English names for the benchmark's configurations, metrics and question types.
 * The backend keeps the technical names (used in the report); the UI shows these.
 */

export interface ConfigLabel {
  /** full name for tables */
  name: string;
  /** short name for chart axes and legends */
  short: string;
  /** one-line explanation */
  hint: string;
}

const CONFIGS: Record<string, ConfigLabel> = {
  "1. Naive RAG": {
    name: "Basic search",
    short: "Basic search",
    hint: "Starting point: fixed-size text pieces, searched by meaning only",
  },
  "2. + Structure-aware chunking": {
    name: "Adds smart splitting",
    short: "Adds smart splitting",
    hint: "Splits documents at headings, list items and table rows instead of fixed sizes",
  },
  "3. + Hybrid retrieval": {
    name: "Adds keyword search",
    short: "Adds keyword search",
    hint: "Adds exact keyword search (BM25) next to meaning-based search",
  },
  "4. + Cross-encoder reranking": {
    name: "Adds AI re-ranking",
    short: "Adds AI re-ranking",
    hint: "A second AI model re-reads the top results and puts the best first",
  },
  "5. Full system": {
    name: "Full system",
    short: "Full system",
    hint: "Adds follow-up question understanding and the “I don’t know” check",
  },
  "Full system": {
    name: "Full system (all features on)",
    short: "Full system",
    hint: "Every feature switched on — the version users get",
  },
  "w/o BM25": {
    name: "Without keyword search",
    short: "Without keyword search",
    hint: "Full system with the exact keyword search (BM25) switched off",
  },
  "w/o dense retrieval": {
    name: "Without meaning search",
    short: "Without meaning search",
    hint: "Full system with the meaning-based (FAISS embedding) search switched off",
  },
  "w/o reranker": {
    name: "Without AI re-ranking",
    short: "Without AI re-ranking",
    hint: "Full system with the second-opinion AI ranking model switched off",
  },
  "w/o query rewriting": {
    name: "Without follow-up understanding",
    short: "Without follow-up understanding",
    hint: "Follow-up questions like “what about sick leave?” are searched as-is",
  },
  "w/o abstention": {
    name: "Without the “I don’t know” check",
    short: "Without “I don’t know” check",
    hint: "The system always answers, even when the documents don’t contain the answer",
  },
  "w/o structure-aware chunking": {
    name: "Without smart splitting",
    short: "Without smart splitting",
    hint: "Full system but documents are cut into fixed-size pieces",
  },
};

export function configLabel(technical: string): ConfigLabel {
  return CONFIGS[technical] ?? { name: technical, short: technical, hint: "" };
}

const CATEGORIES: Record<string, string> = {
  factual: "Direct facts",
  paraphrase: "Reworded questions",
  exact_id: "ID look-ups",
  tabular: "Table values",
  multi_doc: "Two documents",
  followup: "Follow-ups",
  ocr: "Scanned pages",
  unanswerable: "Not in documents",
};

export function categoryLabel(technical: string): string {
  return CATEGORIES[technical] ?? technical.replace(/_/g, " ");
}
