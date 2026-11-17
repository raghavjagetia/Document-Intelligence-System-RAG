"""Unit tests for the core algorithms"""
import math

import pytest

from backend.auth import hash_password, verify_password
from backend.document_intelligence import DocumentIntelligence
from backend.evaluation import evaluate_config, keyword_match
from backend.hybrid_retriever import BM25Index, HybridRetriever, tokenize
from backend.intelligent_chunking import IntelligentChunker
from backend.llm import LLMClient
from backend.rag_pipeline import PipelineSettings, RAGPipeline, RAGResult, split_sentences
from backend.vector_store import VectorStore


def make_store(docs):
    store = VectorStore()
    for doc_id, chunks in docs.items():
        store.add_chunks([{"chunk_id": f"{doc_id}_{i}", "content": c, "section": "General"}
                          for i, c in enumerate(chunks)],
                         {"doc_id": doc_id, "user_id": "u1", "domain": "general", "filename": doc_id})
    return store


# ---------------------------------------------------------------- tokenizer / BM25 / RRF
def test_tokenizer_keeps_identifiers_and_parts():
    toks = tokenize("Invoice INV-2026-8842 totals ₹5,31,000")
    assert "inv-2026-8842" in toks and "8842" in toks and "invoice" in toks


def test_bm25_prefers_exact_identifier():
    idx = BM25Index()
    idx.build([{"chunk_id": "a", "content": "Invoice INV-2026-8842 total is 5,31,000"},
               {"chunk_id": "b", "content": "Invoice INV-2026-8843 total is 1,20,000"},
               {"chunk_id": "c", "content": "Leave policy for employees"}])
    assert idx.search("INV-2026-8842")[0]["chunk_id"] == "a"


def test_hybrid_rrf_fuses_and_normalises():
    store = make_store({"leave.txt": ["Employees receive 20 days of annual leave each year."],
                        "inv.txt": ["Invoice INV-2026-8842 has a total of 5,31,000."]})
    results = HybridRetriever(store).search("annual leave days", user_id="u1")
    assert results[0]["doc_id"] == "leave.txt"
    assert all(0 <= r["retrieval_score"] <= 1 for r in results)
    assert results[0]["retrieval_method"] == "hybrid_rrf"


def test_vector_store_isolation_and_delete():
    store = make_store({"a.txt": ["alpha beta gamma"]})
    assert store.search("alpha", user_id="someone-else") == []
    assert store.search("alpha", user_id="u1")
    assert store.remove_document("a.txt") == 1
    assert store.search("alpha", user_id="u1") == []


# ---------------------------------------------------------------- chunking
def test_chunks_never_straddle_sections_and_tables_stay_whole():
    elements = [
        {"text": "Leave Policy", "element_type": "heading"},
        {"text": "Annual leave is 20 days. " * 5, "element_type": "paragraph"},
        {"text": "Travel Policy", "element_type": "heading"},
        {"text": "| City | Allowance |\n| --- | --- |\n| Delhi | 4000 |", "element_type": "table"},
    ]
    chunks = IntelligentChunker(chunk_size=200, chunk_overlap=20).chunk_structured_elements(elements, "d")
    for c in chunks:
        assert not ("Leave Policy" in c["content"] and "Travel Policy" in c["content"])
    tables = [c for c in chunks if c["element_type"] == "table"]
    assert len(tables) == 1 and "Delhi" in tables[0]["content"] and tables[0]["section"] == "Travel Policy"


def test_fixed_size_chunker_respects_size():
    elements = [{"text": "word " * 400, "element_type": "paragraph"}]
    chunks = IntelligentChunker(chunk_size=300, chunk_overlap=50).chunk_fixed_size(elements, "d")
    assert len(chunks) > 3 and all(len(c["content"]) <= 300 for c in chunks)


def test_split_sentences_turns_table_rows_into_records():
    units = split_sentences("| Name | Salary |\n| --- | --- |\n| Rahul | 24,00,000 |")
    assert units == ["Name: Rahul; Salary: 24,00,000"]


# ---------------------------------------------------------------- query rewriting
def test_heuristic_rewrite_replaces_topic():
    out = RAGPipeline._heuristic_rewrite("What about sick leave?",
                                         "How many days of annual leave do employees get in 2026?")
    assert "sick leave" in out and "annual" not in out and "2026" in out


