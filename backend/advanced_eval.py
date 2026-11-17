"""
Advanced evaluation: baselines, error bars, error analysis and the multilingual benchmark
=======================================================================================

Systems compared on the same 156 questions and the same documents (scored exactly like backend/evaluation.py):

  1. LLM only (no documents)   the configured LLM answers from its own knowledge - shows why retrieval is needed
  2. Standard RAG (LangChain)  the textbook recipe: LangChain RecursiveCharacterTextSplitter (1000 / 200),
                               the same MiniLM embeddings, top-4 cosine retrieval and LangChain's standard
                               RAG prompt ("rlm/rag-prompt"), answered by the same LLM
  3. DocuMind, offline         full pipeline with the extractive answer generator (no LLM)
  4. DocuMind + LLM            full pipeline with the same LLM

Both RAG systems read identical text (extracted by DocumentProcessor), so the comparison isolates the pipeline:
chunking, retrieval, reranking, refusal and prompting.

Statistics
  - 95% confidence intervals: Wilson score interval for each share of correct answers
  - Paired significance: exact McNemar test on the questions one system got right and the other wrong
Error analysis (DocuMind): every wrong answer is put in one category - wrong document found / right document but
wrong or incomplete answer / wrongly refused / answered although the documents cannot answer.
Multilingual: 30 questions in Hindi and Hinglish (evaluation/multilingual_dataset.json) scored against the same
reference keywords as their English originals; also checks the reply language and that numbers survive translation.

Groq usage is protected (GuardedLLM): every answer is cached on disk (a re-run or resume never pays twice), calls are
paced to the per-minute token limit, rate limits are waited out instead of silently falling back to offline answers,
and the run stops while `reserve` requests of the daily allowance are still left for the live website. Run it again
later (e.g. the next day) and it continues where it stopped.
"""
import hashlib
import json
import math
import re
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import requests

from .config import Config
from .document_processor import DocumentProcessor
from .evaluation import (BASE, EVAL_USER, _CachedReranker, build_indexes, case_split, evaluate_config,
                         keyword_match)
from .llm import LLMClient, _clean
from .models import get_embedder
from .rag_pipeline import RAGPipeline, _strip_reasoning

Progress = Optional[Callable[[float, str], None]]
RESULTS_FILE = "advanced_eval.json"
STAGES = ["documind_offline", "llm_only", "documind_llm", "multilingual", "langchain"]
STAGE_LABELS = {
    "documind_offline": "DocuMind (offline, no LLM)",
    "llm_only": "LLM only (no documents)",
    "documind_llm": "DocuMind + LLM",
    "langchain": "Standard RAG (LangChain)",
    "multilingual": "Multilingual benchmark",
}

# LangChain's standard RAG prompt (LangChain Hub "rlm/rag-prompt")
LANGCHAIN_RAG_PROMPT = (
    "You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer "
    "the question. If you don't know the answer, just say that you don't know. Use three sentences maximum and keep "
    "the answer concise.\nQuestion: {question} \nContext: {context} \nAnswer:")
LLM_ONLY_PROMPT = "{question}\n\nAnswer concisely. If you don't know the answer, say that you don't know."

# baselines have no refusal mechanism of their own: an answer that says it does not know counts as a refusal
REFUSAL_RE = re.compile(
    r"\b(i (do not|don't|cannot|can't) (know|find|answer|determine|provide)|not (mentioned|provided|available|"
    r"specified|stated|included|contained|given)|no (information|mention|data|details)|(does|do) not (contain|mention|"
    r"provide|include|specify|state)|unable to (find|determine|answer|provide)|insufficient information|"
    r"there is no information|i don't have|i do not have|not have (access|information))", re.IGNORECASE)


class BudgetPaused(RuntimeError):
    """The daily Groq allowance is down to the reserve kept for the website"""


