"""
RAG Benchmark Runner
Builds an isolated in-memory index over the 50-document sample corpus and runs the
50-question benchmark (evaluation/eval_dataset.json) against:

  Incremental systems                       Ablations of the full system
  1. Naive RAG (fixed chunks, dense only)   - w/o BM25 (dense only)
  2. + Structure-aware chunking             - w/o dense retrieval (BM25 only)
  3. + Hybrid retrieval (BM25 + RRF)        - w/o cross-encoder reranker
  4. + Cross-encoder reranking              - w/o query rewriting
  5. Full system (+ rewriting, abstention)  - w/o abstention threshold
                                            - w/o structure-aware chunking

Metrics (retrieval metrics are document-level over the top-5 retrieved chunks,
computed on answerable questions only):
  Recall@k  = |relevant docs in top-k| / |relevant docs|
  MRR       = 1 / rank of first relevant doc
  nDCG@5    = DCG@5 / IDCG@5 with binary gains, each document counted once (<= 1.0)
  Answer correctness  = all reference answer keywords present (answerable) or
                        correctly abstained (unanswerable)
  Faithfulness        = mean grounding score of non-abstained answers
  Citation accuracy   = cited sources include a relevant document
  Abstention accuracy = abstained iff the question is unanswerable
  Dev / test split     = odd-numbered questions (dev) were used to tune the answer-extraction and abstention
                         rules; even-numbered questions (test) were held out and are reported separately
Answers are generated with the deterministic extractive generator (no LLM) so
runs are reproducible and comparable across configurations.
"""
import hashlib
import json
import math
import statistics
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import Config
from .document_processor import DocumentProcessor
from .llm import LLMClient
from .rag_pipeline import PipelineSettings, RAGPipeline
from .reranker import Reranker
from .vector_store import INDEX_FORMAT, VectorStore

import numpy as np

# ------------------------------------------------------------------ speed-ups (results are unchanged)
# The benchmark runs 11 system versions over the same questions, so the same question/passage pairs are
# scored again and again. Both models are deterministic, so remembering their outputs changes no result.
# Latency, however, must not benefit from that memory: it is measured separately on a fixed sample of
# questions with the memory switched off (see LATENCY_SAMPLE).
LATENCY_SAMPLE = 24


class _CachedReranker(Reranker):
    """Cross-encoder that remembers the score of every (question, passage) pair it has seen"""

    def __init__(self):
        super().__init__()
        self._scores: Dict[Tuple[str, str], float] = {}

    def score_pairs(self, query: str, passages: List[str]) -> List[float]:
        new = [x for x in dict.fromkeys(passages) if (query, x) not in self._scores]
        for x, score in zip(new, super().score_pairs(query, new)):
            self._scores[(query, x)] = score
        return [self._scores[(query, x)] for x in passages]


class _CachedEmbedder:
    """Wraps the embedding model and remembers the vector of every text it has encoded"""

    def __init__(self, inner):
        self._inner, self._vectors, self.enabled = inner, {}, True

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def encode(self, texts: List[str], batch_size: int = 32):
        if not self.enabled or not texts:
            return self._inner.encode(texts, batch_size)
        new = [t for t in dict.fromkeys(texts) if t not in self._vectors]
        if new:
            for t, v in zip(new, self._inner.encode(new, batch_size)):
                self._vectors[t] = v
        return np.stack([self._vectors[t] for t in texts])


def _corpus_fingerprint(files: List[Path]) -> str:
    """Changes whenever a document, the chunking settings or the code that turns documents into chunks changes"""
    h = hashlib.sha256()
    for f in files:
        st = f.stat()
        h.update(f"{f.name}|{st.st_size}|{int(st.st_mtime)}\n".encode())
    h.update(f"{Config.CHUNK_SIZE}|{Config.CHUNK_OVERLAP}|{INDEX_FORMAT}|{Config.EMBEDDING_MODEL}".encode())
    for src in ("document_processor.py", "intelligent_chunking.py", "text_utils.py", "vector_store.py"):
        h.update((Path(__file__).parent / src).read_bytes())
    return h.hexdigest()[:16]

EVAL_USER = "eval"

