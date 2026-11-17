"""
Document Processor
Multi-format ingestion: PDF, DOCX, TXT/Markdown, HTML, CSV, XLSX, PPTX and images (PNG/JPG).
- Extracts structured elements (heading / paragraph / list / table / slide) with page numbers
- OCR (RapidOCR) for scanned PDF pages and image files
- Table extraction to Markdown + row-level natural-language records for tabular QA
- Structure-aware chunking via IntelligentChunker
"""
import hashlib
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pypdf
from bs4 import BeautifulSoup

from .intelligent_chunking import IntelligentChunker
from .models import get_ocr, ocr_image

Elements = List[Dict[str, Any]]
Tables = List[Dict[str, Any]]


class DocumentProcessor:
    def __init__(self, chunk_size: int = 700, chunk_overlap: int = 100):
        self.chunker = IntelligentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._ocr_pages = 0

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """SHA-256 of the file contents (integrity + duplicate detection)"""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                hasher.update(block)
        return hasher.hexdigest()

    def extract_elements(self, file_path: str, display_name: Optional[str] = None) -> Tuple[Elements, int, Tables, int]:
        """Parse a file into structured elements. Returns (elements, page_count, tables, ocr_pages).
        `display_name` is the user's file name (uploads are parsed from a temporary file with a random name)."""
        ext = Path(file_path).suffix.lower()
        name = display_name or Path(file_path).name
        self._ocr_pages = 0
        tables: Tables = []
        if ext == ".pdf":
            elements, pages = self._process_pdf(file_path)
        elif ext == ".docx":
            elements, pages, tables = self._process_docx(file_path)
        elif ext in (".txt", ".md", ".text"):
            elements, pages = self._process_txt(file_path)
        elif ext in (".html", ".htm"):
            elements, pages, tables = self._process_html(file_path)
        elif ext == ".csv":
            elements, pages, tables = self._tabular_df_to_elements(pd.read_csv(file_path), name)
        elif ext == ".xlsx":
            elements, pages, tables = self._process_xlsx(file_path, name)
        elif ext == ".pptx":
            elements, pages = self._process_pptx(file_path)
        elif ext in (".png", ".jpg", ".jpeg"):
            elements, pages = self._process_image(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}") 
        if not tables:
            tables = [{"markdown": e["text"]} for e in elements if e.get("element_type") == "table"]
        return elements, pages, tables, self._ocr_pages

    def process_document(self, file_path: str, domain: str = "general", user_id: str = "",
                         filename: Optional[str] = None, version: int = 1,
                         parent_doc_id: Optional[str] = None, doc_id: Optional[str] = None,
                         fixed_size_chunking: bool = False) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        file_size = path.stat().st_size
        if file_size == 0:
            raise ValueError("File is empty (0 bytes)")

        doc_id = doc_id or uuid.uuid4().hex
        elements, page_count, tables, ocr_pages = self.extract_elements(file_path, filename)
        if not any(e.get("text", "").strip() for e in elements):
            raise ValueError("No extractable text found in document")

        if fixed_size_chunking:
            chunks = self.chunker.chunk_fixed_size(elements, doc_id=doc_id)
        else:
            chunks = self.chunker.chunk_structured_elements(elements, doc_id=doc_id)

        now = datetime.now().isoformat()
        metadata = {
            "doc_id": doc_id,
            "user_id": user_id,
            "filename": filename or path.name,
            "file_path": str(file_path),
            "file_type": path.suffix.lower(),
            "file_size": file_size,
            "file_hash": self.calculate_file_hash(file_path),
            "domain": domain,
            "page_count": max(1, page_count),
            "chunk_count": len(chunks),
            "tables_count": len(tables),
            "ocr_pages": ocr_pages,
            "status": "indexed",
            "version": version,
            "parent_doc_id": parent_doc_id,
            "uploaded_at": now,
        }
        return {"metadata": metadata, "chunks": chunks, "elements": elements, "tables": tables}

    # ---------- PDF ----------
    def _process_pdf(self, file_path: str) -> Tuple[Elements, int]:
        reader = pypdf.PdfReader(file_path)
        elements: Elements = []
        section = "General"
        page_texts: List[str] = []
        for page_idx, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if len(text) < 30:  # scanned / image-only page -> OCR
                ocr_text = self._ocr_pdf_page(file_path, page_idx - 1)
                if ocr_text:
                    text = ocr_text
                    self._ocr_pages += 1
            page_texts.append(text)
        page_texts = self._strip_running_headers(page_texts)

        for page_idx, text in enumerate(page_texts, start=1):
            if not text:
                continue
            para: List[str] = []

            def flush():
                if para:
                    elements.append({"text": self._join_lines(para), "page_number": page_idx,
                                     "element_type": "paragraph", "section": section})
                    para.clear()

            for line in text.split("\n"):
                line = re.sub(r"[ \t]{2,}", " ", line).strip()
                if not line:
                    flush()
                    continue
                if self._looks_like_heading(line):
                    flush()
                    section = line
                    elements.append({"text": line, "page_number": page_idx,
                                     "element_type": "heading", "section": section})
                elif line.startswith(("•", "- ", "* ")) or re.match(r"^\d+[.)]\s", line):
                    flush()
                    elements.append({"text": line, "page_number": page_idx,
                                     "element_type": "list", "section": section})
                else:
                    para.append(line)
                    if line.endswith((".", "!", "?", ":")) and len(" ".join(para)) > 300:
                        flush()
            flush()
        return elements, len(reader.pages)

    @staticmethod
    def _strip_running_headers(pages: List[str]) -> List[str]:
        """Remove page headers/footers: lines repeated across pages, 'Page N' footers, 'Org | Title' banners"""
        norm = lambda l: re.sub(r"\d+", "#", re.sub(r"\s+", " ", l.strip().lower()))
        edge_counts: Dict[str, int] = {}
        for text in pages:
            lines = [l for l in text.split("\n") if l.strip()]
            for l in set(lines[:2] + lines[-2:]):
                edge_counts[norm(l)] = edge_counts.get(norm(l), 0) + 1
        out = []
        for text in pages:
            lines = [l for l in text.split("\n") if l.strip()]
            kept = []
            for i, l in enumerate(lines):
                s = l.strip()
                at_edge = i < 2 or i >= len(lines) - 2
                if re.fullmatch(r"(page\s*)?\d+(\s*(of|/)\s*\d+)?", s, re.IGNORECASE):
                    continue
                if at_edge and len(pages) > 1 and edge_counts.get(norm(s), 0) >= max(2, len(pages) // 2):
                    continue
                if i == 0 and " | " in s and len(lines) > 1 and \
                        re.sub(r"\s+", " ", s.rsplit("|", 1)[1]).strip().lower() == re.sub(r"\s+", " ", lines[1]).strip().lower():
                    continue
                kept.append(l)
            out.append("\n".join(kept))
        return out

    @staticmethod
    def _looks_like_heading(line: str) -> bool:
        if len(line) > 80 or len(line) < 3 or line.endswith((".", ",", ";", "-", "(")):
            return False
        last_word = line.split()[-1].lower()
        if last_word in ("and", "or", "of", "the", "to", "for", "with", "in", "on", "a", "an", "by", "at", "from"):
            return False  # a wrapped line, not a heading
        if re.fullmatch(r"[A-Za-z]+,?\s+\d[\d\s-]*", line):
            return False  # "Bengaluru 560025", "September 2026"
        if re.match(r"^(\d+(\.\d+)*\.?|[IVX]+\.|Section \d+|Article \d+|Clause \d+)\s+[A-Z]", line):
            return len(line.split()) <= 10
        # lines carrying amounts/quantities/percentages are data rows, not headings ("SGST @ 9% 36,000")
        if re.search(r"\d[\d,]{3,}|%|₹|\bRs\b|@", line):
            return False
        letters = [c for c in line if c.isalpha()]
        return bool(letters) and (line.isupper() or line.istitle()) and len(line.split()) <= 10

    def _ocr_pdf_page(self, file_path: str, page_index: int) -> str:
        if get_ocr() is None:
            return ""
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(file_path)
            image = pdf[page_index].render(scale=2.0).to_pil()
            pdf.close()
            return ocr_image(image)
        except Exception:
            return ""

    # ---------- Images ----------
    def _process_image(self, file_path: str) -> Tuple[Elements, int]:
        if get_ocr() is None:
            raise ValueError("OCR engine is not available; install rapidocr-onnxruntime to process images")
        from PIL import Image
        with Image.open(file_path) as img:
            text = ocr_image(img)
        self._ocr_pages = 1
        return self._text_to_elements(text), 1

    # ---------- DOCX ----------
    def _process_docx(self, file_path: str) -> Tuple[Elements, int, Tables]:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        doc = Document(file_path)
        elements: Elements = []
        tables: Tables = []
        section = "General"
        # Walk the body in document order so tables stay next to their section
        for child in doc.element.body.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                para = Paragraph(child, doc)
                text = para.text.strip()
                if not text:
                    continue
                style = (para.style.name if para.style is not None else "").lower()
                is_bold = bool(para.runs) and all(r.bold for r in para.runs if r.text.strip())
                if style.startswith("heading") or style == "title" or (is_bold and len(text) < 80):
                    section = text
                    elements.append({"text": text, "page_number": 1, "element_type": "heading", "section": section})
                elif "list" in style or text.startswith(("•", "-", "*")):
                    elements.append({"text": text, "page_number": 1, "element_type": "list", "section": section})
                else:
                    elements.append({"text": text, "page_number": 1, "element_type": "paragraph", "section": section})
            elif tag == "tbl":
                rows = [[c.text.strip() for c in r.cells] for r in Table(child, doc).rows]
                if rows:
                    md = self._format_table_as_markdown(rows)
                    elements.append({"text": md, "page_number": 1, "element_type": "table", "section": section})
                    tables.append({"section": section, "markdown": md, "rows": rows})
        return elements, 1, tables

    # ---------- TXT / Markdown ----------
    def _process_txt(self, file_path: str) -> Tuple[Elements, int]:
        try:
            raw = Path(file_path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = Path(file_path).read_text(encoding="latin-1")
        return self._text_to_elements(raw), 1

    def _text_to_elements(self, raw: str) -> Elements:
        elements: Elements = []
        section = "General"
        for block in re.split(r"\n\s*\n", raw.strip()):
            lines = [l.rstrip() for l in block.strip().split("\n") if l.strip()]
            if not lines:
                continue
            # Markdown tables stay intact
            if all(l.strip().startswith("|") for l in lines):
                elements.append({"text": "\n".join(lines), "page_number": 1, "element_type": "table", "section": section})
                continue
            first = lines[0].strip()
            md_heading = re.match(r"^#{1,6}\s+(.*)", first)
            if md_heading or (len(lines) == 1 and len(first) < 80 and not first.endswith((".", ":", ","))
                              and not first.startswith(("-", "*", "•"))):
                section = (md_heading.group(1) if md_heading else first).strip()
                elements.append({"text": section, "page_number": 1, "element_type": "heading", "section": section})
                lines = lines[1:]
                if not lines:
                    continue
            is_list = all(re.match(r"^\s*([-*•]|\d+[.)])\s", l) for l in lines)
            text = "\n".join(l.strip() for l in lines) if is_list else self._join_lines(lines)
            elements.append({"text": text, "page_number": 1,
                             "element_type": "list" if is_list else "paragraph", "section": section})
        return elements

    # ---------- HTML ----------
    def _process_html(self, file_path: str) -> Tuple[Elements, int, Tables]:
        soup = BeautifulSoup(Path(file_path).read_text(encoding="utf-8", errors="ignore"), "html.parser")
        for s in soup(["script", "style", "nav", "footer", "noscript"]):
            s.decompose()
        elements: Elements = []
        tables: Tables = []
        section = (soup.title.get_text().strip() if soup.title else "") or "General"
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table"]):
            if tag.find_parent("table") is not None and tag.name != "table":
                continue
            if tag.name.startswith("h"):
                text = tag.get_text(" ", strip=True)
                if text:
                    section = text
                    elements.append({"text": text, "page_number": 1, "element_type": "heading", "section": section})
            elif tag.name == "p":
                text = tag.get_text(" ", strip=True)
                if text:
                    elements.append({"text": text, "page_number": 1, "element_type": "paragraph", "section": section})
            elif tag.name in ("ul", "ol"):
                if tag.find_parent(["ul", "ol"]) is not None:
                    continue
                items = [li.get_text(" ", strip=True) for li in tag.find_all("li")]
                items = [i for i in items if i]
                if items:
                    elements.append({"text": "\n".join(f"- {i}" for i in items), "page_number": 1,
                                     "element_type": "list", "section": section})
            else:
                rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])] for tr in tag.find_all("tr")]
                rows = [r for r in rows if r]
                if rows:
                    md = self._format_table_as_markdown(rows)
                    elements.append({"text": md, "page_number": 1, "element_type": "table", "section": section})
                    tables.append({"section": section, "markdown": md, "rows": rows})
        return elements, 1, tables

    # ---------- XLSX / CSV ----------
    def _process_xlsx(self, file_path: str, display_name: Optional[str] = None) -> Tuple[Elements, int, Tables]:
        sheets = pd.read_excel(file_path, sheet_name=None)
        elements: Elements = []
        tables: Tables = []
        for idx, (name, df) in enumerate(sheets.items(), start=1):
            els, _, tbls = self._tabular_df_to_elements(df, f"{display_name or Path(file_path).name} - {name}", page=idx)
            elements.extend(els)
            tables.extend(tbls)
        return elements, max(1, len(sheets)), tables

    def _tabular_df_to_elements(self, df: pd.DataFrame, title: str, page: int = 1) -> Tuple[Elements, int, Tables]:
        """Markdown table preview + row-level natural-language records (enables precise tabular QA)"""
        df = df.dropna(how="all").dropna(axis=1, how="all")
        elements: Elements = [
            {"text": title, "page_number": page, "element_type": "heading", "section": title},
            {"text": f"Dataset {title} has {len(df)} rows. Columns: {', '.join(map(str, df.columns))}.",
             "page_number": page, "element_type": "paragraph", "section": title},
        ]
        rows = [list(map(str, df.columns))] + df.fillna("").astype(str).values.tolist()
        md = self._format_table_as_markdown(rows[:21])  # preview: header + first 20 rows
        elements.append({"text": md, "page_number": page, "element_type": "table", "section": title})
        records = []
        for i, (_, row) in enumerate(df.iterrows(), start=1):
            fields = [f"{col}: {self._fmt_cell(val)}" for col, val in row.items() if pd.notna(val) and str(val).strip()]
            records.append(f"Record {i}: " + "; ".join(fields) + ".")
        for start in range(0, len(records), 5):
            elements.append({"text": "\n".join(records[start:start + 5]), "page_number": page,
                             "element_type": "table",
                             "section": f"{title} (records {start + 1}-{min(start + 5, len(records))})"})
        return elements, 1, [{"title": title, "markdown": md, "rows": rows}]

    @staticmethod
    def _fmt_cell(val: Any) -> str:
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        if isinstance(val, pd.Timestamp):
            return val.strftime("%Y-%m-%d")
        return str(val)

    # ---------- PPTX ----------
    def _process_pptx(self, file_path: str) -> Tuple[Elements, int]:
        from pptx import Presentation
        prs = Presentation(file_path)
        elements: Elements = []
        for num, slide in enumerate(prs.slides, start=1):
            title = None
            if slide.shapes.title is not None and slide.shapes.title.has_text_frame:
                title = slide.shapes.title.text_frame.text.strip() or None
            body: List[str] = []
            for shape in slide.shapes:
                if shape == slide.shapes.title:
                    continue
                if shape.has_text_frame:
                    body.extend(p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip())
                elif getattr(shape, "has_table", False) and shape.has_table:
                    rows = [[c.text.strip() for c in r.cells] for r in shape.table.rows]
                    body.append(self._format_table_as_markdown(rows))
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    body.append(f"Speaker notes: {notes}")
            heading = title or (body[0][:80] if body else f"Slide {num}")
            elements.append({"text": heading, "page_number": num, "element_type": "heading", "section": heading})
            if body:
                elements.append({"text": "\n".join(body), "page_number": num, "element_type": "slide", "section": heading})
        return elements, max(1, len(prs.slides))

    # ---------- helpers ----------
    @staticmethod
    def _join_lines(lines: List[str]) -> str:
        """
        Keep line structure for key/value blocks, forms and short lines (invoices,
        addresses, table-like text); re-flow hard-wrapped prose into one paragraph.
        """
        lines = [l.strip() for l in lines if l.strip()]
        if len(lines) <= 1:
            return lines[0] if lines else ""
        avg_len = sum(len(l) for l in lines) / len(lines)
        keyvalue = sum(1 for l in lines if re.match(r"^[\w ()/.#&-]{2,40}:\s*\S", l)) >= max(2, len(lines) // 2)
        return "\n".join(lines) if (keyvalue or avg_len < 45) else " ".join(lines)

    @staticmethod
    def _format_table_as_markdown(rows: List[List[str]]) -> str:
        if not rows:
            return ""
        width = max(len(r) for r in rows)
        rows = [[str(c).replace("|", "/").replace("\n", " ") for c in r] + [""] * (width - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join(lines)