def _parse_duration(text: str) -> float:
    """Groq reset headers: '142ms', '7.5s', '1m2.3s', '1h56m38.4s' -> seconds"""
    if not text:
        return 0.0
    total = 0.0
    for value, unit in re.findall(r"([\d.]+)(ms|h|m|s)", text):
        total += float(value) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]
    return total


class GuardedLLM(LLMClient):
    """Groq client for benchmarks: disk cache, per-minute token pacing, patient retries, daily-quota reserve.
    It never raises inside the pipeline silently: a pause or failure sets a flag the runner checks after every
    question, so offline fall-back answers can never be mixed into LLM results."""

    def __init__(self, cache_path: Path, reserve: int = 250):
        super().__init__(provider="groq", retries=0, max_wait=0)
        if not Config.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set in .env - the LLM stages need it")
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache: Dict[str, str] = {}
        if cache_path.exists():
            for line in cache_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self.cache[row["key"]] = row["text"]
        self.reserve = reserve
        self.remaining_requests: Optional[int] = None
        self.remaining_tokens: Optional[int] = None
        self.reset_tokens = 0.0
        self.calls = self.cache_hits = 0
        self.problem: Optional[str] = None  # set when the run must stop (quota reserve reached / repeated errors)

    def stream(self, prompt: str, system: str = "", max_tokens: Optional[int] = None):
        yield self.generate(prompt, system, max_tokens)

    def _key(self, prompt: str, system: str, max_tokens: int) -> str:
        return hashlib.sha256(json.dumps([self.model, system, prompt, max_tokens, Config.LLM_TEMPERATURE],
                                         ensure_ascii=False).encode("utf-8")).hexdigest()

    def _read_headers(self, r: requests.Response) -> None:
        h = r.headers
        if h.get("x-ratelimit-remaining-requests", "").isdigit():
            self.remaining_requests = int(h["x-ratelimit-remaining-requests"])
        if h.get("x-ratelimit-remaining-tokens", "").isdigit():
            self.remaining_tokens = int(h["x-ratelimit-remaining-tokens"])
        self.reset_tokens = _parse_duration(h.get("x-ratelimit-reset-tokens", ""))

    def generate(self, prompt: str, system: str = "", max_tokens: Optional[int] = None) -> str:
        max_tokens = max_tokens or Config.LLM_MAX_TOKENS
        key = self._key(prompt, system, max_tokens)
        if key in self.cache:
            self.cache_hits += 1
            return self.cache[key]
        if self.problem:
            raise BudgetPaused(self.problem)
        if self.remaining_requests is not None and self.remaining_requests <= self.reserve:
            self.problem = (f"Stopped to keep {self.reserve} Groq requests of today's allowance for the website "
                            f"({self.remaining_requests} left). Run again later to continue.")
            raise BudgetPaused(self.problem)
        # pace to the per-minute token limit: wait for the window to refill if this call might not fit
        need = len(prompt + system) // 3 + max_tokens
        if self.remaining_tokens is not None and self.remaining_tokens < need:
            time.sleep(min(60.0, self.reset_tokens + 0.5))
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        for attempt in range(25):
            try:
                r = requests.post(f"{Config.GROQ_BASE_URL.rstrip('/')}/chat/completions",
                                  headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"},
                                  json={"model": self.model, "messages": messages, "temperature": Config.LLM_TEMPERATURE,
                                        "max_tokens": max_tokens}, timeout=Config.LLM_TIMEOUT)
            except requests.RequestException:
                time.sleep(min(60, 5 * (attempt + 1)))
                continue
            self._read_headers(r)
            if r.status_code == 429:
                if self.remaining_requests == 0:
                    self.problem = "Today's Groq request allowance is used up. Run again tomorrow to continue."
                    raise BudgetPaused(self.problem)
                # the daily TOKEN allowance (e.g. 200,000 tokens/day on the free tier) is not in the rate-limit
                # headers, only in the error text; it frees up slowly over 24 hours, so waiting is pointless
                if "per day" in r.text.lower() or "(tpd)" in r.text.lower():
                    self.problem = ("Groq's daily token allowance is used up (free tier). It frees up gradually over "
                                    "24 hours: run again tomorrow to continue.")
                    raise BudgetPaused(self.problem)
                raw = r.headers.get("retry-after", "")
                wait = float(raw) if raw.replace(".", "", 1).isdigit() else max(self.reset_tokens, 5.0)
                if wait > 600:  # a long block (daily token allowance): stop and resume later
                    self.problem = f"Groq asked to wait {wait / 60:.0f} minutes. Run again later to continue."
                    raise BudgetPaused(self.problem)
                time.sleep(wait + 0.5)
                continue
            if r.status_code >= 500:
                time.sleep(min(60, 5 * (attempt + 1)))
                continue
            if r.status_code >= 400:
                self.problem = f"Groq error {r.status_code}: {r.text[:200]}"
                raise BudgetPaused(self.problem)
            text = _strip_reasoning(_clean(r.json()["choices"][0]["message"].get("content") or ""))
            self.cache[key] = text
            with open(self.cache_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "text": text}, ensure_ascii=False) + "\n")
            self.calls += 1
            return text
        self.problem = "Groq kept failing (network or server errors). Run again later to continue."
        raise BudgetPaused(self.problem)


