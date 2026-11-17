"""
Document Intelligence
1. Summarisation  - LLM abstractive summary when available, otherwise extractive
                    centroid summarisation (sentences closest to the document's
                    mean embedding, with a position prior)
2. Named entities - spaCy statistical NER (PERSON/ORG/GPE/DATE/MONEY) + regex for
                    emails, phones, employee/contract/invoice IDs and departments
3. Key-field extraction for contracts, invoices and resumes. Fields that cannot be
   found are returned as null - values are never invented. LLM-extracted values
   are accepted only if they literally occur in the document (verification).
4. Version / document comparison - sentence-level diff with numeric deltas
"""
import difflib
import json
import logging
import re
from collections import Counter
from typing import Any, Dict, List, Optional

import numpy as np

from .llm import LLMClient
from .models import get_embedder
from .rag_pipeline import split_sentences

logger = logging.getLogger(__name__)

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
MONTHS_SHORT = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
DATE_PATTERNS = [
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS}|{MONTHS_SHORT})\.?,?\s+\d{{4}}\b",
    rf"\b(?:{MONTHS}|{MONTHS_SHORT})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b",
    rf"\b(?:{MONTHS})\s+\d{{4}}\b",
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{4}\b",
]
MONEY_RE = r"(?:₹|Rs\.?|INR|\$|USD|€|£)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:lakh|crore|million|billion|k))?"
NUMBER_WITH_UNIT_RE = (r"\b\d[\d,]*(?:\.\d+)?\s?(?:%|percent|days?|weeks?|months?|years?|hours?|hrs|"
                       r"working days|business days|employees|users|units|beds|mg|kg|km|GB|TB)\b")
ID_RE = r"\b[A-Z]{2,5}(?:-[A-Z]{2,4})?-\d{2,4}(?:-\d{2,6})?\b"
DEPARTMENTS = ["Human Resources", "Engineering", "Sales", "Marketing", "Finance", "Legal", "Operations",
               "Customer Support", "Customer Success", "Research and Development", "R&D", "IT", "Procurement",
               "Administration", "Product", "Quality Assurance", "Cardiology", "Pharmacy", "Radiology", "Nursing"]

GENERIC_WORDS = {
    "summary", "patient", "detail", "details", "field", "complaints", "complaint", "medications", "medication",
    "policy", "agreement", "leave", "report", "invoice", "section", "clause", "annexure", "schedule", "lifelong",
    "discharge", "presenting", "course", "total", "date", "table", "page", "item", "items", "description",
    "amount", "serum", "unit", "procedure", "diagnosis", "history", "plan", "advice", "follow", "notes", "status",
    "version", "effective", "purpose", "scope", "definitions", "annual", "monthly", "terms", "fee", "fees",
}

# words that mark a span as a place, a legal/document term or a heading rather than a person or company
PLACE_WORDS = {"road", "street", "st", "lane", "marg", "nagar", "avenue", "tower", "park", "building", "floor", "block",
               "sector", "phase", "layout", "circle", "highway", "plaza", "complex", "campus", "estate", "colony",
               "enclave", "heights", "residency", "gardens", "apartments", "towers"}
DOC_TERMS = {"agreement", "act", "services", "service", "provider", "client", "clients", "responsibilities", "levels",
             "level", "information", "localisation", "localization", "security", "data", "property", "intellectual",
             "recitals", "definitions", "confidential", "confidentiality", "obligations", "warranties", "indemnity",
             "liability", "termination", "schedule", "annexure", "appendix", "statement", "work", "restated", "amended",
             "master", "parties", "party", "processing", "protection", "breach", "notice", "payment", "invoice",
             "policy", "procedure", "committee", "guidelines", "standard", "operating", "training", "module",
             "employees", "employee", "grievances", "grievance", "questions", "interpretation", "home", "opd",
             "ward", "department", "unit", "clinic", "team", "office", "operations", "dear", "choice"}
ORG_SUFFIX_RE = re.compile(r"\b(pvt|private|ltd|limited|llp|llc|inc|corp|corporation|bank|hospital|university|"
                           r"institute|technologies|systems|analytics|labs|foundation|trust|group|holdings)\b\.?",
                           re.IGNORECASE)
