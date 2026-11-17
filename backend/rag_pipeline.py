"""
RAG Pipeline
  1. Conversational query rewriting (LLM, or rule-based when no LLM is configured)
  2. Hybrid retrieval: dense (FAISS) + BM25, fused with Reciprocal Rank Fusion
  3. Cross-encoder reranking
  4. Evidence threshold -> abstain instead of hallucinating
  5. Answer generation:
       - LLM (Groq / Gemini / Claude) with numbered-source prompt, or
       - neural extractive answering: the cross-encoder scores every sentence of
         the top passages and the best-supported sentences form the answer
  6. Grounding verification: every answer sentence must be semantically supported
     by a retrieved sentence (embedding cosine) -> grounding score
  7. Citations for the sources actually referenced in the answer
"""
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np

from .config import Config
from .hybrid_retriever import HybridRetriever, stem, tokenize
from .llm import LLMClient
from .models import get_embedder
from .reranker import Reranker
from .text_utils import split_prose

logger = logging.getLogger(__name__)

ABSTAIN_MESSAGE = ("I could not find sufficient information in the provided documents to answer this "
                   "question. Try rephrasing it, widening the search scope, or uploading a relevant document.")

SYSTEM_PROMPT = """You are DocuMind, a document question-answering assistant.
Answer ONLY from the numbered sources provided. Rules:
- Cite every factual statement with its source number in square brackets, e.g. [1] or [2][3].
- Quote numbers, dates, amounts and IDs exactly as written in the sources.
- Be concise: 1-4 sentences, or a short bullet list when listing several items.
- If the sources do not contain the answer, reply exactly: "INSUFFICIENT_EVIDENCE"."""

# "Detailed" answer style: same grounding rules, fuller and structured
DETAILED_SYSTEM_PROMPT = """You are DocuMind, a document question-answering assistant.
Answer ONLY from the numbered sources provided. Rules:
- Cite every factual statement with its source number in square brackets, e.g. [1] or [2][3].
- Quote numbers, dates, amounts and IDs exactly as written in the sources.
- Start with a one-sentence direct answer in **bold**.
- Then give the useful details as 2-5 short bullet points: conditions, exceptions, limits, who it applies to,
  related figures, and differences between documents or versions (e.g. 2025 vs 2026) when the sources show them.
- Use only details that are relevant to the question; do not pad. Keep it under about 150 words.
- If the sources do not contain the answer, reply exactly: "INSUFFICIENT_EVIDENCE"."""

ANSWER_STYLES = ("quick", "detailed", "quote")

_MONTHS = r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
ANSWER_TYPE_PATTERNS = {
    "org": re.compile(r"\b(pvt\.?\s*ltd|ltd\b|limited|llp|inc\b|corporation|bill(ed)? to)", re.IGNORECASE),
    "cause": re.compile(r"\b(caused by|due to|because|root cause|as a result of)\b", re.IGNORECASE),
    "diagnosis": re.compile(r"\bdiagnos", re.IGNORECASE),
    "money": re.compile(r"(₹|rs\.?\s?\d|inr|\$|usd|€|£|\d{1,3}(,\d{2,3})+|\blakh|\bcrore)", re.IGNORECASE),
    "date": re.compile(rf"(\b\d{{1,2}}\s*({_MONTHS})|\b({_MONTHS})\w*\s+\d{{1,2}}|\b\d{{4}}-\d{{2}}-\d{{2}}|"
                       rf"\b\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}|\bq[1-4]\b|\b({_MONTHS})\w*\s+\d{{4}})", re.IGNORECASE),
    "number": re.compile(r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen|twenty|thirty)\b",
                         re.IGNORECASE),
}

# document identifiers such as INV-2026-8824, PO-HLX-5211, PAT-55102, MOM-ORN-43
ID_RE = re.compile(r"\b[A-Za-z]{2,}(?:-[A-Za-z0-9]+)*-\d[\w-]*\b")

# question words that say nothing about WHAT is being asked (used for coverage-based abstention)
GENERIC_TERMS = {stem(w) for w in """
what which who whom whose when where why how much many does did do is are was were will would can could should
the a an of in on at to for from by with about according per under between and or any all each every
tell give show list name describe explain mention state find provide get gets got have has had
company companies organisation organization firm business employee employees staff people person team
document documents policy policies report reports record records file files
current currently total amount number value detail details information info
""".split()}

COMPARATIVE_RE = re.compile(r"\b(compare|comparison|chang\w*|differ\w*|between|versus|vs\.?|increase\w*|decrease\w*)\b",
                            re.IGNORECASE)

# ---------------------------------------------------------------- multilingual questions
# The embedding model, the cross-encoder and the documents are English. A question in another language
# (Hindi, Tamil, Spanish, ... or Hinglish = Hindi in Latin letters) is translated to English for retrieval,
# answered and grounding-checked in English, and the answer is then translated back into the asker's language.
# Distinctly Hindi words (no common English homographs) used to recognise romanised Hindi
HINGLISH_WORDS = set("""
kya kyaa kitna kitne kitni kaun kaunsa kaunse kab kahan kaha kyun kyon kaise kaisa kaisi hai hain hoga hogi
hota hoti tha thi mein mai milti milta milte milega milegi batao bataiye bataye btao chahiye nahi nahin aur
sakta sakte sakti karna karne karte kare wala wali wale liye kuch koi mujhe humein hamein apna apni iska uska
unka kiska kisne diya gaya gayi hua hui raha rahi rahe yeh woh kitnee chhutti chutti chhuttiyan chuttiyan
saal mahina mahine tankhwah vetan paisa paise rupaye kab tak bhi sabse jyada zyada kam kaam naukri kampani
""".split())