# ---------------------------------------------------------------- statistics
def proportion_ci(values: List[float], z: float = 1.959964) -> List[float]:
    """95% Wilson score interval of a share of correct answers, in percent. Unlike a bootstrap it stays honest at the
    extremes: 15 out of 15 correct gives about 80-100%, not a misleading 100-100%."""
    n = len(values)
    if not n:
        return [0.0, 0.0]
    p = sum(values) / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(100 * max(0.0, centre - half), 1), round(100 * min(1.0, centre + half), 1)]


def mcnemar_exact(a: Dict[str, bool], b: Dict[str, bool]) -> Dict[str, Any]:
    """Exact (binomial) McNemar test on paired per-question outcomes"""
    ids = sorted(set(a) & set(b))
    only_a = sum(1 for i in ids if a[i] and not b[i])
    only_b = sum(1 for i in ids if b[i] and not a[i])
    n = only_a + only_b
    if n == 0:
        p = 1.0
    else:
        k = min(only_a, only_b)
        p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return {"only_first_correct": only_a, "only_second_correct": only_b, "p_value": round(p, 5)}


# ---------------------------------------------------------------- scoring shared by every system
def score_records(cases: List[Dict[str, Any]], records: Dict[str, Dict[str, Any]], k: int) -> Dict[str, Any]:
    """records[id] = {answer, abstained, retrieved_docs (ranked), grounding (optional)}; same rules as evaluation.py"""
    correct, by_split, abst, r1, rk, faith = {}, {"dev": [], "test": []}, [], [], [], []
    for case in cases:
        rec = records[case["id"]]
        relevant = set(case.get("expected_docs") or [])
        if relevant:
            ok = (not rec["abstained"]) and keyword_match(rec["answer"], case.get("answer_keywords") or [])
            abst.append(0.0 if rec["abstained"] else 1.0)
            if rec.get("retrieved_docs") is not None:
                hits = [d in relevant for d in rec["retrieved_docs"]]
                r1.append(sum(hits[:1]) / len(relevant))
                rk.append(sum(hits[:k]) / len(relevant))
            if not rec["abstained"] and rec.get("grounding") is not None:
                faith.append(rec["grounding"])
        else:
            ok = rec["abstained"]
            abst.append(1.0 if rec["abstained"] else 0.0)
        correct[case["id"]] = bool(ok)
        by_split[case_split(case)].append(1.0 if ok else 0.0)
    pct = lambda xs: round(100 * sum(xs) / len(xs), 1) if xs else None
    values = [1.0 if correct[c["id"]] else 0.0 for c in cases]
    return {
        "questions": len(cases),
        "answer_correctness": pct(values), "ci": proportion_ci(values),
        "answer_correctness_test": pct(by_split["test"]), "ci_test": proportion_ci(by_split["test"]),
        "answer_correctness_dev": pct(by_split["dev"]),
        "abstention_accuracy": pct(abst),
        "recall_at_1": pct(r1), "recall_at_k": pct(rk), "k": k if rk else None,
        "faithfulness": pct(faith),
        "per_question": correct,
    }