PLACES = {p.lower() for p in """India Bengaluru Bangalore Mumbai Pune Chennai Hyderabad Delhi New-Delhi Kolkata Ahmedabad
Kochi Jaipur Indore Lucknow Nagpur Coimbatore Surat Gurugram Gurgaon Noida Bhiwandi Whitefield Bellandur Koramangala
Karnataka Maharashtra Tamil-Nadu Telangana Kerala Gujarat Rajasthan West-Bengal Uttar-Pradesh Haryana Singapore Dubai
London USA UK""".replace("-", " ").split()} | {"new delhi", "tamil nadu", "west bengal", "uttar pradesh"}

_nlp = None
_nlp_loaded = False


def get_spacy():
    global _nlp, _nlp_loaded
    if not _nlp_loaded:
        _nlp_loaded = True
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"])
            _nlp.max_length = 2_000_000
        except Exception as e:  # pragma: no cover
            logger.warning("spaCy NER unavailable (%s); using regex entities only", e)
    return _nlp


def _unique(items, limit: int = 50) -> List[str]:
    seen, out = set(), []
    for i in items:
        i = re.sub(r"\s+", " ", str(i)).strip(" ,.;:")
        if i and i.lower() not in seen:
            seen.add(i.lower())
            out.append(i)
    return out[:limit]