TRANSLATE_QUESTION_SYSTEM = ("You translate questions into English for a document search engine. "
                             "Output only the English question, nothing else.")
TRANSLATE_ANSWER_SYSTEM = ("You translate answers for the user of a document assistant. "
                           "Output only the translation, nothing else.")


def needs_translation(question: str) -> bool:
    """True when the question is (probably) not English: it uses non-Latin letters or accented letters,
    or it contains at least two distinctly Hindi words written in Latin letters (Hinglish)"""
    if any(ch.isalpha() and ord(ch) > 0x24F for ch in question):  # beyond Latin Extended: Devanagari, Tamil, ...
        return True
    if sum(ch.isalpha() and ord(ch) > 0x7F for ch in question) >= 2:  # accented Latin: Spanish, French, German ...
        return True
    words = set(re.findall(r"[a-z]+", question.lower()))
    return len(words & HINGLISH_WORDS) >= 2


def _strip_reasoning(text: str) -> str:
    """Drop <think>...</think> blocks that some reasoning models emit before their output"""
    return re.sub(r"<think>.*?(</think>|$)", "", text, flags=re.S | re.I).strip()


FOLLOWUP_PATTERNS = re.compile(
    r"^(and\s+)?(what|how)\s+about\b|^and\b|^also\b|\b(it|its|that|this|they|them|those|these|he|she|his|her)\b",
    re.IGNORECASE,
)


@dataclass
class PipelineSettings:
    use_dense: bool = True
    use_bm25: bool = True
    use_reranker: bool = True
    use_rewrite: bool = True
    use_abstention: bool = True
    use_llm: bool = True
    top_k: int = Config.TOP_K
    candidate_k: int = Config.CANDIDATE_K
    # how the answer is written: "quick" (default, used by the benchmark), "detailed" or "quote"
    answer_style: str = "quick"

    @classmethod
    def for_mode(cls, retrieval_mode: str) -> "PipelineSettings":
        mode = (retrieval_mode or "hybrid").lower()
        return cls(use_dense=mode in ("hybrid", "semantic"), use_bm25=mode in ("hybrid", "bm25"))


@dataclass
class RAGResult:
    question: str
    rewritten_query: str
    answer: str
    contexts: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    grounded: bool
    grounding_score: float
    confidence_score: float
    abstained: bool
    generation_mode: str
    latency_seconds: float
    retrieval_mode: str
    timings: Dict[str, float] = field(default_factory=dict)
    # for a question asked in another language: the English answer that was verified and then translated
    answer_english: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "contexts"}


def split_sentences(text: str) -> List[str]:
    """Sentence splitter that also treats list items / table rows / records as units"""
    units: List[str] = []
    rows = [l.strip() for l in text.split("\n") if l.strip()]
    # "Label:" on one line and its value on the next (slide KPI tiles, forms) -> one unit
    merged: List[str] = []
    for line in rows:
        if merged and merged[-1].endswith(":") and not line.startswith("|") and len(merged[-1]) <= 60 \
                and len(line) <= 80:
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    rows = merged
    header: Optional[List[str]] = None
    for line in rows:
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if header is None:
                header = cells
                continue
            units.append("; ".join(f"{h}: {c}" for h, c in zip(header, cells) if c))
            continue
        header = None
        if line.startswith("## "):
            continue
        if re.match(r"^(Record \d+:|[-*•]\s|\d+[.)]\s)", line):
            units.append(line.lstrip("-*• "))
            continue
        for s in split_prose(line):
            if len(s) > 2:
                units.append(s)
    return units


