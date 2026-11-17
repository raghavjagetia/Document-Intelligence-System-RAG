"""
Source viewer
Shows a cited passage inside its original document with the supporting sentence highlighted.

- PDF: the page is rendered to an image (pypdfium2) and the sentence is located in the page's text layer;
  the character boxes of the match are merged into one rectangle per line and returned as fractions of the
  page size, so the browser can draw the highlight over the image at any zoom level.
- Every other format (DOCX, HTML, TXT, CSV, XLSX, PPTX, images via OCR): the cited chunk and its neighbours
  are returned as text together with the sentences to highlight.

Which sentence is highlighted: the chunk sentence that shares the most words (and every number) with the
answer sentences that cite this source ("focus"), e.g. "20 days" in "Employees get 20 days of leave [1]".
"""
import base64
import io
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .hybrid_retriever import tokenize
from .text_utils import split_prose

RENDER_WIDTH_PX = 1100
MAX_SEARCH_PAGES = 40

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                         " ": " ", " ": " ", "₹": "rs"})


# ---------------------------------------------------------------- which sentences to highlight
def _units(chunk_text: str) -> List[List[str]]:
    """Highlightable units of a chunk. A unit is a list of pieces found in order: one sentence, or the cells
    of one table row (cells are laid out separately on a PDF page)."""
    units: List[List[str]] = []
    for line in chunk_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("## ") or set(line) <= set("|-: "):
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|") if c.strip()]
            if cells:
                units.append(cells)
            continue
        line = re.sub(r"^([-*•]|\d+[.)])\s+", "", line)
        units.extend([s] for s in split_prose(line) if len(s.strip()) > 3)
    return units


