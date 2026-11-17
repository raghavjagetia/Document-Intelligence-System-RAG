"""
Hybrid Retriever
Combines dense semantic search (vector store) with sparse BM25 keyword search
using Reciprocal Rank Fusion (Cormack et al., SIGIR 2009):

    RRF(d) = sum over rankers r of  1 / (k + rank_r(d))

BM25 (Robertson & Zaragoza, 2009) with Lucene's non-negative IDF:
    idf(t)  = ln(1 + (N - df + 0.5) / (df + 0.5))
    score   = sum_t idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |d| / avgdl))

The tokenizer keeps identifiers such as "INV-2026-8842" intact *and* emits their
parts, so exact-ID lookups score highly while partial matches still work.
"""
import math
import re
import threading
from collections import Counter
from typing import Any, Dict, List, Optional

from .config import Config
from .text_utils import doc_title

STOPWORDS = set("""
a an the and or but if of to in on at by for with from as is are was were be been being this that these those
it its into than then there their them they he she his her we our you your i me my do does did done have has had
what which who whom whose when where why how can could should would may might will shall not no yes so such
about any all each per also more most other some only own same too very just over under up down out
""".split())

TOKEN_RE = re.compile(r"[a-z0-9₹$][a-z0-9₹$\-_./]*[a-z0-9]|[a-z0-9₹$]")


_SUFFIXES = ("ations", "ation", "ments", "ment", "ings", "ing", "ies", "ied", "ers", "er", "ed", "es", "s")


def stem(word: str) -> str:
    """Light suffix-stripping stemmer (declaring/declared/declares -> declar). Leaves IDs and numbers alone."""
    if not word.isalpha() or len(word) <= 4:
        return word
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            return word[: -len(suf)] + ("y" if suf in ("ies", "ied") else "")
    return word


def tokenize(text: str, with_parts: bool = True) -> List[str]:
    """
    Lower-case, drop stop words, stem plain words. Compound identifiers such as
    INV-2026-8842 are kept whole and (with_parts=True) also split into parts.
    """
    tokens: List[str] = []
    for tok in TOKEN_RE.findall((text or "").lower()):
        tok = tok.strip("./-_")
        if not tok or tok in STOPWORDS:
            continue
        tokens.append(stem(tok))
        if with_parts and any(ch in tok for ch in "-_/."):
            tokens.extend(stem(p) for p in re.split(r"[-_/.]", tok) if p and p not in STOPWORDS)
    return tokens


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs: List[Dict[str, Any]] = []
        self.tfs: List[Counter] = []
        self.lengths: List[int] = []
        self.idf: Dict[str, float] = {}
        self.avgdl = 1.0
        self.postings: Dict[str, List[int]] = {}

    def build(self, chunks: List[Dict[str, Any]]) -> None:
        self.docs = chunks
        self.tfs, self.lengths, self.postings = [], [], {}
        df: Counter = Counter()
        for i, c in enumerate(chunks):
            toks = tokenize(f"{doc_title(c.get('filename', ''))} {c.get('section', '')} {c.get('content', '')}")
            tf = Counter(toks)
            self.tfs.append(tf)
            self.lengths.append(len(toks))
            for term in tf:
                df[term] += 1
                self.postings.setdefault(term, []).append(i)
        n = len(chunks)
        self.avgdl = (sum(self.lengths) / n) if n else 1.0
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, allowed: Optional[set] = None, top_k: int = 30) -> List[Dict[str, Any]]:
        scores: Dict[int, float] = {}
        for term in set(tokenize(query)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i in self.postings.get(term, []):
                if allowed is not None and self.docs[i]["chunk_id"] not in allowed:
                    continue
                tf = self.tfs[i][term]
                denom = tf + self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avgdl)
                scores[i] = scores.get(i, 0.0) + idf * tf * (self.k1 + 1) / denom
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        results = []
        for rank, (i, s) in enumerate(ranked, start=1):
            item = dict(self.docs[i])
            item["bm25_score"] = s
            item["bm25_rank"] = rank
            results.append(item)
        return results


class HybridRetriever:
    def __init__(self, vector_store, rrf_k: int = Config.RRF_K):
        self.store = vector_store
        self.rrf_k = rrf_k
        self.bm25 = BM25Index()
        self._bm25_version = -1
        self._lock = threading.Lock()

    def _ensure_bm25(self) -> None:
        with self._lock:
            if self._bm25_version != self.store.version:
                self.bm25.build(list(self.store.iter_chunks()))
                self._bm25_version = self.store.version

    def bm25_search(self, query: str, top_k: int, user_id: Optional[str], domain: Optional[str] = None,
                    doc_id: Optional[str] = None) -> List[Dict[str, Any]]:
        self._ensure_bm25()
        allowed = {self.store.metadata[v]["chunk_id"] for v in self.store.filter_ids(user_id, domain, doc_id)}
        if not allowed:
            return []
        return self.bm25.search(query, allowed=allowed, top_k=top_k)

    def search(self, query: str, top_k: int = Config.CANDIDATE_K, user_id: Optional[str] = None,
               domain: Optional[str] = None, doc_id: Optional[str] = None,
               use_dense: bool = True, use_bm25: bool = True) -> List[Dict[str, Any]]:
        """
        Returns up to top_k candidates sorted by fused score. Each item carries
        `retrieval_score` in [0, 1] (normalised fused score) plus per-ranker ranks.
        """
        dense = self.store.search(query, top_k, user_id, domain, doc_id) if use_dense else []
        sparse = self.bm25_search(query, top_k, user_id, domain, doc_id) if use_bm25 else []

        if use_dense and not use_bm25:
            for r in dense:
                r["retrieval_score"] = max(0.0, r["dense_score"])
                r["retrieval_method"] = "semantic"
            return dense
        if use_bm25 and not use_dense:
            top = sparse[0]["bm25_score"] if sparse else 1.0
            for r in sparse:
                r["retrieval_score"] = r["bm25_score"] / top
                r["retrieval_method"] = "bm25"
            return sparse

        fused: Dict[str, Dict[str, Any]] = {}
        for res in dense + sparse:
            item = fused.setdefault(res["chunk_id"], dict(res))
            item.update({k: v for k, v in res.items() if k.endswith(("_score", "_rank"))})
        for cid, item in fused.items():
            score = 0.0
            if "dense_rank" in item:
                score += 1.0 / (self.rrf_k + item["dense_rank"])
            if "bm25_rank" in item:
                score += 1.0 / (self.rrf_k + item["bm25_rank"])
            item["rrf_score"] = score
        ranked = sorted(fused.values(), key=lambda x: x["rrf_score"], reverse=True)[:top_k]
        best = 2.0 / (self.rrf_k + 1)  # maximum achievable RRF score (rank 1 in both lists)
        for r in ranked:
            r["retrieval_score"] = r["rrf_score"] / best
            r["retrieval_method"] = "hybrid_rrf"
        return ranked