class RAGPipeline:
    def __init__(self, vector_store, llm: Optional[LLMClient] = None, reranker: Optional[Reranker] = None):
        self.store = vector_store
        self.retriever = HybridRetriever(vector_store)
        self.reranker = reranker or Reranker()
        self.llm = llm or LLMClient()
        self.embedder = get_embedder()

    # ------------------------------------------------------------------ rewriting
    def is_followup(self, question: str) -> bool:
        return bool(FOLLOWUP_PATTERNS.search(question.strip())) or len(question.split()) <= 3

    @staticmethod
    def _answer_context(previous_answer: Optional[str]) -> str:
        """The previous answer as context for a follow-up: citation markers and quote formatting removed, shortened"""
        if not previous_answer:
            return ""
        text = re.sub(r"\[\d+\]", "", previous_answer)
        text = re.sub(r"^>\s*—.*$", "", text, flags=re.M)
        text = re.sub(r"[>*#]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 600:
            text = text[:600].rsplit(" ", 1)[0] + " …"
        return f"Previous answer: {text}\n"

    def rewrite_query(self, question: str, history: List[str], use_llm: bool = True,
                      previous_answer: Optional[str] = None) -> str:
        """Turn an elliptical follow-up into a standalone query using previous user questions and the previous
        answer ("Who approved it?" after an answer about a purchase order -> "Who approved PO-2026-3317?")"""
        history = [h for h in history if h and h.strip()]
        if not history or not self.is_followup(question):
            return question
        previous = history[-1]
        if use_llm and self.llm.available:
            try:
                prompt = (f"Previous questions:\n" + "\n".join(f"- {h}" for h in history[-3:]) + "\n" +
                          self._answer_context(previous_answer) +
                          f"\nFollow-up question: {question}\n\nRewrite the follow-up as a single standalone "
                          f"question that keeps all needed context. Replace words such as 'it', 'that', 'they' or "
                          f"'the second one' with what they refer to in the previous questions or the previous "
                          f"answer (a document, ID, person, amount or policy). Output only the rewritten question.")
                rewritten = _strip_reasoning(self.llm.generate(prompt, max_tokens=80)).strip().strip('"')
                if 3 < len(rewritten) < 300:
                    return rewritten.splitlines()[0]
            except Exception as e:  # e.g. a rate limit: fall back to the rule-based rewrite
                logger.warning("LLM query rewrite failed (%s); using the rule-based rewrite", e)
        return self._heuristic_rewrite(question, previous)

    @staticmethod
    def _heuristic_rewrite(question: str, previous: str) -> str:
        q = question.strip().rstrip("?.! ")
        prev = previous.strip().rstrip("?.! ")
        m = re.match(r"^(?:and\s+)?(?:what|how)\s+about\s+(?:the\s+)?(.+)$", q, re.IGNORECASE)
        if m:
            phrase = m.group(1).strip()
            head = phrase.split()[-1].lower().rstrip("s")
            words = prev.split()
            for j, w in enumerate(words):
                if re.sub(r"\W", "", w.lower()).rstrip("s") == head:
                    start = j
                    # absorb up to two modifiers before the head noun ("annual leave", "notice period")
                    while start > 0 and j - start < 2 and words[start - 1].lower() not in (
                            "of", "the", "a", "an", "for", "in", "on", "to", "is", "are", "many", "much", "what",
                            "how", "does", "do", "get", "under", "per", "with"):
                        start -= 1
                    return " ".join(words[:start] + [phrase] + words[j + 1:]) + "?"
            return f"{phrase} ({prev})?"
        return f"{q} (context: {prev})?"

    # ------------------------------------------------------------------ translation
    def translate_question(self, question: str, history: List[str],
                           previous_answer: Optional[str] = None) -> Optional[str]:
        """English, standalone version of a non-English question (None if the LLM is unavailable or fails)"""
        history = [h for h in history if h and h.strip()][-3:]
        context = ("Earlier questions in this conversation (use them only if the new question is a follow-up):\n" +
                   "\n".join(f"- {h}" for h in history) + "\n" + self._answer_context(previous_answer) + "\n"
                   ) if history else ""
        prompt = (f"{context}Question: {question}\n\nTranslate the question into clear, standalone English. Keep names, "
                  f"numbers, amounts, dates and IDs exactly as written. Output only the English question.")
        try:
            english = _strip_reasoning(self.llm.generate(prompt, TRANSLATE_QUESTION_SYSTEM, max_tokens=150))
        except Exception:
            return None
        english = english.strip().strip('"').splitlines()[0].strip() if english.strip() else ""
        return english if 3 < len(english) < 400 else None

    def _stream_translated(self, text: str, question: str, out: List[str]) -> Iterator[str]:
        """Stream `text` translated into the language (and script) of `question`; appends the full translation
        to `out`. Falls back to the English text if the LLM fails before producing anything."""
        prompt = (f"User's question: {question}\n\nAnswer (in English):\n{text}\n\n"
                  "Translate the answer into the same language and script as the user's question. If the question is "
                  "Hindi written in Latin letters (Hinglish), write the answer in Hinglish. Keep citation markers such "
                  "as [1] or [2] exactly as they are, and keep numbers, amounts, dates, names, document names and IDs "
                  "unchanged. Output only the translated answer.")
        buffer = ""
        try:
            in_think = False
            for piece in self.llm.stream(prompt, TRANSLATE_ANSWER_SYSTEM, max_tokens=Config.LLM_MAX_TOKENS + 300):
                buffer += piece
                # suppress a leading <think> block of reasoning models
                if buffer.lstrip().lower().startswith("<think>") and "</think>" not in buffer.lower():
                    in_think = True
                    continue
                if in_think:
                    in_think = False
                    piece = _strip_reasoning(buffer)
                yield piece
            translated = _strip_reasoning(buffer)
            out.append(translated or text)
        except Exception:
            if _strip_reasoning(buffer):
                out.append(_strip_reasoning(buffer))
            else:
                for tok in self._chunk_text(text):
                    yield tok
                out.append(text)

    # ------------------------------------------------------------------ retrieval
    def retrieve(self, query: str, user_id: Optional[str], domain: Optional[str] = None,
                 doc_id: Optional[str] = None, settings: Optional[PipelineSettings] = None) -> List[Dict[str, Any]]:
        s = settings or PipelineSettings()
        candidates = self.retriever.search(query, top_k=s.candidate_k, user_id=user_id, domain=domain,
                                           doc_id=doc_id, use_dense=s.use_dense, use_bm25=s.use_bm25)
        if s.use_reranker and candidates:
            return self.reranker.rerank(query, candidates[:20], top_n=s.top_k)
        return candidates[:s.top_k]

    # ------------------------------------------------------------------ main entry points
    def answer(self, question: str, user_id: Optional[str], domain: Optional[str] = None,
               doc_id: Optional[str] = None, history: Optional[List[str]] = None,
               settings: Optional[PipelineSettings] = None, previous_answer: Optional[str] = None) -> RAGResult:
        result = None
        for event, payload in self.stream(question, user_id, domain, doc_id, history, settings, previous_answer):
            if event == "done":
                result = payload
        return result

    def stream(self, question: str, user_id: Optional[str], domain: Optional[str] = None,
               doc_id: Optional[str] = None, history: Optional[List[str]] = None,
               settings: Optional[PipelineSettings] = None,
               previous_answer: Optional[str] = None) -> Iterator[Tuple[str, Any]]:
        """
        Generator of (event, payload):
          ("meta",  {"rewritten_query", "citations"(all retrieved), "contexts"})
          ("token", str)
          ("done",  RAGResult)
        """
        s = settings or PipelineSettings()
        t0 = time.perf_counter()
        timings: Dict[str, float] = {}
        mode = "hybrid" if (s.use_dense and s.use_bm25) else ("semantic" if s.use_dense else "bm25")

        # non-English question: retrieve, answer and verify in English, then translate the answer back
        english = None
        if s.use_llm and self.llm.available and needs_translation(question):
            english = self.translate_question(question, history or [], previous_answer)
        translate = english is not None
        if translate:
            rewritten = english
        else:
            rewritten = self.rewrite_query(question, history or [], use_llm=s.use_llm,
                                           previous_answer=previous_answer) if s.use_rewrite else question
        timings["rewrite"] = time.perf_counter() - t0

        t1 = time.perf_counter()
        contexts = self.retrieve(rewritten, user_id, domain, doc_id, s)
        timings["retrieval"] = time.perf_counter() - t1

        top_score = self._top_score(contexts, s)
        abstain = not contexts or (s.use_abstention and s.use_reranker and self._should_abstain(rewritten, contexts))
        all_citations = self._build_citations(contexts, list(range(1, len(contexts) + 1)))
        yield "meta", {"rewritten_query": rewritten, "citations": all_citations, "contexts": contexts}

        if not translate and not (s.use_llm and self.llm.available) and needs_translation(question):
            # without an LLM there is nothing to translate with: say so instead of a generic refusal
            abstain_message = ("This question seems to be in a language other than English. Answering in other "
                               "languages needs an AI provider (e.g. a Groq API key) to be configured; until then, "
                               "please ask in English.")
            abstain = True
        else:
            abstain_message = ABSTAIN_MESSAGE

        if abstain:
            shown = [abstain_message]
            if translate:
                shown = []
                for tok in self._stream_translated(abstain_message, question, shown):
                    yield "token", tok
            else:
                for tok in self._chunk_text(abstain_message):
                    yield "token", tok
            yield "done", RAGResult(question, rewritten, shown[0], contexts, [], True, 1.0, 0.0, True,
                                    "abstained", round(time.perf_counter() - t0, 3), mode, timings)
            return

        t2 = time.perf_counter()
        answer_text, gen_mode = "", ""
        style = s.answer_style if s.answer_style in ANSWER_STYLES else "quick"
        detailed = style == "detailed"
        # "quote" never paraphrases: the answer is made of sentences copied from the documents
        if s.use_llm and self.llm.available and style != "quote":
            try:
                gen_mode = f"llm:{self.llm.label}"
                buffer, holding = "", True
                prompt = self._build_prompt(rewritten if translate else question, rewritten, contexts,
                                            n_chunks=len(contexts) if detailed else Config.LLM_CONTEXT_CHUNKS)
                for piece in self.llm.stream(prompt, DETAILED_SYSTEM_PROMPT if detailed else SYSTEM_PROMPT,
                                             Config.LLM_MAX_TOKENS + 400 if detailed else None):
                    buffer += piece
                    if translate:
                        continue  # the English answer is translated (and streamed) once it is complete
                    if holding:
                        # hold output back while it could still be the abstain token
                        if "INSUFFICIENT_EVIDENCE".startswith(buffer.strip()) or "INSUFFICIENT_EVIDENCE" in buffer:
                            continue
                        holding = False
                        yield "token", buffer
                    else:
                        yield "token", piece
                # source pointers such as "[1\u2020L3-L5]" (gpt-oss style) -> plain "[1]" citations
                answer_text = re.sub(r"\[(\d+)\u2020[^\]]*\]", r"[\1]", _strip_reasoning(buffer))
            except Exception:
                answer_text = ""
        if not answer_text:
            answer_text, _ = self._extractive_answer(rewritten, contexts, rewritten if translate else question,
                                                     max_sentences=5 if detailed else 3, as_quotes=style == "quote")
            gen_mode = f"extractive:{self.reranker.kind}"
            if not translate:
                for tok in self._chunk_text(answer_text):
                    yield "token", tok
        timings["generation"] = time.perf_counter() - t2

        if "INSUFFICIENT_EVIDENCE" in answer_text or not answer_text:
            shown = [ABSTAIN_MESSAGE]
            if translate:
                shown = []
                for tok in self._stream_translated(ABSTAIN_MESSAGE, question, shown):
                    yield "token", tok
            yield "done", RAGResult(question, rewritten, shown[0], contexts, [], True, 1.0, 0.0, True,
                                    gen_mode, round(time.perf_counter() - t0, 3), mode, timings)
            return

        t3 = time.perf_counter()
        # quote attribution lines ("> — *file.pdf, page 2* [1]") and quote markers are not claims
        claims = re.sub(r"^>\s*—.*$", "", answer_text, flags=re.M)
        claims = re.sub(r"^>\s?", "", claims, flags=re.M)
        grounding = self.grounding_score(claims, contexts, question=f"{question} {rewritten}")
        timings["grounding"] = time.perf_counter() - t3
        cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer_text) if 1 <= int(n) <= len(contexts)})
        citations = self._build_citations(contexts, cited or list(range(1, len(contexts) + 1)))
        confidence = round(0.55 * min(1.0, top_score) + 0.45 * grounding, 3)

        shown_answer = answer_text
        if translate:
            # grounding and citations were checked on the English answer; show it in the asker's language
            t4 = time.perf_counter()
            out: List[str] = []
            if style == "quote":
                # quotes stay word-for-word; a translation follows them
                for tok in self._chunk_text(answer_text + "\n\n---\n\n"):
                    yield "token", tok
            for tok in self._stream_translated(answer_text, question, out):
                yield "token", tok
            shown_answer = f"{answer_text}\n\n---\n\n{out[0]}" if style == "quote" else out[0]
            timings["translation"] = time.perf_counter() - t4

        yield "done", RAGResult(
            question=question, rewritten_query=rewritten, answer=shown_answer, contexts=contexts,
            citations=citations, grounded=grounding >= 0.7, grounding_score=round(grounding, 3),
            confidence_score=confidence, abstained=False, generation_mode=gen_mode,
            latency_seconds=round(time.perf_counter() - t0, 3), retrieval_mode=mode, timings=timings,
            answer_english=answer_text if translate else "",
        )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _top_score(contexts: List[Dict[str, Any]], s: PipelineSettings) -> float:
        if not contexts:
            return 0.0
        if s.use_reranker:
            return max(c.get("rerank_score", 0.0) for c in contexts)
        return max(min(1.0, c.get("retrieval_score", 0.0)) for c in contexts)

    @staticmethod
    def _build_prompt(question: str, rewritten: str, contexts: List[Dict[str, Any]],
                      n_chunks: Optional[int] = None) -> str:
        blocks = []
        for i, c in enumerate(contexts[:n_chunks or Config.LLM_CONTEXT_CHUNKS], start=1):
            blocks.append(f"[{i}] {c['filename']} | page {c.get('page_number', 1)} | section: {c.get('section', '')}\n"
                          f"{c['content']}")
        q = question if rewritten == question else f"{question}\n(standalone form: {rewritten})"
        return "SOURCES:\n\n" + "\n\n".join(blocks) + f"\n\nQUESTION: {q}\n\nANSWER:"

    # ------------------------------------------------------------------ abstention
    def _should_abstain(self, query: str, contexts: List[Dict[str, Any]]) -> bool:
        """
        Abstain when the evidence is weak on BOTH relevance signals (cross-encoder and dense
        similarity), or when the question hinges on a specific identifier/year that does not
        occur anywhere in the retrieved evidence (e.g. asking about a 2027 policy when only
        the 2026 policy exists).
        """
        top_rerank = max(c.get("rerank_score", 0.0) for c in contexts)
        top_dense = max(c.get("dense_score", 0.0) for c in contexts)
        if top_rerank < self.reranker.abstain_threshold and top_dense < Config.ABSTAIN_DENSE_THRESHOLD:
            return True
        # coverage: the question's subject ("pets", "share price", "canteen menu") is absent from the evidence
        # and the passages are only loosely related semantically -> the documents do not cover it
        uncovered, terms = self.uncovered_terms(query, contexts), self.content_terms(query)
        if len(uncovered) >= 2 and len(uncovered) >= 0.4 * len(terms) and top_dense < Config.ABSTAIN_COVERAGE_DENSE \
                and self.missing_subject_nouns(query, contexts, uncovered):
            return True
        return bool(self.missing_key_terms(query, contexts))

    @staticmethod
    def missing_key_terms(query: str, contexts: List[Dict[str, Any]]) -> List[str]:
        evidence = " ".join(f"{c.get('filename', '')} {c.get('section', '')} {c['content']}" for c in contexts)
        evidence = evidence.lower().replace(",", "")
        terms = [t.strip(".,?!:;()'\"") for t in re.findall(r"[A-Za-z0-9-]*\d[A-Za-z0-9-]*", query)]
        return [t for t in terms if len(t) >= 3 and t.lower().replace(",", "") not in evidence]

    @staticmethod
    def content_terms(question: str) -> List[str]:
        """Stemmed content words of a question: no stop/question words, generic words or identifiers"""
        return [t for t in tokenize(question, with_parts=False)
                if len(t) >= 3 and not re.search(r"\d", t) and t not in GENERIC_TERMS]

    @classmethod
    def uncovered_terms(cls, question: str, contexts: List[Dict[str, Any]]) -> List[str]:
        """Content words of the question that occur nowhere in the retrieved evidence"""
        evidence = set()
        for c in contexts:
            evidence.update(tokenize(f"{c.get('filename', '')} {c.get('section', '')} {c['content']}",
                                     with_parts=True))
        return [t for t in cls.content_terms(question) if t not in evidence]

    def missing_subject_nouns(self, question: str, contexts: List[Dict[str, Any]], uncovered: List[str]) -> List[str]:
        """
        Uncovered question words that are nouns (the question's subject: "pets", "share price", "canteen menu")
        and have no close synonym in the evidence. Loose paraphrase words ("someone", "quick") and nouns
        whose meaning is present under another word ("sugar" ~ "glucose") do not count.
        """
        from .document_intelligence import get_spacy  # lazy: avoids a circular import at module load
        nlp = get_spacy()
        if nlp is not None:
            nouns = {tokenize(t.text, with_parts=False)[0]: t.text.lower() for t in nlp(question)
                     if t.pos_ in ("NOUN", "PROPN") and tokenize(t.text, with_parts=False)}
            missing = {nouns[u]: u for u in uncovered if u in nouns}
        else:
            missing = {u: u for u in uncovered}
        if not missing or self.embedder.kind != "neural":
            return list(missing.values())
        vocab = sorted({w.lower() for c in contexts for w in re.findall(r"[A-Za-z][A-Za-z-]{2,}", c["content"])})
        if not vocab:
            return list(missing.values())
        words = list(missing)
        sims = self.embedder.encode(words) @ self.embedder.encode(vocab).T
        return [missing[w] for i, w in enumerate(words) if float(sims[i].max()) < Config.ABSTAIN_SYNONYM_SIM]

    # ------------------------------------------------------------------ extractive answering
    def _extractive_answer(self, query: str, contexts: List[Dict[str, Any]],
                           original_question: Optional[str] = None, max_sentences: int = 3,
                           as_quotes: bool = False) -> Tuple[str, float]:
        """
        Neural extractive QA: every sentence of the top passages is scored by the cross-encoder,
        then adjusted by (1) expected answer type, (2) novelty w.r.t. the question,
        (3) exact-identifier matching and (4) passage rank. Comparison questions take the
        best sentence from each of the two most relevant documents.
        """
        question = original_question or query
        comparative = bool(COMPARATIVE_RE.search(question))
        q_ids = [i.lower() for i in ID_RE.findall(f"{question} {query}")]
        pool = list(enumerate(contexts[:5], start=1))
        if not comparative and pool:
            # Answer from ONE document: the one carrying the identifier the question names, otherwise the
            # top-ranked one. Mixing sentences from look-alike documents (other invoices, other incidents)
            # was the main source of wrong answers.
            docs = {c["doc_id"] for _, c in pool if q_ids and any(i in c["content"].lower() for i in q_ids)}
            if not docs and as_quotes:
                # Quotes show each source verbatim, so several equally relevant documents (the 2025 and the 2026
                # policy) can all be quoted without mixing them up: keep up to 3 documents scoring close to the top
                top = pool[0][1].get("rerank_score", 0.0)
                docs = {pool[0][1]["doc_id"]}
                for _, c in pool[1:]:
                    if len(docs) < 3 and c.get("rerank_score", 0.0) >= max(0.6 * top, 0.3):
                        docs.add(c["doc_id"])
            docs = docs or {pool[0][1]["doc_id"]}
            pool = [(i, c) for i, c in pool if c["doc_id"] in docs]
        quote_docs = len({c["doc_id"] for _, c in pool}) if as_quotes and not comparative else 0
        if quote_docs > 1:
            max_sentences = max(max_sentences, 2 * quote_docs)
        candidates: List[Tuple[int, str]] = []
        for i, c in pool:
            for sent in split_sentences(c["content"]):
                if len(sent) > 600:
                    sent = sent[:600].rsplit(" ", 1)[0] + "…"
                candidates.append((i, sent))
        if not candidates:
            return "", 0.0
        answer_type = self._expected_answer_type(question) or self._expected_answer_type(query)
        if answer_type:
            # type-first selection: when some sentences carry the expected kind of answer (an amount, a date,
            # a company, a cause), choose only among them. The cross-encoder favours fluent sentences that restate
            # the question and scores terse table rows ("Total net pay 129,560") near zero, so down-weighting
            # alone cannot recover the answer. Identifiers are removed first: their digits are not amounts.
            typed = [(i, sent) for i, sent in candidates
                     if ANSWER_TYPE_PATTERNS[answer_type].search(ID_RE.sub(" ", sent))]
            candidates = typed or candidates
        scores = self.reranker.score_pairs(query, [s for _, s in candidates])
        q_tokens = set(tokenize(query, with_parts=False))
        title_tokens = {i: set(tokenize(re.sub(r"[_.]", " ", c.get("filename", "")), with_parts=False))
                        for i, c in pool}
        q_content = set(self.content_terms(question))
        ids = [t for t in q_tokens if re.search(r"\d", t) and (len(t) >= 5 or "-" in t)]
        sentences_with_id = {src for src, sent in candidates if any(i in sent.lower() for i in ids)}
        # IDs of the same family but a different value (INV-2026-8824 vs INV-2026-8842) signal the wrong record
        id_families = {i.rsplit("-", 1)[0]: i for i in ids if "-" in i}
        adjusted = []
        for score, (src, sent) in zip(scores, candidates):
            low = sent.lower()
            # identifiers contain digits/years - they must not satisfy a number/money/date expectation
            if answer_type and not ANSWER_TYPE_PATTERNS[answer_type].search(ID_RE.sub(" ", sent)):
                score *= 0.55
            s_tokens = set(tokenize(sent, with_parts=False))
            # sentences that only restate the question or the document's own title carry no answer
            known = q_tokens | title_tokens.get(src, set())
            if s_tokens and len(s_tokens - known) / len(s_tokens) < 0.34:
                score *= 0.5
            # sharing the question's own content words ("billed" -> "Bill to", "net pay") is strong evidence
            # that a sentence is the field being asked about
            shared = len((s_tokens & q_content) - title_tokens.get(src, set()))
            score *= 1.0 + 0.5 * min(shared, 3)
            if ids and not any(i in low for i in ids):
                if any(fam in low for fam in id_families):
                    score *= 0.3  # mentions a different ID of the same family -> almost certainly wrong record
                elif src in sentences_with_id:
                    score *= 0.6  # a sibling sentence in this passage carries the exact ID - prefer it
            score *= 1.0 - 0.08 * (src - 1)
            adjusted.append(score)
        ranked = sorted(zip(adjusted, candidates), key=lambda x: x[0], reverse=True)
        best = ranked[0][0]

        chosen: List[Tuple[int, str]] = []
        seen = set()

        def take(src: int, sent: str) -> None:
            key = re.sub(r"\W+", "", re.sub(r"^record \d+:", "", sent.lower()))[:80]
            if key not in seen:
                seen.add(key)
                chosen.append((src, sent))

        if comparative or quote_docs > 1:
            want = quote_docs if quote_docs > 1 else 2
            best_per_doc: Dict[str, Tuple[int, str]] = {}
            for score, (src, sent) in ranked:
                doc = contexts[src - 1]["doc_id"]
                if doc not in best_per_doc and (not answer_type or
                                                ANSWER_TYPE_PATTERNS[answer_type].search(ID_RE.sub(" ", sent))):
                    best_per_doc[doc] = (src, sent)
                if len(best_per_doc) == want:
                    break
            for src, sent in best_per_doc.values():
                take(src, sent)
        for score, (src, sent) in ranked:
            if len(chosen) >= max_sentences or (chosen and score < max(0.35 * best, 0.02)):
                break
            take(src, sent)
        if as_quotes:
            # word-for-word excerpts as block quotes, each followed by its document and page
            quotes = []
            # group the quotes by document, in the order the documents were ranked
            chosen.sort(key=lambda x: min(i for i, c in pool if c["doc_id"] == contexts[x[0] - 1]["doc_id"]))
            for src, sent in chosen:
                c = contexts[src - 1]
                quotes.append(f"> {sent.strip()}\n>\n> — *{c['filename']}, page {c.get('page_number', 1)}* [{src}]")
            return "\n\n".join(quotes), float(best)
        parts = [f"{sent.rstrip()} [{src}]" for src, sent in chosen]
        return " ".join(parts), float(best)

    @staticmethod
    def _expected_answer_type(query: str) -> Optional[str]:
        q = query.lower()
        if re.search(r"\b(which|what) (customer|client|vendor|supplier|company|party|lessor|lessee|organi[sz]ation|"
                     r"firm)\b|\bbilled to\b|\bwho is (billed|the (customer|client|vendor|supplier))\b", q):
            return "org"
        if re.search(r"\b(what caused|cause of|caused|root cause|reason for|why did)\b", q):
            return "cause"
        if re.search(r"\bdiagnos", q):
            return "diagnosis"
        if re.search(r"\b(how many|number of|by how much|how much (time|notice|leave)|how much longer|how long|"
                     r"notice period|initial term|term of|tenure)\b", q):
            return "number"
        if re.search(r"\b(how much|total|amount|cost|price|salary|fee|fees|budget|payable|paid|pay|value|"
                     r"revenue|allowance|reimburse\w*|rate|charge|charges|spend|expense|rent|deposit|ctc|"
                     r"compensation|premium)\b", q):
            return "money"
        if re.search(r"\b(when|what date|which date|deadline|due date|date|expire\w*|until|by when|start date)\b", q):
            return "date"
        if re.search(r"\b(how many|how long|how often|number of|percentage|percent|days|weeks|months|years|"
                     r"limit|minimum|maximum|duration|period)\b", q):
            return "number"
        return None

    def grounding_score(self, answer: str, contexts: List[Dict[str, Any]], question: str = "") -> float:
        """Fraction of answer sentences supported by the retrieved evidence (words that merely restate
        the question do not count as claims)"""
        answer_sents = [re.sub(r"\[\d+\]", "", s).strip() for s in split_sentences(answer)]
        # drop attribution phrases ("According to [1] and [3], ...") that carry no factual claim
        answer_sents = [re.sub(r"^(according to|as per|based on|per)\b[^,]{0,60},\s*", "", s, flags=re.I)
                        for s in answer_sents]
        answer_sents = [s for s in answer_sents if len(tokenize(s)) >= 2]
        context_sents = []
        for c in contexts:
            sents = split_sentences(c["content"])
            context_sents.extend(sents)
            # windows of two adjacent sentences: generated answers often merge facts from both
            context_sents.extend(f"{a} {b}" for a, b in zip(sents, sents[1:]))
        if not answer_sents or not context_sents:
            return 1.0 if not answer_sents else 0.0
        # a chunk's filename and section are part of its evidence: an invoice's line-item chunk does not
        # repeat "INV-2026-8842", but it comes from Invoice_INV-2026-8842.pdf
        evidence = " ".join(f"{c.get('filename', '')} {c.get('section', '')} {c['content']}" for c in contexts)
        evidence_tokens = set(tokenize(evidence, with_parts=True)) | set(tokenize(question, with_parts=True))
        supported = 0
        if self.embedder.kind == "neural":
            a = self.embedder.encode(answer_sents)
            cvec = self.embedder.encode(context_sents)
            sims = a @ cvec.T
            for i, s in enumerate(answer_sents):
                if sims[i].max() >= 0.65 or self._lexical_support(s, context_sents) >= 0.75 \
                        or self._fact_support(s, evidence, evidence_tokens):
                    supported += 1
        else:
            supported = sum(1 for s in answer_sents if self._lexical_support(s, context_sents) >= 0.6
                            or self._fact_support(s, evidence, evidence_tokens))
        return supported / len(answer_sents)

    @staticmethod
    def _fact_support(sentence: str, evidence: str, evidence_tokens: set) -> bool:
        """
        Claim-level support: every number, amount, date and identifier in the sentence occurs in the
        evidence, and at least 70% of its content words do. This accepts answers that restate a table row
        in prose ("40 laptops were ordered under PO-2026-3317" from "Item: Laptops; Quantity: 40"), which
        sentence-to-sentence similarity misses, while an invented value ("48 months") still fails.
        """
        norm = lambda t: t.replace(",", "").lower()
        ev = norm(evidence)
        ids = [i.lower() for i in ID_RE.findall(sentence)]
        numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", ID_RE.sub(" ", sentence))
        if not ids and not numbers:
            return False  # nothing checkable: leave the decision to the similarity tests
        if any(i not in ev for i in ids) or any(norm(n) not in ev for n in numbers):
            return False
        words = [t for t in tokenize(ID_RE.sub(" ", sentence), with_parts=False) if not re.search(r"\d", t)]
        return not words or sum(w in evidence_tokens for w in words) / len(words) >= 0.7

    @staticmethod
    def _lexical_support(sentence: str, context_sents: List[str]) -> float:
        toks = set(tokenize(sentence))
        if not toks:
            return 1.0
        return max(len(toks & set(tokenize(c))) / len(toks) for c in context_sents)

    @staticmethod
    def _build_citations(contexts: List[Dict[str, Any]], numbers: List[int]) -> List[Dict[str, Any]]:
        out = []
        for n in numbers:
            c = contexts[n - 1]
            snippet = c["content"].strip()
            out.append({
                "citation_number": n,
                "doc_id": c["doc_id"],
                "filename": c["filename"],
                "page_number": c.get("page_number", 1),
                "section": c.get("section", "General"),
                "chunk_id": c["chunk_id"],
                "source_snippet": snippet if len(snippet) <= 420 else snippet[:420].rsplit(" ", 1)[0] + "…",
                "relevance_score": round(float(c.get("rerank_score", c.get("retrieval_score", 0.0))), 3),
                # which search method(s) surfaced this passage: "meaning" (semantic) and/or "words" (keyword)
                "found_by": [name for name, key in (("meaning", "dense_rank"), ("words", "bm25_rank")) if key in c],
            })
        return out

    @staticmethod
    def _chunk_text(text: str) -> List[str]:
        return re.findall(r"\S+\s*", text)

    def suggested_questions(self, user_id: str, domain: Optional[str] = None, limit: int = 6) -> List[str]:
        """Build starter questions from section headings of the user's documents, one per document so the
        suggestions cover different documents instead of the first document's sections"""
        seen = set()
        per_doc: Dict[str, List[str]] = {}
        for m in self.store.iter_chunks(user_id):
            if domain and domain != "all" and m["domain"] != domain:
                continue
            sec = (m.get("section") or "").strip()
            if not sec or sec == "General" or len(sec) > 60 or sec.lower() in seen or "record" in sec.lower():
                continue
            # file names and table rows ("Training (per batch) 39,000") make poor topics
            if re.search(r"\.(csv|xlsx|pdf|docx)", sec.lower()) or re.search(r"\d{3,}|\d,\d", sec):
                continue
            # table column headers and version stamps ("Item Amount", "Version 4.0")
            if re.match(r"^\s*(version|v)\s*\d", sec, re.I) or set(re.findall(r"[a-z]+", sec.lower())) <= {
                    "item", "items", "amount", "description", "qty", "quantity", "rate", "total", "sr", "no", "s",
                    "date", "unit", "price", "value", "particulars"}:
                continue
            seen.add(sec.lower())
            clean = re.sub(r"^[\d.\s]+|^(section|clause|article)\s+\d+[:.\s-]*", "", sec, flags=re.I).strip()
            title = m["filename"].rsplit(".", 1)[0].replace("_", " ")
            sec_terms = set(tokenize(clean, with_parts=False))
            # a heading that just repeats the document's title ("Project Proposal: SmartClaims") is no topic
            if sec_terms and len(sec_terms & set(tokenize(title, with_parts=False))) / len(sec_terms) >= 0.5:
                continue
            if len(clean.split()) >= 2:
                per_doc.setdefault(m["doc_id"], []).append(f"What does {title} say about {clean.lower()}?")
        if not per_doc:
            return []
        # stable for a given set of documents (no reshuffling on every page load)
        rng = np.random.default_rng(sum(map(len, per_doc)) + len(per_doc))
        doc_ids = sorted(per_doc)
        order = [doc_ids[i] for i in rng.permutation(len(doc_ids))]
        out: List[str] = []
        depth = 0
        while len(out) < limit and any(depth < len(per_doc[d]) for d in order):
            for d in order:
                if depth < len(per_doc[d]) and len(out) < limit:
                    out.append(per_doc[d][depth])
            depth += 1
        return out