def test_non_followup_is_not_rewritten():
    p = RAGPipeline(make_store({"a.txt": ["x y z"]}), llm=LLMClient("none"))
    q = "What is the notice period in the master services agreement?"
    assert p.rewrite_query(q, ["previous question about leave"]) == q


# ---------------------------------------------------------------- other languages
def test_language_detection():
    from backend.rag_pipeline import needs_translation
    assert needs_translation("वार्षिक छुट्टी कितने दिन की है?")          # Devanagari
    assert needs_translation("chhutti kitne din milti hai?")            # Hinglish
    assert needs_translation("¿Cuántos días de vacaciones tengo?")      # accented Latin
    assert not needs_translation("What is the annual leave entitlement?")
    assert not needs_translation("What is the total on INV-2026-8842 in ₹?")
    assert not needs_translation("Who is the vendor on the café invoice?")  # one accented letter is not enough


class FakeLLM(LLMClient):
    """Translates by table lookup and answers in English with a citation"""
    def __init__(self):
        super().__init__("none")
        self.provider, self.model = "groq", "fake"
        self.prompts = []

    def stream(self, prompt, system="", max_tokens=None):
        self.prompts.append((system, prompt))
        if system.startswith("You translate questions"):
            yield "How many days of annual leave do employees get?"
        elif system.startswith("You translate answers"):
            yield "कर्मचारियों को 20 दिन की वार्षिक छुट्टी मिलती है [1]।"
        else:
            yield "Employees get 20 days of annual leave [1]."


def test_non_english_question_is_answered_in_english_then_translated():
    llm = FakeLLM()
    p = RAGPipeline(make_store({"leave.txt": ["Employees get 20 days of annual leave per year.",
                                              "The office canteen opens at 9 am."]}), llm=llm)
    events = list(p.stream("वार्षिक छुट्टी कितने दिन की है?", "u1",
                           settings=PipelineSettings(use_abstention=False)))
    result = events[-1][1]
    assert result.rewritten_query == "How many days of annual leave do employees get?"  # retrieval ran in English
    assert result.answer.startswith("कर्मचारियों")                                    # answer shown in Hindi
    assert result.citations and result.citations[0]["filename"] == "leave.txt"
    streamed = "".join(p for e, p in events if e == "token")
    assert streamed == result.answer


def test_english_question_makes_no_translation_calls():
    llm = FakeLLM()
    p = RAGPipeline(make_store({"leave.txt": ["Employees get 20 days of annual leave per year."]}), llm=llm)
    p.answer("How many days of annual leave do employees get?", "u1", settings=PipelineSettings(use_abstention=False))
    assert not any(system.startswith("You translate") for system, _ in llm.prompts)


def test_answer_styles():
    llm = FakeLLM()
    p = RAGPipeline(make_store({"leave.txt": ["Employees get 20 days of annual leave per year.",
                                              "Unused leave of up to 10 days can be carried forward."]}), llm=llm)
    ask = lambda style: p.answer("How many days of annual leave do employees get?", "u1",
                                 settings=PipelineSettings(use_abstention=False, answer_style=style))
    quote = ask("quote")
    assert quote.answer.startswith("> ") and "leave.txt, page" in quote.answer   # verbatim, with its source
    assert not llm.prompts                                                         # quotes never use the LLM
    assert quote.grounded and quote.grounding_score == 1.0                         # verbatim text is fully supported
    ask("detailed")
    assert "bullet points" in llm.prompts[-1][0]                                   # detailed prompt was used
    ask("quick")
    assert "1-4 sentences" in llm.prompts[-1][0]                                   # default prompt unchanged


def test_exact_quote_covers_several_equally_relevant_documents():
    p = RAGPipeline(make_store({"policy_2025.txt": ["Employees get 18 days of annual leave per year."],
                                "policy_2026.txt": ["Employees get 20 days of annual leave per year."],
                                "canteen.txt": ["The canteen serves lunch from noon."]}), llm=LLMClient("none"))
    r = p.answer("How many days of annual leave do employees get?", "u1",
                 settings=PipelineSettings(use_abstention=False, answer_style="quote"))
    assert "policy_2025.txt" in r.answer and "policy_2026.txt" in r.answer and "canteen" not in r.answer