def pick_highlights(chunk_text: str, focus: str, limit: int = 2) -> List[List[str]]:
    """The unit(s) of the chunk that best support the focus text (the answer sentences citing this source)"""
    units = _units(chunk_text)
    if not units:
        return []
    focus = re.sub(r"\[\d+\]", " ", focus or "")
    f_tokens = set(tokenize(focus, with_parts=True))
    f_numbers = {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", focus)}
    if not f_tokens:
        return units[:1]
    scored: List[Tuple[float, int]] = []
    for idx, unit in enumerate(units):
        text = " ".join(unit)
        toks = set(tokenize(text, with_parts=True))
        if not toks:
            continue
        overlap = len(toks & f_tokens)
        numbers = {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}
        score = overlap / math.sqrt(len(toks)) + 1.5 * len(numbers & f_numbers)
        scored.append((score, idx))
    scored.sort(reverse=True)
    if not scored or scored[0][0] <= 0:
        return units[:1]
    best = scored[0][0]
    keep = sorted(idx for score, idx in scored[:limit] if score >= 0.7 * best)
    return [units[i] for i in keep]


# ---------------------------------------------------------------- PDF
def _normalise(text: str) -> Tuple[str, List[int]]:
    """Lower-cased text with every whitespace run collapsed to one space, plus a map from each normalised
    character back to its index in the original text"""
    out, index = [], []
    prev_space = True
    for i, raw in enumerate(text):
        if raw.isspace():
            if not prev_space:
                out.append(" ")
                index.append(i)
            prev_space = True
            continue
        for ch in raw.translate(_QUOTES).lower():  # one character can become several ("₹" -> "rs")
            out.append(ch)
            index.append(i)
        prev_space = False
    return "".join(out), index


def _norm_piece(piece: str) -> str:
    piece = re.sub(r"\*\*|__|`", "", piece)
    return re.sub(r"\s+", " ", piece.translate(_QUOTES).lower()).strip(" .")


def _find(ntext: str, piece: str, start: int) -> Optional[Tuple[int, int]]:
    """Span of `piece` in the normalised page text at or after `start`; falls back to anchoring on the first
    or last words when the full text differs slightly (hyphenation, symbols the PDF renders differently)"""
    p = _norm_piece(piece)
    if len(p) < 2:
        return None
    i = ntext.find(p, start)
    if i < 0 and start:
        i = ntext.find(p)
    if i >= 0:
        return i, i + len(p)
    words = p.split()
    if len(words) >= 6:
        head = " ".join(words[:5])
        i = ntext.find(head, start)
        if i >= 0:
            return i, min(len(ntext), i + len(p))
        tail = " ".join(words[-5:])
        i = ntext.find(tail, start)
        if i >= 0:
            return max(0, i + len(tail) - len(p)), i + len(tail)
    return None


def _line_boxes(textpage, char_indices: List[int], page_w: float, page_h: float) -> List[Dict[str, float]]:
    """Merge character boxes into one rectangle per text line (fractions of the page size, origin top-left)"""
    lines: List[List[float]] = []  # [left, bottom, right, top]
    for ci in char_indices:
        l, b, r, t = textpage.get_charbox(ci)
        if r - l <= 0 or t - b <= 0:
            continue
        if lines:
            L = lines[-1]
            same_line = abs(b - L[1]) < 0.6 * max(t - b, L[3] - L[1]) and l >= L[0] - 1
            if same_line:
                L[0], L[1], L[2], L[3] = min(L[0], l), min(L[1], b), max(L[2], r), max(L[3], t)
                continue
        lines.append([l, b, r, t])
    pad = 1.5
    return [{"x": max(0.0, (l - pad) / page_w), "y": max(0.0, (page_h - t - pad) / page_h),
             "w": (r - l + 2 * pad) / page_w, "h": (t - b + 2 * pad) / page_h} for l, b, r, t in lines]


def _locate_on_page(page, highlights: List[List[str]]) -> List[Dict[str, float]]:
    textpage = page.get_textpage()
    n = textpage.count_chars()
    if n <= 0:
        return []  # scanned page without a text layer
    text = textpage.get_text_range(0, n)
    ntext, index = _normalise(text)
    page_w, page_h = page.get_size()
    boxes: List[Dict[str, float]] = []
    for unit in highlights:
        pos = 0
        for piece in unit:
            span = _find(ntext, piece, pos)
            if not span:
                continue
            s, e = span
            pos = e
            boxes.extend(_line_boxes(textpage, [index[k] for k in range(s, min(e, len(index)))], page_w, page_h))
    return boxes


def pdf_view(path: Path, page_number: int, highlights: List[List[str]]) -> Dict[str, Any]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        count = len(pdf)
        first = min(max(1, page_number or 1), count)
        # the cited page first, then its neighbours, then the rest (chunk page numbers can be off by one)
        order = [first] + [p for d in range(1, count) for p in (first - d, first + d) if 1 <= p <= count]
        page_no, boxes = first, []
        for p in order[:MAX_SEARCH_PAGES]:
            found = _locate_on_page(pdf[p - 1], highlights) if highlights else []
            if found:
                page_no, boxes = p, found
                break
        page = pdf[page_no - 1]
        w, h = page.get_size()
        image = page.render(scale=RENDER_WIDTH_PX / w).to_pil()
        buf = io.BytesIO()
        image.save(buf, format="PNG", optimize=True)
        return {
            "kind": "pdf",
            "page_number": page_no,
            "page_count": count,
            "aspect_ratio": h / w,
            "image": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"),
            "boxes": boxes,
            "found": bool(boxes),
        }
    finally:
        pdf.close()


# ---------------------------------------------------------------- entry point
def build_source_view(doc: Dict[str, Any], chunks: List[Dict[str, Any]], chunk_id: Optional[str],
                      page_number: Optional[int], focus: str) -> Dict[str, Any]:
    """Everything the viewer needs to show the cited passage of `doc` with its supporting sentence highlighted"""
    pos = next((i for i, c in enumerate(chunks) if c["chunk_id"] == chunk_id), None)
    chunk = chunks[pos] if pos is not None else None
    highlights = pick_highlights(chunk["content"], focus) if chunk else []
    page = page_number or (chunk or {}).get("page_number") or 1
    base = {"doc_id": doc["doc_id"], "filename": doc["filename"], "chunk_id": chunk_id,
            "highlights": [" ".join(u) for u in highlights]}

    path = Path(doc.get("file_path") or "")
    if doc.get("file_type") == ".pdf" and path.exists():
        try:
            return {**base, **pdf_view(path, page, highlights)}
        except Exception:  # damaged or encrypted PDF: fall back to the text view
            pass
    window = chunks[max(0, pos - 1): pos + 2] if pos is not None else chunks[:3]
    return {**base, "kind": "text", "page_number": page, "found": bool(highlights),
            "chunks": [{"chunk_id": c["chunk_id"], "section": c.get("section"), "page_number": c.get("page_number"),
                        "content": c["content"], "cited": c["chunk_id"] == chunk_id} for c in window]}