class DocumentIntelligence:
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()
        self.embedder = get_embedder()

    # ================================================================ summarisation
    # how much each summary length contains
    SUMMARY_SPEC = {
        "short": {"points": 3, "overview_sentences": 1, "sections": 0, "conclusion": False, "topics": 5,
                  "dates": 4, "numbers": 6},
        "detailed": {"points": 8, "overview_sentences": 3, "sections": 10, "conclusion": True, "topics": 10,
                     "dates": 10, "numbers": 12},
    }

    def generate_summary(self, chunks: List[Dict[str, Any]], summary_type: str = "detailed") -> Dict[str, Any]:
        """
        short    - a quick glance: one-sentence overview and three key points
        detailed - a fuller overview paragraph, eight key points, a section-by-section summary and a conclusion
        """
        summary_type = "short" if summary_type == "short" else "detailed"
        spec = self.SUMMARY_SPEC[summary_type]
        text = "\n\n".join(c["content"] for c in chunks)
        topics = _unique([c.get("section", "") for c in chunks
                          if c.get("section") and c["section"] != "General" and len(c["section"]) < 70
                          and "record" not in c["section"].lower()], limit=spec["topics"])
        dates = self.extract_dates(text)[:spec["dates"]]
        numbers = _unique(re.findall(MONEY_RE, text) + re.findall(NUMBER_WITH_UNIT_RE, text), limit=spec["numbers"])

        # chunks overlap, so a chunk may begin mid-sentence ("Pvt. Ltd., having its registered office ...");
        # such fragments are not used in summaries
        sentences = [s for s in split_sentences(text)
                     if 40 <= len(s) <= 400 and not s.startswith("Record ") and not self._is_fragment(s)]
        if not sentences:
            sentences = [s for s in split_sentences(text) if len(s) > 10][:spec["points"] + 2]

        if self.llm.available:
            try:
                return self._llm_summary(text, topics, dates, numbers, summary_type, spec)
            except Exception as e:
                logger.warning("LLM summary failed (%s); falling back to extractive", e)

        ranked = self._rank_sentences(sentences)
        # the overview is made of real prose sentences from the opening part of the document - not
        # definitions ('"Services" means ...') or table rows ('Field: value; Field: value')
        opening = max(3, int(len(sentences) * 0.4))
        prose = [i for i in ranked if self._is_prose(sentences[i]) and i <= opening]
        overview_ids = sorted(prose[:spec["overview_sentences"]]) or ([ranked[0]] if ranked else [])
        top = sorted(i for i in ranked[:spec["points"] + len(overview_ids) + 2] if i not in overview_ids)
        key_points = [sentences[i] for i in top][:spec["points"]]
        conclusion = ""
        if spec["conclusion"]:
            pool = [i for i in ranked[: max(4, len(ranked) // 3)]
                    if i >= len(sentences) * 0.6 and i not in overview_ids and sentences[i] not in key_points]
            conclusion = sentences[pool[0]] if pool else (sentences[-1] if sentences else "")
        return {
            "summary_type": summary_type,
            "overview": " ".join(sentences[i] for i in overview_ids) if sentences else "No textual content available.",
            "key_points": key_points,
            "sections": self._section_summaries(chunks, spec["sections"]),
            "main_topics": topics,
            "important_dates": dates,
            "important_numbers": numbers,
            "conclusion": conclusion,
            "method": f"extractive (centroid {self.embedder.kind} embeddings)",
        }

    def _section_summaries(self, chunks: List[Dict[str, Any]], limit: int) -> List[Dict[str, str]]:
        """One or two representative sentences for each section, in document order"""
        if limit <= 0:
            return []
        order: List[str] = []
        by_section: Dict[str, List[str]] = {}
        for c in chunks:
            sec = (c.get("section") or "").strip()
            if not sec or sec == "General" or len(sec) >= 70 or "record" in sec.lower():
                continue
            if sec not in by_section:
                order.append(sec)
                by_section[sec] = []
            by_section[sec].append(c["content"])
        out: List[Dict[str, str]] = []
        for sec in order:
            sents = [x for x in split_sentences("\n".join(by_section[sec]))
                     if len(x) >= 25 and x.strip().lower() != sec.lower() and not self._is_fragment(x)]
            if not sents:
                continue
            pick = ([x for x in sents if self._is_prose(x)] or sents)[:2]
            out.append({"title": re.sub(r"^#+\s*", "", sec), "summary": " ".join(pick)[:420]})
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _is_fragment(s: str) -> bool:
        """A sentence cut off at its start: begins in lower case or with a dangling abbreviation"""
        first = s.lstrip(" \"'([")[:1]
        return (not first) or first.islower() or bool(re.match(r"(Pvt|Ltd|Inc|Co|Corp|LLP)\.?[\s,]", s))

    @staticmethod
    def _is_prose(s: str) -> bool:
        return (len(s.split()) >= 10 and s.rstrip().endswith((".", "!", "?")) and s[:1] not in "\"'“‘(#|"
                and not re.search(r"\bmeans\b|\bshall mean\b", s) and s.count(":") <= 1 and ";" not in s)

    def _rank_sentences(self, sentences: List[str]) -> List[int]:
        """Rank sentences by cosine similarity to the document centroid, with a mild lead bias"""
        if not sentences:
            return []
        vecs = self.embedder.encode(sentences)
        centroid = vecs.mean(axis=0)
        centroid /= (np.linalg.norm(centroid) or 1.0)
        sims = vecs @ centroid
        position_prior = np.array([0.08 * (1 - i / len(sentences)) for i in range(len(sentences))])
        scores = sims + position_prior
        # Maximal Marginal Relevance to avoid near-duplicate key points
        selected: List[int] = []
        candidates = list(np.argsort(-scores))
        while candidates and len(selected) < len(sentences):
            if not selected:
                selected.append(int(candidates.pop(0)))
                continue
            best, best_val = None, -1e9
            for c in candidates[:30]:
                redundancy = max(float(vecs[c] @ vecs[s]) for s in selected)
                val = 0.7 * scores[c] - 0.3 * redundancy
                if val > best_val:
                    best, best_val = c, val
            candidates.remove(best)
            selected.append(int(best))
            if len(selected) >= 12:
                break
        return selected

    def _llm_summary(self, text, topics, dates, numbers, summary_type, spec) -> Dict[str, Any]:
        if summary_type == "short":
            shape = ('"overview": 1-2 sentences, "key_points": a list of 3 bullet strings of at most 20 words each. '
                     'Keep it brief - this is a quick glance.')
            doc, max_tokens = text[:12000], 500
        else:
            shape = (f'"overview": a paragraph of 4-5 sentences, "key_points": a list of {spec["points"]} bullet '
                     'strings that include the specific figures, dates and names, "sections": a list of objects '
                     '{"title": ..., "summary": ...} - one per major section of the document in order (at most '
                     f'{spec["sections"]}), each summary 1-2 sentences, and "conclusion": 2 sentences.')
            doc, max_tokens = text[:16000], 1800
        prompt = (f"Summarise the document below. Return ONLY valid JSON with these keys: {shape} "
                  f"Use only facts stated in the document.\n\nDOCUMENT:\n{doc}")
        raw = self.llm.generate(prompt, max_tokens=max_tokens)
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        sections = [{"title": str(x.get("title", "")).strip(), "summary": str(x.get("summary", "")).strip()}
                    for x in data.get("sections", []) if isinstance(x, dict) and x.get("summary")]
        return {
            "summary_type": summary_type,
            "overview": str(data.get("overview", "")).strip(),
            "key_points": [str(p) for p in data.get("key_points", [])][:spec["points"]],
            "sections": sections[:spec["sections"]],
            "main_topics": topics,
            "important_dates": dates,
            "important_numbers": numbers,
            "conclusion": str(data.get("conclusion", "")).strip() if spec["conclusion"] else "",
            "method": f"abstractive (llm:{self.llm.label})",
        }

    # ================================================================ entities
    def extract_entities(self, text: str) -> Dict[str, Any]:
        ents: Dict[str, List[str]] = {k: [] for k in (
            "Person", "Organization", "Location", "Date", "Money", "Email", "Phone",
            "Employee ID", "Contract ID", "Department")}
        nlp = get_spacy()
        if nlp is not None:
            doc = nlp(text[:200_000])
            for e in doc.ents:
                val = e.text.strip()
                if e.label_ == "PERSON" and 2 <= len(val.split()) <= 4 and not re.search(r"\d|@|:", val):
                    ents["Person"].append(val)
                elif e.label_ == "ORG" and len(val) > 2 and not re.search(r"^\d|^[A-Z]{2,5}-\d", val):
                    ents["Organization"].append(val)
                elif e.label_ in ("GPE", "LOC", "FAC"):
                    ents["Location"].append(val)
        else:
            ents["Person"] = re.findall(r"\b(?:Mr|Ms|Mrs|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", text)
            ents["Organization"] = re.findall(
                r"\b[A-Z][\w&]+(?:\s+[A-Z][\w&]+)*\s+(?:Pvt\.? Ltd\.?|Ltd\.?|Inc\.?|LLP|LLC|Corp\.?|Hospital|Bank|University)",
                text)
        ents["Date"] = self.extract_dates(text)
        ents["Money"] = re.findall(MONEY_RE, text)
        ents["Email"] = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+\w", text)
        ents["Phone"] = re.findall(r"(?:\+91[\s-]?)?\b[6-9]\d{4}[\s-]?\d{5}\b|\b0\d{2,4}[\s-]\d{6,8}\b", text)
        ids = re.findall(ID_RE, text)
        ents["Employee ID"] = [i for i in ids if i.startswith(("EMP", "E-"))]
        ents["Contract ID"] = [i for i in ids if not i.startswith(("EMP", "E-"))]
        ents["Department"] = [d for d in DEPARTMENTS if re.search(rf"\b{re.escape(d)}\b", text)]
        cleaned = {k: _unique(v) for k, v in ents.items()}
        self._clean_named_entities(cleaned, text)
        return {"entities": cleaned,
                "method": "spaCy en_core_web_sm NER + regex patterns" if nlp is not None else "regex patterns"}

    @staticmethod
    def _clean_named_entities(ents: Dict[str, List[str]], text: str) -> None:
        """Remove typical statistical-NER false positives: headings, abbreviations, generic nouns"""
        standalone_lines = {re.sub(r"\s+", " ", l).strip().lower() for l in text.splitlines() if l.strip()}

        def strip_article(v: str) -> str:
            return re.sub(r"^(the|a|an)\s+", "", v, flags=re.IGNORECASE).strip(" •()")

        def lower_words(v: str) -> List[str]:
            return [w.lower().strip(".,'’\"") for w in v.split()]

        def keep(v: str, kind: str) -> bool:
            if not v or v.lower() in standalone_lines or "•" in v or v.count("(") != v.count(")"):
                return False
            if v[:1] in "\"'“‘" or re.search(r"\d", v) and kind != "Location":
                return False
            words, lw = v.split(), lower_words(v)
            if kind == "Person":
                return (2 <= len(words) <= 4 and all(w[:1].isupper() and w.replace(".", "").isalpha() for w in words)
                        and not any(w in GENERIC_WORDS or w in PLACE_WORDS or w in DOC_TERMS for w in lw)
                        and v.lower() not in PLACES)
            if re.fullmatch(r"[A-Z]{1,5}", v):  # bare abbreviations: RCA, ECG, MD, ST
                return False
            if kind == "Location":
                return (v[:1].isupper() and not any(w in GENERIC_WORDS or w in DOC_TERMS for w in lw)
                        and (v.lower() in PLACES or any(w in PLACE_WORDS for w in lw)))
            # organisations: a company suffix is strong evidence; otherwise reject document/legal phrases
            if v.lower() in PLACES:
                return False
            if ORG_SUFFIX_RE.search(v):
                return len(v) > 3
            return len(v) > 3 and not any(w in GENERIC_WORDS or w in DOC_TERMS or w in PLACE_WORDS for w in lw)

        # statistical NER often swaps labels: a known place is always a Location
        for kind in ("Person", "Organization"):
            ents["Location"] += [v for v in ents[kind] if strip_article(v).lower() in PLACES]
        departments = {d.lower() for d in DEPARTMENTS}
        for kind in ("Person", "Organization", "Location"):
            ents[kind] = _unique([strip_article(v) for v in ents[kind]
                                  if keep(strip_article(v), kind) and strip_article(v).lower() not in departments])
        # "Orchid Retail Ventures Pvt" is a truncated duplicate of "Orchid Retail Ventures Pvt. Ltd"
        orgs = ents["Organization"]
        ents["Organization"] = [o for o in orgs
                                if not any(o != p and p.lower().startswith(o.lower().rstrip(".")) for p in orgs)]

    @staticmethod
    def extract_dates(text: str) -> List[str]:
        found = []
        for pat in DATE_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                found.append((m.start(), m.group(0)))
        found.sort()
        # drop "March 2026" when "12 March 2026" was also found at an overlapping position
        out: List[str] = []
        for _, d in found:
            if not any(d != o and d in o for o in out):
                out.append(d)
        return _unique(out, limit=25)

    # ================================================================ key-field extraction
    TEMPLATES = {
        "contract": ["parties", "effective_date", "end_date", "term", "contract_value", "payment_terms",
                     "notice_period", "termination_terms", "governing_law", "contract_id"],
        "invoice": ["invoice_number", "vendor", "customer", "invoice_date", "due_date", "subtotal", "tax_amount",
                    "total_amount", "payment_terms", "po_number"],
        "resume": ["candidate_name", "email", "phone", "location", "education", "skills", "experience_years",
                   "current_role", "certifications"],
    }

    def detect_type(self, text: str) -> str:
        t = text.lower()
        scores = {
            "invoice": sum(t.count(w) for w in ("invoice", "gst", "amount due", "bill to", "subtotal")),
            "contract": sum(t.count(w) for w in ("agreement", "party", "parties", "termination", "governing law",
                                                 "hereinafter", "clause")),
            "resume": sum(t.count(w) for w in ("experience", "education", "skills", "projects", "resume",
                                               "curriculum vitae", "b.tech")),
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "contract"

    def extract_structured_info(self, text: str, doc_type: str = "auto") -> Dict[str, Any]:
        doc_type = (doc_type or "auto").lower()
        text = re.sub(r"(?m)^#{1,6}\s+", "", text)  # drop chunk heading markers
        if doc_type not in self.TEMPLATES:
            doc_type = self.detect_type(text)
        fields = {"contract": self._contract, "invoice": self._invoice, "resume": self._resume}[doc_type](text)
        method = "rule-based patterns"
        if self.llm.available:
            try:
                fields = self._llm_fill(text, doc_type, fields)
                method = f"rule-based + llm:{self.llm.label} (values verified against source text)"
            except Exception as e:
                logger.warning("LLM extraction failed: %s", e)
        return {"document_type": doc_type, "fields": fields, "method": method}

    def _llm_fill(self, text: str, doc_type: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        missing = [k for k, v in fields.items() if not v]
        if not missing:
            return fields
        prompt = (f"Extract these fields from the {doc_type} below: {', '.join(missing)}. Return ONLY JSON mapping "
                  f"each field to the exact text copied from the document, or null if absent.\n\n{text[:10000]}")
        raw = self.llm.generate(prompt, max_tokens=500)
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        norm = re.sub(r"\s+", " ", text).lower()
        for k in missing:
            v = data.get(k)
            values = v if isinstance(v, list) else [v]
            verified = [str(x).strip() for x in values if x and re.sub(r"\s+", " ", str(x)).lower() in norm]
            if verified:
                fields[k] = verified if isinstance(v, list) else verified[0]
        return fields

    @staticmethod
    def _find(patterns: List[str], text: str, flags=re.IGNORECASE) -> Optional[str]:
        for p in patterns:
            m = re.search(p, text, flags)
            if m:
                val = (m.group(1) if m.groups() else m.group(0)).strip(" .,:;\n")
                if val:
                    return re.sub(r"\s+", " ", val)
        return None

    def _contract(self, text: str) -> Dict[str, Any]:
        f = self._find
        parties = None
        between = re.search(r"\bbetween\b([\s\S]{0,900})", text, re.IGNORECASE)
        if between:
            names = re.findall(r"([A-Z][\w&.'\-]*(?:\s+[A-Z&][\w&.'\-]*){0,6}\s+(?:Pvt\.?\s+Ltd\.?|Private Limited|"
                               r"Limited|Ltd\.?|LLP|Inc\.?|LLC|Hospital|Trust))", between.group(1))
            names = _unique([n for n in names if not re.match(r"(?i)^(between|and|the)\b", n)], 2)
            if len(names) == 2:
                parties = names
        m = None if parties else re.search(r"between\s+(.{3,120}?)\s*(?:\(|,|hereinafter)[\s\S]{0,200}?\band\s+(.{3,120}?)\s*(?:\(|,|hereinafter|\.)",
                      text, re.IGNORECASE)
        if m:
            parties = [re.sub(r"\s+", " ", m.group(1)).strip(" ,"), re.sub(r"\s+", " ", m.group(2)).strip(" ,")]
        dates = self.extract_dates(text)
        return {
            "parties": parties,
            "effective_date": f([rf"(?:effective date|commencement date|effective from|dated)\s*(?:of|is|:)?\s*((?:\d{{1,2}}\s+)?(?:{MONTHS})\s+\d{{1,2}},?\s*\d{{4}}|\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})"], text)
                              or (dates[0] if dates else None),
            "end_date": f([rf"(?:expir\w*|end date|terminat\w* on|valid until|until)\s*(?:on|date|:)?\s*((?:\d{{1,2}}\s+)?(?:{MONTHS})\s+\d{{1,2}},?\s*\d{{4}}|\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})"], text),
            "term": f([r"(?:for a term of|initial term of|term of|initial term|period of)\s+((?:\w+\s*)?\(?\d+\)?\s*(?:months?|years?)|"
                       r"(?:one|two|three|four|five|six|twelve|eighteen|twenty-four|thirty-six)\s+(?:months?|years?))"], text),
            "contract_value": f([rf"(?:contract value|total value|total fees?|consideration|annual fee|fees? of)\s*(?:of|is|shall be|:)?\s*({MONEY_RE})"], text),
            "payment_terms": f([r"(?:payment terms?|payable)\s*[:\-]?\s*([^\n.]{5,160})", r"(net\s*\d{1,3}\s*days[^\n.]{0,80})"], text),
            "notice_period": f([r"(\d{1,3}\s*\(?\w*\)?\s*days['’]?\s*(?:prior\s+)?(?:written\s+)?notice)", r"notice period of\s+([^\n.,]{3,40})"], text),
            "termination_terms": f([r"((?:either party )?may terminate[^\n.]{10,220})", r"(terminat\w+ [^\n.]{10,220})"], text),
            "governing_law": f([r"governed by(?: and construed in accordance with)? the laws of\s+([^\n.,]{3,60})", r"governing law[:\s]+([^\n.]{3,80})"], text),
            "contract_id": f([r"\b((?:CNT|MSA|NDA|SLA|DPA|AGR|LIC|CTR)-[A-Z0-9-]{3,20})\b"], text, 0),
        }

    def _invoice(self, text: str) -> Dict[str, Any]:
        """Line-anchored patterns; labels may be followed by ':' / '-' or just whitespace (PDF tables)"""
        f = self._find
        amt = r"((?:₹|Rs\.?|INR)?\s?\d[\d,]*(?:\.\d+)?)"
        line = lambda labels: rf"(?im)^\s*(?:{labels})\b\s*[:\-]?\s*([^\n]{{2,120}})$"
        next_line = lambda labels: rf"(?im)^\s*(?:{labels})\s*[:\-]?\s*\n\s*([^\n]{{3,}})$"
        first_part = lambda v: v.split(",")[0].strip() if v else v
        first_sentence = lambda v: re.split(r"(?<=\.)\s", v)[0].strip() if v else v
        taxes = [re.sub(r"\s+", " ", m.group(0)).strip() for m in re.finditer(
            r"(?im)^\s*(?:[csi]gst|gst|vat|total tax|tax amount)\b[^\n]*?"
            r"(?:(?:₹|Rs\.?|INR)\s?\d[\d,]*|\d{1,3}(?:,\d{2,3})+)(?:\.\d+)?\s*$", text)]
        return {
            "invoice_number": f([r"(?im)^\s*invoice\s*(?:no\.?|number|#|id)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{3,25})",
                                 r"\b(INV-\d[\dA-Z-]{3,20})\b"], text, 0),
            "vendor": first_part(f([next_line("supplier|vendor|seller|from|billed by"),
                                    line("supplier|vendor|seller|billed by")], text)),
            "customer": first_part(f([line("bill(?:ed)? to|customer|buyer|client"),
                                      next_line("bill(?:ed)? to|customer|buyer")], text)),
            "invoice_date": f([line("invoice date|date of issue|issued on|issue date")], text),
            "due_date": f([line("due date|payment due|due by|due on")], text),
            "subtotal": f([rf"(?im)^\s*sub[\s-]?total\b[^\n\d₹]*{amt}"], text),
            "tax_amount": (taxes[0] if len(taxes) == 1 else taxes) or None,
            "total_amount": f([rf"(?im)^\s*(?:grand total|total amount(?: payable| due)?|amount due|total payable|"
                               rf"invoice total|total)\b[^\n\d₹]*{amt}\s*$"], text),
            "payment_terms": first_sentence(f([line("payment terms?"), next_line("payment terms?"),
                                                r"(?i)\b(net\s*\d{1,3}\s*days)\b"], text)),
            "po_number": f([r"(?i)(?:p\.?o\.?|purchase order)\s*(?:no\.?|number|#|ref\w*)?\s*[:\-]?\s*"
                            r"([A-Z]{0,4}-?\d[A-Z0-9\-/]{2,25})"], text),
        }

    def _resume(self, text: str) -> Dict[str, Any]:
        f = self._find
        name = None
        for raw in [l for l in text.splitlines() if l.strip()][:8]:
            cand = re.split(r"\s[-–|]\s|\|", raw)[0].strip(" #*-")
            words = cand.split()
            if (2 <= len(words) <= 4 and all(w[:1].isupper() and w.replace(".", "").isalpha() for w in words)
                    and not re.search(r"resume|curriculum|profile|summary|engineer|developer|scientist|manager",
                                      cand, re.I)):
                name = cand
                break
        skills = None
        table = re.search(r"(?is)skills\b[^\n]*\n((?:\s*\|[^\n]*\|\s*\n?)+)", text)
        if table:  # skills laid out as a table: | Area | Tools |
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in table.group(1).strip().splitlines()]
            rows = [r for r in rows[1:] if not all(set(c) <= set("-: ") for c in r)]
            skills = [t.strip() for r in rows for t in re.split(r"[,;/]", r[-1]) if t.strip()]
        else:
            skills_block = f([r"(?:technical\s+)?skills\s*[:\n]\s*([^\n]{5,400})"], text)
            if skills_block:
                skills = [re.sub(r"^[\w ]+:\s*", "", s).strip() for s in re.split(r"[,|;•]", skills_block)]
        education = re.findall(r"((?:B\.?\s?Tech|M\.?\s?Tech|B\.?E\.?|B\.?Sc|M\.?Sc|BCA|MCA|MBA|Ph\.?D|Bachelor|Master)[^\n]{3,140})", text)
        certs = re.findall(r"((?:AWS|Azure|Google|Oracle|Cisco|PMP|Certified)[^\n,;]{3,80}(?:Certif\w+|Associate|Professional|Practitioner))", text)
        return {
            "candidate_name": name,
            "email": f([r"([\w.+-]+@[\w-]+\.[\w.-]+\w)"], text),
            "phone": f([r"((?:\+91[\s-]?)?\b[6-9]\d{4}[\s-]?\d{5}\b)"], text),
            "location": f([r"(?:location|address|based in)\s*[:\-]\s*([^\n|]{3,60})"], text),
            "education": _unique(education, 5) or None,
            "skills": [s for s in (skills or []) if s][:20] or None,
            "experience_years": f([r"(\d+\+?\s*years?)\s+of\s+(?:professional\s+|industry\s+)?experience"], text),
            "current_role": f([r"(?:current role|designation|title)\s*[:\-]\s*([^\n]{3,80})"], text),
            "certifications": _unique(certs, 6) or None,
        }

    # ================================================================ comparison
    def compare_documents(self, text_a: str, text_b: str, label_a: str = "Document A",
                          label_b: str = "Document B") -> Dict[str, Any]:
        sa = [s for s in split_sentences(text_a) if len(s) > 3]
        sb = [s for s in split_sentences(text_b) if len(s) > 3]
        norm = lambda s: re.sub(r"\s+", " ", s.lower()).strip()
        matcher = difflib.SequenceMatcher(None, [norm(s) for s in sa], [norm(s) for s in sb], autojunk=False)
        added, removed, modified = [], [], []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "insert":
                added.extend(sb[j1:j2])
            elif tag == "delete":
                removed.extend(sa[i1:i2])
            elif tag == "replace":
                olds, news = list(sa[i1:i2]), list(sb[j1:j2])
                # pair each old sentence with its most similar new sentence
                for old in olds:
                    best_j, best_r = None, 0.0
                    for j, new in enumerate(news):
                        r = difflib.SequenceMatcher(None, norm(old), norm(new)).ratio()
                        if r > best_r:
                            best_j, best_r = j, r
                    if best_j is not None and best_r >= 0.55:
                        new = news.pop(best_j)
                        modified.append({"from_text": old, "to_text": new,
                                         "deltas": self._numeric_deltas(old, new)})
                    else:
                        removed.append(old)
                added.extend(news)
        similarity = difflib.SequenceMatcher(None, norm(text_a), norm(text_b), autojunk=False).quick_ratio() \
            if max(len(text_a), len(text_b)) > 50_000 else \
            difflib.SequenceMatcher(None, [norm(s) for s in sa], [norm(s) for s in sb], autojunk=False).ratio()
        modified.sort(key=lambda m: 0 if m["deltas"] else 1)  # substantive numeric changes first
        da, db = set(self.extract_dates(text_a)), set(self.extract_dates(text_b))
        return {
            "label_a": label_a, "label_b": label_b,
            "similarity_score": round(similarity * 100, 1),
            "added_count": len(added), "removed_count": len(removed), "modified_count": len(modified),
            "added_clauses": added, "removed_clauses": removed, "modified_clauses": modified,
            "new_dates": sorted(db - da), "removed_dates": sorted(da - db),
        }

    @staticmethod
    def _numeric_deltas(old: str, new: str) -> List[Dict[str, Any]]:
        num = r"(?<![\w-])\d[\d,]*(?:\.\d+)?(?![\w-])"
        to_float = lambda s: float(s.replace(",", ""))
        a, b = re.findall(num, old), re.findall(num, new)
        sm = difflib.SequenceMatcher(None, a, b)
        out = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace" and (i2 - i1) == (j2 - j1):
                for x, y in zip(a[i1:i2], b[j1:j2]):
                    dx, dy = to_float(x), to_float(y)
                    is_year = lambda v, s: 1900 <= v <= 2100 and float(v).is_integer() and len(s) == 4
                    if is_year(dx, x) and is_year(dy, y):
                        continue  # 2025 -> 2026 is a version/date bump, not a substantive change
                    if dx != dy:
                        diff = dy - dx
                        pct = f" ({diff / dx * 100:+.0f}%)" if dx else ""
                        out.append({"original_value": x, "new_value": y,
                                    "change_delta": f"{diff:+g}{pct}"})
        return out

    # ================================================================ misc
    @staticmethod
    def top_keywords(text: str, n: int = 10) -> List[str]:
        from .hybrid_retriever import tokenize
        words = [w for w in tokenize(text) if len(w) > 3 and not w.isdigit()]
        return [w for w, _ in Counter(words).most_common(n)]