BASE = PipelineSettings(use_dense=True, use_bm25=True, use_reranker=True, use_rewrite=True,
                        use_abstention=True, use_llm=False)

EXPERIMENTS: List[Tuple[str, str, str, PipelineSettings]] = [
    ("1. Naive RAG", "Fixed-size chunks, dense retrieval only", "fixed",
     replace(BASE, use_bm25=False, use_reranker=False, use_rewrite=False, use_abstention=False)),
    ("2. + Structure-aware chunking", "Section/sentence-aware chunks, dense only", "structured",
     replace(BASE, use_bm25=False, use_reranker=False, use_rewrite=False, use_abstention=False)),
    ("3. + Hybrid retrieval", "Dense + BM25 fused with RRF", "structured",
     replace(BASE, use_reranker=False, use_rewrite=False, use_abstention=False)),
    ("4. + Cross-encoder reranking", "Hybrid + ms-marco cross-encoder", "structured",
     replace(BASE, use_rewrite=False, use_abstention=False)),
    ("5. Full system", "Hybrid + rerank + query rewriting + abstention", "structured", BASE),
]

ABLATIONS: List[Tuple[str, str, str, PipelineSettings]] = [
    ("Full system", "All components enabled", "structured", BASE),
    ("w/o BM25", "Dense retrieval only", "structured", replace(BASE, use_bm25=False)),
    ("w/o dense retrieval", "BM25 only", "structured", replace(BASE, use_dense=False)),
    ("w/o reranker", "No cross-encoder (abstention needs it, so it is off too)", "structured",
     replace(BASE, use_reranker=False)),
    ("w/o query rewriting", "Follow-ups sent verbatim", "structured", replace(BASE, use_rewrite=False)),
    ("w/o abstention", "Always answers", "structured", replace(BASE, use_abstention=False)),
    ("w/o structure-aware chunking", "Fixed-size chunks", "fixed", BASE),
]


def _norm(s: str) -> str:
    return s.lower().replace(",", "").replace(" ", " ")


def keyword_match(answer: str, keywords: List[str]) -> bool:
    a = _norm(answer)
    return all(_norm(k) in a for k in keywords)


def build_indexes(docs_dir: Path, progress: Optional[Callable] = None) -> Dict[str, VectorStore]:
    files = sorted(p for p in docs_dir.rglob("*") if p.is_file() and p.suffix.lower() in Config.ALLOWED_EXTENSIONS)
    if not files:
        raise FileNotFoundError(f"No sample documents found in {docs_dir}. Run scripts/generate_sample_data.py")
    # indexes are cached on disk and rebuilt only when the documents or the chunking code change
    cache = Config.DATA_DIR / "eval_cache" / _corpus_fingerprint(files)
    stores = {"structured": VectorStore(cache / "structured"), "fixed": VectorStore(cache / "fixed")}
    if all(st.load() for st in stores.values()):
        if progress:
            progress(0.25, f"Using the saved search index ({len(files)} documents)")
        return stores
    processor = DocumentProcessor(Config.CHUNK_SIZE, Config.CHUNK_OVERLAP)
    stores = {"structured": VectorStore(), "fixed": VectorStore()}
    for i, path in enumerate(files, start=1):
        if progress:
            progress(0.25 * i / len(files), f"Indexing {path.name} ({i}/{len(files)})")
        domain = path.parent.name if path.parent.name in Config.DOMAINS else "general"
        elements, _, _, _ = processor.extract_elements(str(path))
        meta = {"doc_id": path.name, "user_id": EVAL_USER, "domain": domain, "filename": path.name}
        stores["structured"].add_chunks(processor.chunker.chunk_structured_elements(elements, path.name), meta)
        stores["fixed"].add_chunks(processor.chunker.chunk_fixed_size(elements, path.name), meta)
    for key, st in stores.items():
        st.index_dir = cache / key
        st.save()
    return stores


def case_split(case: Dict[str, Any]) -> str:
    """Odd-numbered questions are the tuning (dev) set, even-numbered ones the held-out test set"""
    return "dev" if int(str(case["id"]).lstrip("Qq")) % 2 else "test"