# ---------------------------------------------------------------- error analysis
ERROR_CATEGORIES = [
    ("wrong_document", "Wrong document found",
     "The right document was not among the top retrieved passages, so the answer came from elsewhere."),
    ("wrong_sentence", "Right document, wrong or incomplete answer",
     "The right document was retrieved, but the answer picked the wrong sentence or missed part of the fact."),
    ("wrongly_refused", "Wrongly refused",
     "The documents contain the answer, but the system said it could not find enough evidence."),
    ("should_refuse", "Answered when it should have refused",
     "The documents do not contain the answer, but the system answered anyway."),
]


def error_analysis(cases: List[Dict[str, Any]], records: Dict[str, Dict[str, Any]],
                   correct: Dict[str, bool], max_examples: int = 4) -> Dict[str, Any]:
    buckets: Dict[str, List[Dict[str, Any]]] = {key: [] for key, _, _ in ERROR_CATEGORIES}
    for case in cases:
        if correct[case["id"]]:
            continue
        rec = records[case["id"]]
        relevant = set(case.get("expected_docs") or [])
        found = bool(relevant & set(rec.get("retrieved_docs") or []))
        if not relevant:
            key = "should_refuse"
        elif rec["abstained"]:
            key = "wrongly_refused"
        elif not found:
            key = "wrong_document"
        else:
            key = "wrong_sentence"
        buckets[key].append({
            "id": case["id"], "category": case["category"], "question": case["question"],
            "expected": ", ".join(case.get("answer_keywords") or []) or "(should refuse)",
            "expected_docs": sorted(relevant), "retrieved_docs": (rec.get("retrieved_docs") or [])[:3],
            "answer": re.sub(r"\s+", " ", rec["answer"])[:280],
            "right_document_retrieved": found,
        })
    total = sum(len(v) for v in buckets.values())
    return {"total_errors": total, "questions": len(cases), "categories": [
        {"key": key, "label": label, "description": desc, "count": len(buckets[key]),
         "share": round(100 * len(buckets[key]) / total, 1) if total else 0.0,
         # e.g. a refusal where search never found the right document is really a search failure
         "right_document_found": sum(1 for e in buckets[key] if e["right_document_retrieved"]),
         "examples": buckets[key][:max_examples]} for key, label, desc in ERROR_CATEGORIES]}


# ---------------------------------------------------------------- systems
def run_documind(store, cases, llm: Optional[LLMClient], progress: Progress, label: str,
                 check: Optional[Callable[[], None]] = None) -> Dict[str, Dict[str, Any]]:
    use_llm = llm is not None
    pipe = RAGPipeline(store, llm=llm or LLMClient(provider="none"), reranker=_CachedReranker())
    records: Dict[str, Dict[str, Any]] = {}
    settings = replace(BASE, use_llm=use_llm)
    for i, case in enumerate(cases):
        if progress:
            progress(i / len(cases), f"{label}: question {i + 1}/{len(cases)}")
        res = pipe.answer(case["question"], EVAL_USER, None, None, case.get("history") or [], settings)
        if check:
            check()  # stop at once if the LLM paused, so no offline fall-back answer is recorded as an LLM answer
        ranked: List[str] = []
        for c in res.contexts:
            if c["doc_id"] not in ranked:
                ranked.append(c["doc_id"])
        records[case["id"]] = {"answer": res.answer, "abstained": res.abstained, "retrieved_docs": ranked,
                               "grounding": res.grounding_score, "generation_mode": res.generation_mode}
    return records


