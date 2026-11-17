"""
Reranker
Second-stage relevance scoring of (query, passage) pairs.
- Primary: cross-encoder ms-marco-MiniLM-L-6-v2 (Nogueira & Cho, 2019 style
  BERT re-ranking). The logit is mapped to [0, 1] with a sigmoid.
- Fallback: a transparent lexical scorer (query-term coverage + exact phrase /
  identifier bonuses), reported as type "lexical".
"""
import math
import re
from typing import Any, Dict, List

from .config import Config
from .hybrid_retriever import tokenize
from .models import get_cross_encoder
from .text_utils import doc_title


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class Reranker:
    def __init__(self):
        self.model = get_cross_encoder()

    @property
    def kind(self) -> str:
        return "cross-encoder" if self.model is not None else "lexical"

    @property
    def model_name(self) -> str:
        return Config.RERANKER_MODEL if self.model is not None else "lexical-overlap"

    @property
    def abstain_threshold(self) -> float:
        return Config.ABSTAIN_THRESHOLD if self.model is not None else Config.ABSTAIN_THRESHOLD_LEXICAL

    def score_pairs(self, query: str, passages: List[str]) -> List[float]:
        if not passages:
            return []
        if self.model is not None:
            logits = self.model.predict([(query, p) for p in passages], batch_size=32, show_progress_bar=False)
            return [_sigmoid(float(s)) for s in logits]
        return self._lexical_scores(query, passages)

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        scores = self.score_pairs(query, [f"{doc_title(c.get('filename', ''))} | {c.get('section', '')}\n{c['content']}"
                                          for c in candidates])
        for c, s in zip(candidates, scores):
            c["rerank_score"] = round(float(s), 4)
        return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)[:top_n]

    @staticmethod
    def _lexical_scores(query: str, passages: List[str]) -> List[float]:
        """
        IDF-weighted query-term coverage, IDF computed over the candidate set so terms
        shared by every candidate count little. Identifiers count as one unit.
        """
        q_terms = set(tokenize(query, with_parts=False))
        if not q_terms:
            return [0.0] * len(passages)
        p_terms = [set(tokenize(p)) for p in passages]
        n = len(passages)
        idf = {t: math.log(1 + (n + 1) / (1 + sum(t in ps for ps in p_terms))) for t in q_terms}
        total = sum(idf.values())
        scores = []
        for passage, ps in zip(passages, p_terms):
            coverage = sum(idf[t] for t in q_terms if t in ps) / total
            id_bonus = 0.15 * sum(1 for t in q_terms if re.search(r"\d", t) and t in ps)
            phrase_bonus = 0.15 if query.lower().strip(" ?") in passage.lower() else 0.0
            scores.append(min(0.99, 0.85 * coverage + id_bonus + phrase_bonus))
        return scores