def evaluate_config(pipeline: RAGPipeline, cases: List[Dict[str, Any]], settings: PipelineSettings,
                    keep_details: bool = False) -> Dict[str, Any]:
    r1, r3, r5, rr, ndcg, faith, cite, correct, abst, lat = ([] for _ in range(10))
    by_split: Dict[str, List[float]] = {"dev": [], "test": []}
    llm_written: List[float] = []  # share of non-refused answers actually written by the LLM
    per_cat: Dict[str, Dict[str, List[float]]] = {}
    details = []
    for case in cases:
        t0 = time.perf_counter()
        res = pipeline.answer(case["question"], EVAL_USER, None, None, case.get("history") or [], settings)
        lat.append(time.perf_counter() - t0)
        if not res.abstained:
            llm_written.append(1.0 if res.generation_mode.startswith("llm") else 0.0)
        relevant = set(case.get("expected_docs") or [])
        answerable = bool(relevant)
        ranked: List[str] = []
        for c in res.contexts:
            if c["doc_id"] not in ranked:
                ranked.append(c["doc_id"])
        if answerable:
            hits = [d in relevant for d in ranked]
            r1.append(sum(hits[:1]) / len(relevant))
            r3.append(sum(hits[:3]) / len(relevant))
            r5.append(sum(hits[:5]) / len(relevant))
            first = next((i for i, h in enumerate(hits) if h), None)
            rr.append(1.0 / (first + 1) if first is not None else 0.0)
            dcg = sum(1.0 / math.log2(i + 2) for i, h in enumerate(hits[:5]) if h)
            idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), 5)))
            ndcg.append(dcg / idcg)
            ok = (not res.abstained) and keyword_match(res.answer, case.get("answer_keywords") or [])
            if not res.abstained:
                faith.append(res.grounding_score)
                cite.append(1.0 if {c["doc_id"] for c in res.citations} & relevant else 0.0)
            abst.append(0.0 if res.abstained else 1.0)
        else:
            ok = res.abstained
            abst.append(1.0 if res.abstained else 0.0)
        correct.append(1.0 if ok else 0.0)
        by_split[case_split(case)].append(1.0 if ok else 0.0)
        bucket = per_cat.setdefault(case["category"], {"recall_at_5": [], "answer_correctness": []})
        bucket["answer_correctness"].append(1.0 if ok else 0.0)
        if answerable:
            bucket["recall_at_5"].append(r5[-1])
        if keep_details:
            details.append({"id": case["id"], "category": case["category"], "question": case["question"],
                            "rewritten_query": res.rewritten_query, "answer": res.answer, "correct": ok,
                            "abstained": res.abstained, "retrieved_docs": ranked,
                            "expected_docs": sorted(relevant), "grounding": res.grounding_score})

    pct = lambda xs: round(100 * statistics.fmean(xs), 1) if xs else 0.0
    out = {
        "recall_at_1": pct(r1), "recall_at_3": pct(r3), "recall_at_5": pct(r5),
        "mrr": round(statistics.fmean(rr), 3) if rr else 0.0, "ndcg_at_5": pct(ndcg),
        "answer_correctness": pct(correct), "faithfulness": pct(faith), "citation_accuracy": pct(cite),
        "abstention_accuracy": pct(abst),
        "answer_correctness_dev": pct(by_split["dev"]), "answer_correctness_test": pct(by_split["test"]),
        "llm_answer_rate": pct(llm_written),
        "avg_latency": round(statistics.fmean(lat), 3),
        # the median is the typical time; unlike the mean, one stalled question (e.g. the laptop sleeping
        # mid-run) cannot distort it
        "median_latency": round(statistics.median(lat), 3),
        "p95_latency": round(sorted(lat)[max(0, math.ceil(0.95 * len(lat)) - 1)], 3),
        "per_category": {k: {"count": len(v["answer_correctness"]), "recall_at_5": pct(v["recall_at_5"]),
                             "answer_correctness": pct(v["answer_correctness"])} for k, v in per_cat.items()},
    }
    if keep_details:
        out["details"] = details
    return out