def run_llm_only(cases, llm: GuardedLLM, progress: Progress) -> Dict[str, Dict[str, Any]]:
    records = {}
    for i, case in enumerate(cases):
        if progress:
            progress(i / len(cases), f"LLM only: question {i + 1}/{len(cases)}")
        answer = llm.generate(LLM_ONLY_PROMPT.format(question=case["question"]), max_tokens=300)
        records[case["id"]] = {"answer": answer, "abstained": bool(REFUSAL_RE.search(answer)),
                               "retrieved_docs": None, "grounding": None}
    return records


def _langchain_index(docs_dir: Path):
    """Standard LangChain chunking over the same extracted text, embedded with the same MiniLM model"""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    files = sorted(p for p in docs_dir.rglob("*") if p.is_file() and p.suffix.lower() in Config.ALLOWED_EXTENSIONS)
    processor = DocumentProcessor(Config.CHUNK_SIZE, Config.CHUNK_OVERLAP)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks: List[Dict[str, Any]] = []
    for path in files:
        elements, _, _, _ = processor.extract_elements(str(path), path.name)
        text = "\n\n".join(e["text"] for e in elements if e.get("text", "").strip())
        for j, piece in enumerate(splitter.split_text(text)):
            chunks.append({"doc_id": path.name, "filename": path.name, "chunk_id": f"{path.name}#{j}",
                           "content": piece, "section": "", "page_number": 1})
    embedder = get_embedder()
    vectors = embedder.encode([c["content"] for c in chunks])
    return chunks, vectors, embedder


def run_langchain(cases, llm: GuardedLLM, docs_dir: Path, progress: Progress) -> Dict[str, Dict[str, Any]]:
    if progress:
        progress(0.0, "Standard RAG: building the LangChain index")
    chunks, vectors, embedder = _langchain_index(docs_dir)
    grounder = RAGPipeline.__new__(RAGPipeline)  # only its grounding check is used, on the same evidence
    grounder.embedder = embedder
    records = {}
    for i, case in enumerate(cases):
        if progress:
            progress(i / len(cases), f"Standard RAG (LangChain): question {i + 1}/{len(cases)}")
        q = embedder.encode([case["question"]])[0]
        top = np.argsort(-(vectors @ q))[:4]
        ctx = [chunks[t] for t in top]
        context = "\n\n".join(c["content"] for c in ctx)  # LangChain's format_docs
        answer = llm.generate(LANGCHAIN_RAG_PROMPT.format(question=case["question"], context=context), max_tokens=300)
        ranked: List[str] = []
        for c in ctx:
            if c["doc_id"] not in ranked:
                ranked.append(c["doc_id"])
        abstained = bool(REFUSAL_RE.search(answer))
        records[case["id"]] = {"answer": answer, "abstained": abstained, "retrieved_docs": ranked,
                               "grounding": None if abstained else grounder.grounding_score(answer, ctx, case["question"])}
    return records