def test_followup_rewrite_sees_previous_answer():
    llm = FakeLLM()
    p = RAGPipeline(make_store({"po.txt": ["PO-2026-3317 was approved by Meera Iyer."]}), llm=llm)
    p.rewrite_query("Who approved it?", ["How many laptops were ordered?"], previous_answer="40 laptops were ordered "
                    "under purchase order PO-2026-3317 [1].")
    prompt = llm.prompts[-1][1]
    assert "Previous answer: 40 laptops were ordered under purchase order PO-2026-3317" in prompt and "[1]" not in prompt


def test_citations_record_which_search_found_them():
    p = RAGPipeline(make_store({"leave.txt": ["Employees get 20 days of annual leave per year."]}),
                    llm=LLMClient("none"))
    for mode, expected in (("hybrid", {"meaning", "words"}), ("semantic", {"meaning"}), ("bm25", {"words"})):
        result = p.answer("annual leave days", "u1", settings=PipelineSettings.for_mode(mode))
        assert set(result.citations[0]["found_by"]) == expected


def test_suggested_questions_cover_several_documents():
    store = VectorStore()
    for d in ("Policy_A", "Policy_B", "Policy_C"):
        store.add_chunks([{"chunk_id": f"{d}_{i}", "content": f"text {i}", "section": f"{d} topic number {i}"}
                          for i in range(10)],
                         {"doc_id": d, "user_id": "u1", "domain": "general", "filename": f"{d}.pdf"})
    qs = RAGPipeline(store, llm=LLMClient("none")).suggested_questions("u1", limit=6)
    assert len(qs) == 6
    assert all(sum(f"Policy {d}" in q for q in qs) == 2 for d in "ABC")


# ---------------------------------------------------------------- auth
def test_password_hashing():
    h = hash_password("s3cret!")
    assert h.startswith("pbkdf2_sha256$") and verify_password("s3cret!", h)
    assert not verify_password("wrong", h)
    assert hash_password("s3cret!") != h  # random salt


# ---------------------------------------------------------------- document intelligence
def test_extraction_never_invents_values():
    di = DocumentIntelligence(llm=LLMClient("none"))
    out = di.extract_structured_info("Invoice Number: INV-2026-0001\nGrand Total: ₹1,18,000\n", "invoice")
    f = out["fields"]
    assert f["invoice_number"] == "INV-2026-0001"
    assert f["total_amount"] == "₹1,18,000"
    assert f["po_number"] is None and f["vendor"] is None


def test_compare_detects_numeric_delta():
    di = DocumentIntelligence(llm=LLMClient("none"))
    res = di.compare_documents("Employees receive 18 days of annual leave.\nWFH is 2 days a week.",
                               "Employees receive 20 days of annual leave.\nWFH is 2 days a week.")
    assert res["modified_count"] == 1
    delta = res["modified_clauses"][0]["deltas"][0]
    assert delta["original_value"] == "18" and delta["new_value"] == "20" and delta["change_delta"].startswith("+2")


def test_date_extraction():
    dates = DocumentIntelligence.extract_dates("Signed on 12 March 2026 and renewed on 2027-03-12.")
    assert "12 March 2026" in dates and "2027-03-12" in dates and "March 2026" not in dates


# ---------------------------------------------------------------- evaluation metrics
class _FakePipeline:
    """Returns a fixed ranking so metric arithmetic can be checked by hand"""
    def answer(self, question, *args, **kwargs):
        ctx = [{"doc_id": d, "chunk_id": d} for d in ("x", "a", "a", "b")]
        return RAGResult(question, question, "Annual leave is 20 days [2]", ctx,
                         [{"doc_id": "a"}], True, 1.0, 0.9, False, "test", 0.01, "hybrid")


def test_metrics_are_correct_and_ndcg_bounded():
    cases = [{"id": "Q1", "category": "factual", "question": "q", "expected_docs": ["a"], "answer_keywords": ["20"]}]
    m = evaluate_config(_FakePipeline(), cases, PipelineSettings())
    assert m["recall_at_1"] == 0.0 and m["recall_at_3"] == 100.0
    assert m["mrr"] == 0.5
    assert math.isclose(m["ndcg_at_5"], round(100 / math.log2(3), 1))
    assert m["ndcg_at_5"] <= 100 and m["answer_correctness"] == 100.0 and m["citation_accuracy"] == 100.0