def _time_sample(pipeline: RAGPipeline, cases: List[Dict[str, Any]], settings: PipelineSettings) -> Dict[str, Any]:
    """Seconds per question, measured without any remembered model outputs"""
    lat = []
    for case in cases:
        t0 = time.perf_counter()
        pipeline.answer(case["question"], EVAL_USER, None, None, case.get("history") or [], settings)
        lat.append(time.perf_counter() - t0)
    return {"avg_latency": round(statistics.fmean(lat), 3), "median_latency": round(statistics.median(lat), 3),
            "p95_latency": round(sorted(lat)[max(0, math.ceil(0.95 * len(lat)) - 1)], 3),
            "latency_sample": len(lat)}


def run_benchmark(progress: Optional[Callable[[float, str], None]] = None,
                  dataset_path: Optional[Path] = None, docs_dir: Optional[Path] = None,
                  save: bool = True) -> Dict[str, Any]:
    dataset = json.loads(Path(dataset_path or Config.EVAL_DATASET).read_text(encoding="utf-8"))
    cases = dataset["test_cases"]
    stores = build_indexes(Path(docs_dir or Config.SAMPLE_DOCS_DIR), progress)
    reranker = Reranker()
    offline = LLMClient(provider="none")
    embedder = _CachedEmbedder(stores["structured"].embedder)
    for st in stores.values():
        st.embedder = embedder
    cached_reranker = _CachedReranker()
    # accuracy: pipelines with memory; latency: plain pipelines on a fixed sample
    pipelines = {k: RAGPipeline(v, llm=offline, reranker=cached_reranker) for k, v in stores.items()}
    timing = {k: RAGPipeline(v, llm=offline, reranker=reranker) for k, v in stores.items()}
    for pipe in pipelines.values():
        pipe.embedder = embedder
    step = max(1, len(cases) // LATENCY_SAMPLE)
    sample = cases[::step][:LATENCY_SAMPLE]

    runs = [("experiments", e) for e in EXPERIMENTS] + [("ablations", a) for a in ABLATIONS[1:]]
    results: Dict[str, Any] = {}
    report = {"created_at": datetime.now().isoformat(timespec="seconds"), "total_queries": len(cases),
              "corpus_documents": len({m["doc_id"] for m in stores["structured"].metadata.values()}),
              "generation": "extractive (cross-encoder sentence selection, no LLM) for reproducibility",
              "reranker": reranker.model_name, "embedding": stores["structured"].embedder.model_name,
              "latency_note": f"latency measured on a fixed sample of {len(sample)} questions per configuration",
              "experiments": [], "ablations": [], "per_category": {}}
    for i, (group, (name, desc, store_key, settings)) in enumerate(runs):
        if progress:
            progress(0.25 + 0.75 * i / len(runs), f"Evaluating: {name}")
        embedder.enabled = False
        latency = _time_sample(timing[store_key], sample, settings)
        embedder.enabled = True
        metrics = evaluate_config(pipelines[store_key], cases, settings, keep_details=(name == "5. Full system"))
        metrics.update(latency)
        row = {"config_name": name, "description": desc,
               **{k: v for k, v in metrics.items() if k not in ("per_category", "details")}}
        report[group].append(row)
        if name == "5. Full system":
            report["per_category"] = metrics["per_category"]
            report["details"] = metrics["details"]
            results["full_row"] = dict(row, config_name="Full system", description="All components enabled")
    report["ablations"].insert(0, results["full_row"])

    if save:
        Config.EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (Config.EVAL_RESULTS_DIR / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (Config.EVAL_RESULTS_DIR / "latest.md").write_text(to_markdown(report), encoding="utf-8")
    if progress:
        progress(1.0, "Benchmark complete")
    return report


def run_llm_comparison(progress: Optional[Callable[[float, str], None]] = None,
                       dataset_path: Optional[Path] = None, docs_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Full system with the configured LLM (Groq / Gemini / Claude) vs the same system
    with the offline extractive generator. Saved to evaluation/results/llm_comparison.{json,md}.
    """
    llm = LLMClient(retries=10, max_wait=90)  # the benchmark waits out rate limits instead of answering offline
    if not llm.available:
        raise RuntimeError("No LLM is configured or reachable (set GROQ_API_KEY, GEMINI_API_KEY or ANTHROPIC_API_KEY in .env)")
    cases = json.loads(Path(dataset_path or Config.EVAL_DATASET).read_text(encoding="utf-8"))["test_cases"]
    store = build_indexes(Path(docs_dir or Config.SAMPLE_DOCS_DIR), progress)["structured"]
    reranker = Reranker()
    rows = []
    for idx, (label, client, use_llm) in enumerate([("Extractive (no LLM)", LLMClient(provider="none"), False),
                                                     (f"LLM: {llm.label}", llm, True)]):
        if progress:
            progress(0.25 + 0.375 * idx, f"Evaluating full system - {label}")
        pipe = RAGPipeline(store, llm=client, reranker=reranker)
        m = evaluate_config(pipe, cases, replace(BASE, use_llm=use_llm), keep_details=True)
        rows.append({"config_name": label, **m})
    report = {"created_at": datetime.now().isoformat(timespec="seconds"), "total_queries": len(cases),
              "llm": llm.label, "rows": rows}
    Config.EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (Config.EVAL_RESULTS_DIR / "llm_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    keys = [("Answer correct", "answer_correctness", "%"), ("Correct (held-out test)", "answer_correctness_test", "%"),
            ("Written by LLM", "llm_answer_rate", "%"), ("Abstention acc.", "abstention_accuracy", "%"),
            ("Faithfulness", "faithfulness", "%"), ("Citation acc.", "citation_accuracy", "%"),
            ("Recall@1", "recall_at_1", "%"), ("Median latency", "median_latency", "s"), ("P95 latency", "p95_latency", "s")]
    md = [f"# Extractive vs LLM generation ({report['created_at']})", "",
          f"Full system, {len(cases)} questions. LLM: `{llm.label}`.", "",
          "| Generator | " + " | ".join(k[0] for k in keys) + " |", "|---|" + "|".join(":---:" for _ in keys) + "|"]
    md += ["| " + r["config_name"] + " | " + " | ".join(f"{r[k]}{u}" for _, k, u in keys) + " |" for r in rows]
    cats = list(rows[0]["per_category"])
    md += ["", "| Category | " + " | ".join(r["config_name"] for r in rows) + " |", "|---|" + "|".join(":---:" for _ in rows) + "|"]
    md += [f"| {c} | " + " | ".join(f"{r['per_category'][c]['answer_correctness']}%" for r in rows) + " |" for c in cats]
    (Config.EVAL_RESULTS_DIR / "llm_comparison.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if progress:
        progress(1.0, "LLM comparison complete")
    return report


def to_markdown(report: Dict[str, Any]) -> str:
    cols = [("Recall@1", "recall_at_1", "%"), ("Recall@5", "recall_at_5", "%"), ("MRR", "mrr", ""),
            ("nDCG@5", "ndcg_at_5", "%"), ("Answer correct", "answer_correctness", "%"),
            ("Correct (test)", "answer_correctness_test", "%"), ("Faithfulness", "faithfulness", "%"), ("Citation acc.", "citation_accuracy", "%"),
            ("Abstention acc.", "abstention_accuracy", "%"), ("Median latency", "median_latency", "s")]

    def table(rows):
        head = "| Configuration | " + " | ".join(c[0] for c in cols) + " |\n"
        head += "|---|" + "|".join(":---:" for _ in cols) + "|\n"
        return head + "".join("| " + r["config_name"] + " | " + " | ".join(
            f"{r[k]}{u}" for _, k, u in cols) + " |\n" for r in rows)

    lines = [f"# Benchmark results ({report['created_at']})", "",
             f"{report['total_queries']} questions over {report['corpus_documents']} documents. "
             f"Embedding: `{report['embedding']}`; reranker: `{report['reranker']}`; "
             f"generation: {report['generation']}.", "",
             "Odd-numbered questions (dev) were used to tune answer extraction and abstention; even-numbered "
             "questions (test) were held out. *Correct (test)* is the held-out score.", "",
             "## Incremental systems", "", table(report["experiments"]),
             "## Ablation study", "", table(report["ablations"]), "## Full system by question category", "",
             "| Category | Questions | Recall@5 | Answer correct |", "|---|:---:|:---:|:---:|"]
    for cat, v in report["per_category"].items():
        lines.append(f"| {cat} | {v['count']} | {v['recall_at_5']}% | {v['answer_correctness']}% |")
    return "\n".join(lines) + "\n"