_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def run_multilingual(items, cases_by_id, store, llm: GuardedLLM, english: Dict[str, Dict[str, Any]],
                     progress: Progress, check: Callable[[], None]) -> Dict[str, Any]:
    pipe = RAGPipeline(store, llm=llm, reranker=_CachedReranker())
    settings = replace(BASE, use_llm=True)
    rows = []
    for i, item in enumerate(items):
        if progress:
            progress(i / len(items), f"Multilingual: question {i + 1}/{len(items)}")
        case = cases_by_id[item["source_id"]]
        res = pipe.answer(item["question"], EVAL_USER, None, None, [], settings)
        check()
        relevant = bool(case.get("expected_docs"))
        verified = res.answer_english or res.answer  # the English answer that was checked, before translation
        ok = ((not res.abstained) and keyword_match(verified, case.get("answer_keywords") or [])) if relevant \
            else res.abstained
        language_ok = reply_language_ok(item["language"], res.answer)
        numbers = {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", re.sub(r"\[\d+\]", "", verified))}
        shown = res.answer.replace(",", "")
        numbers_ok = all(n in shown for n in numbers) if numbers and not res.abstained else None
        rows.append({"id": item["id"], "source_id": item["source_id"], "language": item["language"],
                     "question": item["question"], "understood_as": res.rewritten_query,
                     "english_question": case["question"], "answer": res.answer[:400],
                     "correct": bool(ok), "english_correct": bool(english.get(item["source_id"])),
                     "abstained": res.abstained, "language_ok": language_ok, "numbers_preserved": numbers_ok})

    return summarize_multilingual(rows)


# common Hindi function words written in Latin letters ("ka total amount 4,72,000 hai"); a Hinglish reply is in
# Latin script and contains at least one of them
_HINGLISH_REPLY_WORDS = {"hai", "hain", "ka", "ki", "ke", "ko", "mein", "se", "kiye", "kiya", "gaye", "gaya", "gayi",
                         "diya", "liye", "nahi", "nahin", "aur", "tak", "milti", "milta", "hota", "hoti", "karna",
                         "sakte", "sakta", "wale", "wala", "kitna", "kitne", "kya", "kaun", "bhi", "yeh", "jo"}


def reply_language_ok(language: str, answer: str) -> bool:
    """Is the shown answer in the language the question was asked in?"""
    if language == "hindi":
        return bool(_DEVANAGARI.search(answer))
    words = set(re.findall(r"[a-z]+", answer.lower()))
    return not _DEVANAGARI.search(answer) and bool(words & _HINGLISH_REPLY_WORDS)


def summarize_multilingual(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    for r in rows:  # re-checked here so stored runs are scored with the current rules
        r["language_ok"] = reply_language_ok(r["language"], r["answer"])

    def summary(sub):
        vals = [1.0 if r["correct"] else 0.0 for r in sub]
        eng = [1.0 if r["english_correct"] else 0.0 for r in sub]
        nums = [r["numbers_preserved"] for r in sub if r["numbers_preserved"] is not None]
        return {"questions": len(sub), "accuracy": round(100 * sum(vals) / len(vals), 1), "ci": proportion_ci(vals),
                "english_accuracy": round(100 * sum(eng) / len(eng), 1), "english_ci": proportion_ci(eng),
                "reply_in_same_language": round(100 * sum(r["language_ok"] for r in sub) / len(sub), 1),
                "numbers_preserved": round(100 * sum(nums) / len(nums), 1) if nums else None}

    return {"overall": summary(rows),
            "by_language": {lang: summary([r for r in rows if r["language"] == lang]) for lang in ("hindi", "hinglish")},
            "rows": rows}


# ---------------------------------------------------------------- orchestration
def run_advanced(reserve: int = 250, progress: Progress = None, docs_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Runs every stage that has not finished yet (finished stages are kept in data/eval_cache/advanced/) and
    writes evaluation/results/advanced_eval.{json,md}. Safe to stop and re-run at any time."""
    stage_dir = Config.DATA_DIR / "eval_cache" / "advanced"
    stage_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = Path(docs_dir or Config.SAMPLE_DOCS_DIR)
    cases = json.loads(Config.EVAL_DATASET.read_text(encoding="utf-8"))["test_cases"]
    cases_by_id = {c["id"]: c for c in cases}
    ml_path = Config.EVAL_DATASET.parent / "multilingual_dataset.json"
    items = json.loads(ml_path.read_text(encoding="utf-8"))["test_cases"]

    llm = GuardedLLM(stage_dir / "groq_cache.jsonl", reserve=reserve)
    store = None
    paused: Optional[str] = None

    def check():
        if llm.problem:
            raise BudgetPaused(llm.problem)

    def stage(name: str, fn):
        nonlocal paused
        path = stage_dir / f"{name}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        if paused:
            return None
        sub = (lambda f, m: progress(STAGES.index(name) / len(STAGES) + f / len(STAGES), m)) if progress else None
        try:
            data = fn(sub)
        except BudgetPaused as e:
            paused = str(e)
            return None
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def get_store():
        nonlocal store
        if store is None:
            store = build_indexes(docs_dir)["structured"]
        return store

    rec = {
        "documind_offline": stage("documind_offline", lambda p: run_documind(get_store(), cases, None, p, "DocuMind offline")),
        "llm_only": stage("llm_only", lambda p: run_llm_only(cases, llm, p)),
        "documind_llm": stage("documind_llm", lambda p: run_documind(get_store(), cases, llm, p, "DocuMind + LLM", check)),
    }
    english = score_records(cases, rec["documind_llm"], 5)["per_question"] if rec["documind_llm"] else {}
    # the (smaller) multilingual stage runs before the LangChain baseline, so it finishes first when the daily
    # LLM allowance only covers part of the remaining work
    multilingual = stage("multilingual", lambda p: run_multilingual(items, cases_by_id, get_store(), llm,
                                                                    english, p, check)) if english else None
    if multilingual:
        multilingual = summarize_multilingual(multilingual["rows"])
    rec["langchain"] = stage("langchain", lambda p: run_langchain(cases, llm, docs_dir, p))
    scores = {k: score_records(cases, v, 4 if k == "langchain" else 5) for k, v in rec.items() if v}
    report = build_report(cases, rec, scores, multilingual, llm, paused, reserve)
    Config.EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (Config.EVAL_RESULTS_DIR / RESULTS_FILE).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    (Config.EVAL_RESULTS_DIR / "advanced_eval.md").write_text(to_markdown(report), encoding="utf-8")
    if progress:
        progress(1.0, "Advanced evaluation saved" if not paused else paused)
    return report


SYSTEM_DESCRIPTIONS = {
    "llm_only": "The same LLM answering from its own knowledge, without any documents",
    "langchain": "LangChain RecursiveCharacterTextSplitter (1000/200), same MiniLM embeddings, top-4 cosine "
                 "retrieval, LangChain's standard RAG prompt, same LLM",
    "documind_offline": "Full DocuMind pipeline, extractive answers (no LLM)",
    "documind_llm": "Full DocuMind pipeline (hybrid search, re-ranking, refusal, verification) with the same LLM",
}


def build_report(cases, rec, scores, multilingual, llm: GuardedLLM, paused, reserve) -> Dict[str, Any]:
    order = ["llm_only", "langchain", "documind_offline", "documind_llm"]
    systems = []
    for key in order:
        s = scores.get(key)
        row = {"key": key, "name": STAGE_LABELS[key], "description": SYSTEM_DESCRIPTIONS[key], "done": s is not None}
        if s:
            row.update({k: v for k, v in s.items() if k != "per_question"})
        systems.append(row)
    significance = []
    ours = scores.get("documind_llm")
    for other in ("langchain", "llm_only", "documind_offline"):
        if ours and scores.get(other):
            significance.append({"first": STAGE_LABELS["documind_llm"], "second": STAGE_LABELS[other],
                                 **mcnemar_exact(ours["per_question"], scores[other]["per_question"])})
    errors = {key: {"name": STAGE_LABELS[key], **error_analysis(cases, rec[key], scores[key]["per_question"])}
              for key in ("documind_llm", "documind_offline", "langchain") if scores.get(key)}
    done = [k for k in STAGES if (Config.DATA_DIR / "eval_cache" / "advanced" / f"{k}.json").exists()]
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "llm": f"groq/{Config.GROQ_MODEL}",
        "questions": len(cases),
        "status": {"complete": len(done) == len(STAGES), "finished_stages": [STAGE_LABELS[k] for k in done],
                   "pending_stages": [STAGE_LABELS[k] for k in STAGES if k not in done], "paused_reason": paused},
        "groq": {"calls_this_run": llm.calls, "answers_from_cache": llm.cache_hits,
                 "remaining_requests_today": llm.remaining_requests, "reserve_for_website": reserve},
        "systems": systems,
        "significance": significance,
        "error_analysis": errors,
        "multilingual": multilingual,
        "method": {
            "confidence_intervals": "95% Wilson score interval for each share of correct answers",
            "significance": "exact McNemar test on paired per-question outcomes",
            "baseline_refusal": "a baseline answer that says it does not know counts as a refusal",
            "multilingual_scoring": "the verified English answer (before translation back) is scored against the "
                                    "English original's reference keywords; the shown answer is checked for the "
                                    "question's language and for numbers surviving translation",
        },
    }


def to_markdown(r: Dict[str, Any]) -> str:
    f = lambda v, u="%": "–" if v is None else f"{v}{u}"
    lines = [f"# Advanced evaluation ({r['created_at']})", "", f"{r['questions']} questions; LLM `{r['llm']}`.", ""]
    if not r["status"]["complete"]:
        lines += [f"**Incomplete** - pending: {', '.join(r['status']['pending_stages'])}. "
                  f"{r['status']['paused_reason'] or ''}", ""]
    lines += ["## Compared with standard approaches", "",
              "| System | Answer correct (95% CI) | Held-out test (95% CI) | Abstention acc. | Recall@1 | Faithfulness |",
              "|---|:---:|:---:|:---:|:---:|:---:|"]
    for s in r["systems"]:
        if s["done"]:
            lines.append(f"| {s['name']} | {s['answer_correctness']}% ({s['ci'][0]}–{s['ci'][1]}) | "
                         f"{s['answer_correctness_test']}% ({s['ci_test'][0]}–{s['ci_test'][1]}) | "
                         f"{f(s['abstention_accuracy'])} | {f(s['recall_at_1'])} | {f(s['faithfulness'])} |")
        else:
            lines.append(f"| {s['name']} | pending | | | | |")
    if r["significance"]:
        lines += ["", "| Comparison | Only first correct | Only second correct | McNemar p |", "|---|:---:|:---:|:---:|"]
        lines += [f"| {x['first']} vs {x['second']} | {x['only_first_correct']} | {x['only_second_correct']} | "
                  f"{x['p_value']} |" for x in r["significance"]]
    for key, ea in r["error_analysis"].items():
        lines += ["", f"## Error analysis - {ea['name']} ({ea['total_errors']} of {ea['questions']} wrong)", "",
                  "| Failure type | Count | Share |", "|---|:---:|:---:|"]
        lines += [f"| {c['label']} | {c['count']} | {c['share']}% |" for c in ea["categories"]]
        refused = next(c for c in ea["categories"] if c["key"] == "wrongly_refused")
        if refused["count"]:
            lines += ["", f"Of the {refused['count']} wrong refusals, the right document had been found in "
                          f"{refused['right_document_found']}; in the other {refused['count'] - refused['right_document_found']} "
                          f"search never found it."]
    m = r.get("multilingual")
    if m:
        lines += ["", "## Multilingual benchmark", "",
                  "| Language | Questions | Accuracy (95% CI) | Same questions in English | Reply in same language | Numbers preserved |",
                  "|---|:---:|:---:|:---:|:---:|:---:|"]
        for name, s in [("Hindi", m["by_language"]["hindi"]), ("Hinglish", m["by_language"]["hinglish"]),
                        ("All", m["overall"])]:
            lines.append(f"| {name} | {s['questions']} | {s['accuracy']}% ({s['ci'][0]}–{s['ci'][1]}) | "
                         f"{s['english_accuracy']}% | {s['reply_in_same_language']}% | {f(s['numbers_preserved'])} |")
    return "\n".join(lines) + "\n"