def test_keyword_match_ignores_case_and_commas():
    assert keyword_match("Total payable is ₹5,31,000.", ["₹531000"])
    assert not keyword_match("Total payable is ₹5,31,000.", ["6,00,000"])


def test_llm_retries_rate_limit_then_streams(monkeypatch):
    """A 429 before any text is produced is waited out and retried instead of failing straight away"""
    import pytest
    import requests
    from backend import llm as llm_mod

    calls = {"n": 0}

    def fake_groq(self, prompt, system, max_tokens):
        calls["n"] += 1
        if calls["n"] == 1:
            resp = requests.Response()
            resp.status_code, resp.headers["retry-after"] = 429, "0"
            raise requests.HTTPError(response=resp)
        yield "20 days [1]"

    monkeypatch.setattr(llm_mod.Config, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(llm_mod.LLMClient, "_stream_groq", fake_groq)
    client = llm_mod.LLMClient(provider="groq", retries=2)
    assert client.generate("q") == "20 days [1]" and calls["n"] == 2
    calls["n"] = 0
    with pytest.raises(requests.HTTPError):
        llm_mod.LLMClient(provider="groq", retries=0).generate("q")


def test_llm_text_normalisation():
    from backend.llm import _clean
    assert _clean("20 days 【1】") == "20 days [1]"


def test_grounding_accepts_restated_table_facts_but_not_invented_values():
    from backend.rag_pipeline import RAGPipeline
    ev = "## Items\nItem: Laptops; Quantity: 40; Unit price (Rs.): 68,000\nPO number PO-2026-3317, delivery in 15 days."
    from backend.hybrid_retriever import tokenize
    question = "How many laptops were ordered under purchase order PO-2026-3317?"
    # words that merely restate the question are not claims, so they count as known
    toks = set(tokenize(ev, with_parts=True)) | set(tokenize(question, with_parts=True))
    assert RAGPipeline._fact_support("40 laptops were ordered under purchase order PO-2026-3317", ev, toks)
    assert not RAGPipeline._fact_support("48 laptops were ordered under purchase order PO-2026-3317", ev, toks)
    assert not RAGPipeline._fact_support("40 laptops were ordered under purchase order PO-2026-9999", ev, toks)
    assert not RAGPipeline._fact_support("40 tablets and phones were shipped overseas by air freight", ev, toks)


def test_llm_long_rate_limit_pauses_instead_of_waiting(monkeypatch):
    """A long retry-after (e.g. a used-up daily allowance) fails at once and pauses the provider"""
    import time as _time
    import pytest
    import requests
    from backend import llm as llm_mod

    calls = {"n": 0}

    def limited(self, prompt, system, max_tokens):
        calls["n"] += 1
        resp = requests.Response()
        resp.status_code, resp.headers["retry-after"] = 429, "600"
        raise requests.HTTPError(response=resp)
        yield  # pragma: no cover

    monkeypatch.setattr(llm_mod.Config, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(llm_mod.LLMClient, "_stream_groq", limited)
    monkeypatch.setattr(llm_mod.LLMClient, "_paused_until", {})
    client = llm_mod.LLMClient(provider="groq", retries=2, max_wait=5)
    t0 = _time.perf_counter()
    with pytest.raises(requests.HTTPError):
        client.generate("q")
    assert calls["n"] == 1 and _time.perf_counter() - t0 < 1  # no 600 s wait, no retries
    assert client.paused_seconds > 500
    with pytest.raises(llm_mod.LLMPaused):  # later calls skip the provider entirely
        client.generate("q")
    assert calls["n"] == 1


# ---------------------------------------------------------------- advanced evaluation
def test_bootstrap_ci_and_mcnemar():
    from backend.advanced_eval import mcnemar_exact, proportion_ci
    lo, hi = proportion_ci([1.0] * 90 + [0.0] * 10)
    assert lo < 90 < hi and 82 <= lo and hi <= 96          # 90 of 100 correct: about 82.6-94.5%
    lo, hi = proportion_ci([1.0] * 15)
    assert hi == 100.0 and 75 < lo < 85                    # 15 of 15 is NOT proof of 100%: about 79.6-100%
    same = mcnemar_exact({"a": True, "b": False}, {"a": True, "b": False})
    assert same["p_value"] == 1.0
    a = {str(i): True for i in range(30)}
    b = {str(i): i >= 20 for i in range(30)}              # first system wins on 20 questions, loses on none
    r = mcnemar_exact(a, b)
    assert r["only_first_correct"] == 20 and r["only_second_correct"] == 0 and r["p_value"] < 0.01


def test_error_analysis_categories():
    from backend.advanced_eval import error_analysis
    cases = [
        {"id": "1", "category": "f", "question": "q1", "expected_docs": ["a.pdf"], "answer_keywords": ["20"]},
        {"id": "2", "category": "f", "question": "q2", "expected_docs": ["a.pdf"], "answer_keywords": ["20"]},
        {"id": "3", "category": "f", "question": "q3", "expected_docs": ["a.pdf"], "answer_keywords": ["20"]},
        {"id": "4", "category": "u", "question": "q4", "expected_docs": [], "answer_keywords": []},
        {"id": "5", "category": "f", "question": "q5", "expected_docs": ["a.pdf"], "answer_keywords": ["20"]},
    ]
    records = {
        "1": {"answer": "18 days", "abstained": False, "retrieved_docs": ["b.pdf"]},     # wrong document
        "2": {"answer": "18 days", "abstained": False, "retrieved_docs": ["a.pdf"]},     # right doc, wrong sentence
        "3": {"answer": "not found", "abstained": True, "retrieved_docs": ["a.pdf"]},    # wrongly refused
        "4": {"answer": "yes", "abstained": False, "retrieved_docs": ["a.pdf"]},         # should have refused
        "5": {"answer": "20 days", "abstained": False, "retrieved_docs": ["a.pdf"]},     # correct
    }
    correct = {"1": False, "2": False, "3": False, "4": False, "5": True}
    ea = error_analysis(cases, records, correct)
    counts = {c["key"]: c["count"] for c in ea["categories"]}
    assert ea["total_errors"] == 4 and set(counts.values()) == {1}


def test_baseline_refusal_detection():
    from backend.advanced_eval import REFUSAL_RE
    for t in ["I don't know.", "The context does not mention the share price.", "There is no information about pets."]:
        assert REFUSAL_RE.search(t)
    assert not REFUSAL_RE.search("The total amount payable is 4,72,000.")


def test_guarded_llm_caches_and_keeps_reserve(tmp_path, monkeypatch):
    import backend.advanced_eval as ae
    monkeypatch.setattr(ae.Config, "GROQ_API_KEY", "test-key")
    calls = []

    class Resp:
        status_code = 200
        headers = {"x-ratelimit-remaining-requests": "251", "x-ratelimit-remaining-tokens": "7000",
                   "x-ratelimit-reset-tokens": "1s"}
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "<think>hmm</think>Answer 42"}}]}

    monkeypatch.setattr(ae.requests, "post", lambda *a, **k: calls.append(1) or Resp())
    llm = ae.GuardedLLM(tmp_path / "cache.jsonl", reserve=250)
    assert llm.generate("q1") == "Answer 42" and llm.generate("q1") == "Answer 42"
    assert len(calls) == 1 and llm.cache_hits == 1                      # second answer came from the cache
    Resp.headers = dict(Resp.headers, **{"x-ratelimit-remaining-requests": "250"})
    llm.generate("q2")                                                  # now down to the reserve
    with pytest.raises(ae.BudgetPaused):
        llm.generate("q3")
    assert ae.GuardedLLM(tmp_path / "cache.jsonl").generate("q1") == "Answer 42"   # cache survives restarts


def test_hinglish_reply_detection():
    from backend.advanced_eval import reply_language_ok
    assert reply_language_ok("hinglish", "Invoice INV-2026-8842 ka total amount 4,72,000 hai [1].")
    assert not reply_language_ok("hinglish", "The total amount payable is 4,72,000 [1].")
    assert not reply_language_ok("hinglish", "कुल राशि 4,72,000 है [1]।")
    assert reply_language_ok("hindi", "कुल राशि 4,72,000 है [1]।")
