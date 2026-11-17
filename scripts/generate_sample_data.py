"""Generate the 50-document demo corpus for the Document Intelligence & Hybrid RAG System.

Usage (from the project root):

    .venv/Scripts/python.exe scripts/generate_sample_data.py

Writes 50 realistic, fully fictional documents into ``data/sample_documents/<domain>/``
(domains: hr, legal, healthcare, finance, general - 10 each) plus
``data/sample_documents/manifest.json``. All content is hardcoded, so the output is
deterministic and the script can be re-run at any time (the output folder is rebuilt).

Format mix: 12 PDF (incl. 1 scanned image-only PDF that needs OCR), 10 DOCX, 5 TXT,
3 Markdown, 5 HTML, 5 CSV, 5 XLSX, 5 PPTX.

The questions in ``evaluation/eval_dataset.json`` are written against this corpus.
Documents are written once for a single company and then rebranded per document (see ORGS /
ORG_OF_FILE) across nine fictional organisations plus Silverleaf hospital (10 in total); each organisation
gets its own colour theme in the rendered PDF / DOCX / PPTX / XLSX / HTML files.
All organisations and people are fictional.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "sample_documents"
FONT_DIR = Path("C:/Windows/Fonts")
DOMAINS = ("hr", "legal", "healthcare", "finance", "general")
FIXED_DATE = dt.datetime(2026, 10, 1, 9, 0, 0)

NIMBUS = "Nimbus Technologies Pvt. Ltd."
HOSPITAL = "Silverleaf Multispeciality Hospital, Bengaluru"

DOCS: list[dict] = []


# --------------------------------------------------------------------------- #
# Content building blocks
# --------------------------------------------------------------------------- #
def H1(text):
    return ("h1", text)


def H2(text):
    return ("h2", text)


def P(*parts):
    return ("p", " ".join(parts))


def UL(*items):
    return ("ul", list(items))


def TABLE(*rows):
    return ("table", [[str(c) for c in r] for r in rows])


def doc(filename, domain, title, description, **content):
    """Register a document. content: pages | blocks | slides | sheets | rows | scanned_pages."""
    assert domain in DOMAINS, domain
    fmt = filename.rsplit(".", 1)[1].lower()
    DOCS.append(dict(filename=filename, domain=domain, format=fmt, title=title,
                     description=description, org=content.pop("org", NIMBUS), **content))


# --------------------------------------------------------------------------- #
# Organisations: the corpus spans several fictional organisations so the demo
# library reads like a real multi-party document set. Related documents stay
# with the same organisation (e.g. both leave policies, the product and its
# financial reports) so cross-document questions remain consistent.
# --------------------------------------------------------------------------- #
ORGS = {
    "helix": ("Helix Systems Pvt. Ltd.", "Helix", "helixsystems.example"),
    "orion": ("Orion Softworks Pvt. Ltd.", "Orion", "orionsoft.example"),
    "brightpath": ("Brightpath Consulting LLP", "Brightpath", "brightpath.example"),
    "tejas": ("Tejas Infrastructure Ltd.", "Tejas", "tejasinfra.example"),
    "meridian": ("Meridian Capital Pvt. Ltd.", "Meridian", "meridiancap.example"),
    "cobalt": ("Cobalt Cloud Services Pvt. Ltd.", "Cobalt", "cobaltcloud.example"),
    "lumen": ("Lumen Insurtech Pvt. Ltd.", "Lumen", "lumeninsurtech.example"),
    "zenith": ("Zenith Retail Ltd.", "Zenith", "zenithretail.example"),
    "aster": ("Aster Logistics Pvt. Ltd.", "Aster", "asterlogistics.example"),
}
ORG_OF_FILE = {
    **dict.fromkeys(["HR_Leave_Policy_2025.pdf", "HR_Leave_Policy_2026.pdf", "Employee_Onboarding_Guide.html",
                     "Company_Newsletter_Oct_2026.html"], "orion"),
    **dict.fromkeys(["Employee_Directory.csv", "Expense_Ledger_Q2_2026.csv", "Holiday_Calendar_2026.xlsx"],
                    "zenith"),
    **dict.fromkeys(["Performance_Review_Process.txt", "Remote_Work_Policy.docx"], "aster"),
    **dict.fromkeys(["Travel_Reimbursement_Policy.docx", "Code_of_Conduct_and_POSH.md",
                     "Employee_Benefits_2026.pptx"], "brightpath"),
    **dict.fromkeys(["Office_Lease_Deed_Whitefield.pdf", "Vendor_Contract_Facility_Services.docx",
                     "Compliance_Checklist_2026.xlsx", "IT_Security_Policy_Scanned.pdf", "Product_Inventory.csv"],
                    "tejas"),
    **dict.fromkeys(["Annual_Budget_FY2026-27.xlsx", "Purchase_Order_PO-2026-3317.docx",
                     "Approved_Vendor_Register.csv"], "meridian"),
    "Invoice_INV-2026-8842.pdf": "cobalt",
    "Project_Proposal_SmartClaims.pptx": "lumen",
}  # everything else (contracts, product, finance reports, resumes) belongs to Helix Systems


def rebrand_text(s: str, filename: str) -> str:
    """Rewrite the original single-company wording for the organisation that owns `filename`"""
    full, short, domain = ORGS[ORG_OF_FILE.get(filename, "helix")]
    plain = full.replace(" Pvt. Ltd.", "").replace(" Ltd.", "").replace(" LLP", "")
    for old, new in (("NimbusDesk", "HelixDesk"), ("Nimbus Technologies Pvt. Ltd.", full),
                     ("Nimbus Technologies", plain), ("nimbustech.example", domain), ("HackNimbus", f"Hack{short}"),
                     ("NIMBUS", short.upper()), ("Nimbians", f"{short} team"), ("Nimbus", short)):
        s = s.replace(old, new)
    return s


def rebrand(spec: dict) -> dict:
    original = spec["filename"]

    def walk(o):
        if isinstance(o, str):
            return rebrand_text(o, original)
        if isinstance(o, list):
            return [walk(v) for v in o]
        if isinstance(o, tuple):
            return tuple(walk(v) for v in o)
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        return o

    return walk(spec)


# --------------------------------------------------------------------------- #
# Visual theme: every organisation gets its own accent colour
# --------------------------------------------------------------------------- #
THEMES = {"Helix": (37, 99, 235), "Orion": (79, 70, 229), "Brightpath": (13, 148, 136), "Tejas": (234, 88, 12),
          "Meridian": (5, 150, 105), "Cobalt": (2, 132, 199), "Lumen": (190, 24, 93), "Silverleaf": (225, 29, 72),
          "Zenith": (202, 138, 4), "Aster": (124, 58, 237)}
PALETTE = [(37, 99, 235), (79, 70, 229), (13, 148, 136), (234, 88, 12), (5, 150, 105), (2, 132, 199),
           (190, 24, 93), (124, 58, 237), (202, 138, 4), (8, 145, 178)]
INK, MUTED, ZEBRA = (30, 41, 59), (100, 116, 139), (244, 246, 250)


def accent(org: str) -> tuple:
    for key, rgb in THEMES.items():
        if key in (org or ""):
            return rgb
    return PALETTE[sum(map(ord, org or "x")) % len(PALETTE)]


def tint(rgb: tuple, amount: float = 0.88) -> tuple:
    """Mix a colour with white (amount 0..1 = how much white)"""
    return tuple(round(c + (255 - c) * amount) for c in rgb)


def hexc(rgb: tuple) -> str:
    return "{:02X}{:02X}{:02X}".format(*rgb)


def is_total_row(row) -> bool:
    """Rows such as 'Total amount payable' (the label may sit in the first or second column)"""
    labels = [str(c).strip().lower() for c in list(row)[:2] if c is not None]
    return any(l.startswith(("total", "grand total", "net total", "balance due", "amount payable")) for l in labels)


# --------------------------------------------------------------------------- #
# Renderers
# --------------------------------------------------------------------------- #
_LATIN1_MAP = {"₹": "Rs.", "•": "-", "–": "-", "—": "-", "’": "'",
               "‘": "'", "“": '"', "”": '"', "≥": ">=", "≤": "<=",
               "×": "x"}


def _latin1(s: str) -> str:
    for k, v in _LATIN1_MAP.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def _make_pdf_class():
    from fpdf import FPDF

    class DocPDF(FPDF):
        def __init__(self, org, title):
            super().__init__(format="A4")
            self.org, self.doc_title = org, title
            self.accent = accent(org)
            self.set_margins(18, 21, 18)
            self.set_auto_page_break(True, margin=18)
            self.set_creation_date(FIXED_DATE.replace(tzinfo=dt.timezone.utc))
            self.unicode_ok = (FONT_DIR / "arial.ttf").exists() and (FONT_DIR / "arialbd.ttf").exists()
            if self.unicode_ok:
                self.add_font("Body", "", str(FONT_DIR / "arial.ttf"))
                self.add_font("Body", "B", str(FONT_DIR / "arialbd.ttf"))
                self.fam = "Body"
            else:
                self.fam = "helvetica"

        def t(self, s):
            return s if self.unicode_ok else _latin1(s)

        def header(self):
            # full-width colour band with the organisation and document name
            self.set_fill_color(*self.accent)
            self.rect(0, 0, self.w, 12.5, "F")
            self.set_fill_color(*tint(self.accent, 0.55))
            self.rect(0, 12.5, self.w, 0.9, "F")
            if self.org:
                self.set_xy(self.l_margin, 3.6)
                self.set_font(self.fam, "B", 8.5)
                self.set_text_color(255, 255, 255)
                self.cell(self.epw, 5, self.t(f"{self.org}  |  {self.doc_title}"), align="L")
            self.set_xy(self.l_margin, 21)
            self.set_text_color(*INK)

        def footer(self):
            self.set_draw_color(*tint(self.accent, 0.6))
            self.set_line_width(0.3)
            self.line(self.l_margin, self.h - 14, self.w - self.r_margin, self.h - 14)
            self.set_y(-12.5)
            self.set_font(self.fam, "", 7.5)
            self.set_text_color(*MUTED)
            self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")
            self.set_text_color(*INK)

    return DocPDF


def _pdf_blocks(pdf, blocks):
    from fpdf.fonts import FontFace

    w = pdf.epw
    acc = pdf.accent
    for kind, val in blocks:
        if kind == "h1":
            pdf.ln(2.5)
            y = pdf.get_y()
            pdf.set_fill_color(*acc)
            pdf.rect(pdf.l_margin, y + 0.6, 1.3, 5.6, "F")
            pdf.set_x(pdf.l_margin + 4)
            pdf.set_font(pdf.fam, "B", 12.5)
            pdf.set_text_color(*acc)
            pdf.multi_cell(w - 4, 6.8, pdf.t(val), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*INK)
            pdf.ln(1)
        elif kind == "h2":
            pdf.ln(1)
            pdf.set_font(pdf.fam, "B", 10.5)
            pdf.set_text_color(*INK)
            pdf.multi_cell(w, 6, pdf.t(val), new_x="LMARGIN", new_y="NEXT")
        elif kind == "p":
            pdf.set_font(pdf.fam, "", 9.8)
            pdf.set_text_color(51, 65, 85)
            pdf.multi_cell(w, 5, pdf.t(val), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*INK)
            pdf.ln(1.5)
        elif kind == "ul":
            pdf.set_font(pdf.fam, "", 9.8)
            for item in val:
                y = pdf.get_y()
                pdf.set_fill_color(*acc)
                pdf.rect(pdf.l_margin + 1.2, y + 1.9, 1.4, 1.4, "F")
                pdf.set_x(pdf.l_margin + 5)
                pdf.set_text_color(51, 65, 85)
                pdf.multi_cell(w - 5, 5, pdf.t(item), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*INK)
            pdf.ln(1.5)
        elif kind == "table":
            pdf.set_font(pdf.fam, "", 8.8)
            pdf.set_draw_color(*tint(acc, 0.75))
            pdf.set_line_width(0.2)
            head = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=acc)
            total = FontFace(emphasis="BOLD", color=INK, fill_color=tint(acc, 0.82))
            # column widths follow content length (long descriptions get more room)
            lens = [max(len(str(r[c])) for r in val) for c in range(len(val[0]))]
            widths = [min(max(n, 6), 48) for n in lens]
            pdf.set_fill_color(*ZEBRA)
            with pdf.table(text_align="LEFT", line_height=5, first_row_as_headings=True, headings_style=head,
                           cell_fill_color=ZEBRA, cell_fill_mode="ROWS", borders_layout="HORIZONTAL_LINES",
                           padding=(1.1, 1.8), col_widths=widths) as tbl:
                for r in val:
                    row = tbl.row()
                    style = total if r is not val[0] and is_total_row(r) else None
                    for c in r:
                        row.cell(pdf.t(c), style=style)
            pdf.ln(2.5)


def render_pdf(spec, path):
    DocPDF = _make_pdf_class()
    pdf = DocPDF(spec["org"], spec["title"])
    for i, blocks in enumerate(spec["pages"]):
        pdf.add_page()
        if i == 0:
            pdf.set_font(pdf.fam, "B", 18)
            pdf.set_text_color(*INK)
            pdf.multi_cell(pdf.epw, 8.5, pdf.t(spec["title"]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_fill_color(*pdf.accent)
            pdf.rect(pdf.l_margin, pdf.get_y() + 1, 22, 1.2, "F")
            pdf.ln(4.5)
        _pdf_blocks(pdf, blocks)
        if pdf.page_no() != i + 1:
            raise RuntimeError(f"{spec['filename']}: logical page {i + 1} overflowed onto a new page")
    pdf.output(str(path))


def _wrap(draw, text, font, width):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def render_scanned_pdf(spec, path):
    """Render text to bitmap pages (Pillow) and embed them as image-only PDF pages (no text layer)."""
    from fpdf import FPDF
    from PIL import Image, ImageDraw, ImageFont

    def font(name, size):
        f = FONT_DIR / name
        return ImageFont.truetype(str(f), size) if f.exists() else ImageFont.load_default(size=size)

    body, bold = font("arial.ttf", 28), font("arialbd.ttf", 34)
    W, Hh, margin = 1240, 1754, 95
    pdf = FPDF(format="A4")
    pdf.set_creation_date(FIXED_DATE.replace(tzinfo=dt.timezone.utc))
    pdf.set_auto_page_break(False)
    for page_no, paras in enumerate(spec["scanned_pages"], start=1):
        img = Image.new("RGB", (W, Hh), "white")
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, W, 26], fill=accent(spec["org"]))  # printed letterhead strip
        y = 90
        for para in paras:
            is_head = para.startswith("# ")
            text = para[2:] if is_head else para
            f = bold if is_head else body
            for line in _wrap(draw, text, f, W - 2 * margin):
                draw.text((margin, y), line, fill="black", font=f)
                y += 46 if is_head else 38
            y += 16
        draw.text((W // 2 - 40, Hh - 70), f"Page {page_no}", fill="black", font=body)
        if y > Hh - 100:
            raise RuntimeError(f"scanned page {page_no} overflow (y={y})")
        pdf.add_page()
        pdf.image(img, x=0, y=0, w=210, h=297)
    pdf.output(str(path))


def _docx_shade(cell, rgb):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexc(rgb))
    cell._tc.get_or_add_tcPr().append(shd)


def _docx_table_borders(tbl, rgb):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "bottom", "insideH"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "4")
        e.set(qn("w:color"), hexc(rgb))
        borders.append(e)
    for edge in ("left", "right", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "nil")
        borders.append(e)
    tbl._tbl.tblPr.append(borders)


def _docx_field(paragraph, code):
    """Insert a Word field (e.g. PAGE / NUMPAGES) into a paragraph"""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    run = paragraph.add_run()
    for kind, text in (("begin", None), (None, code), ("separate", None), (None, "1"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        elif text == code:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = f" {code} "
        else:
            el = OxmlElement("w:t")
            el.text = text
        run._r.append(el)
    return run


def _docx_bottom_border(paragraph, rgb, size=12):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    pbdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    b.set(qn("w:val"), "single")
    b.set(qn("w:sz"), str(size))
    b.set(qn("w:space"), "4")
    b.set(qn("w:color"), hexc(rgb))
    pbdr.append(b)
    paragraph._p.get_or_add_pPr().append(pbdr)


def render_docx(spec, path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor

    acc = accent(spec["org"])
    d = Document()
    cp = d.core_properties
    cp.author, cp.title, cp.created, cp.modified = spec["org"], spec["title"], FIXED_DATE, FIXED_DATE

    for sec in d.sections:
        sec.left_margin = sec.right_margin = Cm(2.1)
        sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2)
        hp = sec.header.paragraphs[0]
        run = hp.add_run((spec["org"] or "").upper())
        run.font.size, run.font.bold, run.font.color.rgb = Pt(8), True, RGBColor(*acc)
        hp.add_run("    " + spec["title"]).font.color.rgb = RGBColor(*MUTED)
        for r in hp.runs:
            r.font.size = Pt(8)
        _docx_bottom_border(hp, acc, 10)
        fp = sec.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for piece in ("Page ", ("PAGE",), " of ", ("NUMPAGES",)):
            r = _docx_field(fp, piece[0]) if isinstance(piece, tuple) else fp.add_run(piece)
            r.font.size, r.font.color.rgb = Pt(8), RGBColor(*MUTED)

    styles = d.styles
    normal = styles["Normal"]
    normal.font.name, normal.font.size, normal.font.color.rgb = "Calibri", Pt(10.5), RGBColor(51, 65, 85)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15
    for name, size, color in (("Title", 24, INK), ("Heading 1", 14, acc), ("Heading 2", 11.5, INK)):
        st = styles[name]
        st.font.name, st.font.size, st.font.bold, st.font.color.rgb = "Calibri", Pt(size), True, RGBColor(*color)
        st.paragraph_format.space_before = Pt(14 if name == "Heading 1" else 8)
        st.paragraph_format.space_after = Pt(4)

    title = d.add_heading(spec["title"], level=0)
    _docx_bottom_border(title, acc, 18)
    for kind, val in spec["blocks"]:
        if kind == "h1":
            d.add_heading(val, level=1)
        elif kind == "h2":
            d.add_heading(val, level=2)
        elif kind == "p":
            d.add_paragraph(val)
        elif kind == "ul":
            for item in val:
                d.add_paragraph(item, style="List Bullet")
        elif kind == "table":
            tbl = d.add_table(rows=len(val), cols=len(val[0]))
            tbl.style = "Table Grid"
            _docx_table_borders(tbl, tint(acc, 0.7))
            for r, row in enumerate(val):
                total = r > 0 and is_total_row(row)
                for c, text in enumerate(row):
                    cell = tbl.cell(r, c)
                    cell.text = text
                    para = cell.paragraphs[0]
                    para.paragraph_format.space_after = Pt(0)
                    for run in para.runs:
                        run.font.size = Pt(9.5)
                        if r == 0:
                            run.bold, run.font.color.rgb = True, RGBColor(255, 255, 255)
                        elif total:
                            run.bold = True
                    if r == 0:
                        _docx_shade(cell, acc)
                    elif total:
                        _docx_shade(cell, tint(acc, 0.82))
                    elif r % 2 == 0:
                        _docx_shade(cell, ZEBRA)
            d.add_paragraph("")
    d.save(str(path))


def render_txt(spec, path):
    out = [spec["title"].upper(), "=" * len(spec["title"]), ""]
    for kind, val in spec["blocks"]:
        if kind == "h1":
            out += [val.upper(), "-" * len(val)]
        elif kind == "h2":
            out += [val]
        elif kind == "p":
            out += [val, ""]
        elif kind == "ul":
            out += [f"  - {i}" for i in val] + [""]
        elif kind == "table":
            widths = [max(len(r[c]) for r in val) for c in range(len(val[0]))]
            for n, r in enumerate(val):
                out.append("  " + " | ".join(x.ljust(widths[i]) for i, x in enumerate(r)))
                if n == 0:
                    out.append("  " + "-+-".join("-" * w for w in widths))
            out.append("")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def render_md(spec, path):
    out = [f"# {spec['title']}", ""]
    for kind, val in spec["blocks"]:
        if kind == "h1":
            out += [f"## {val}", ""]
        elif kind == "h2":
            out += [f"### {val}", ""]
        elif kind == "p":
            out += [val, ""]
        elif kind == "ul":
            out += [f"- {i}" for i in val] + [""]
        elif kind == "table":
            out.append("| " + " | ".join(val[0]) + " |")
            out.append("|" + "|".join("---" for _ in val[0]) + "|")
            out += ["| " + " | ".join(r) + " |" for r in val[1:]]
            out.append("")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def render_html(spec, path):
    e = html.escape
    acc = "#" + hexc(accent(spec["org"]))
    soft = "#" + hexc(tint(accent(spec["org"]), 0.9))
    css = (
        ":root{--accent:%s;--soft:%s;--ink:#1e293b;--muted:#64748b;--line:#e2e8f0}"
        "*{box-sizing:border-box}"
        "body{margin:0;background:#f1f5f9;color:var(--ink);font:15px/1.65 'Segoe UI',system-ui,-apple-system,"
        "Roboto,Arial,sans-serif}"
        ".band{height:8px;background:linear-gradient(90deg,var(--accent),var(--soft))}"
        ".page{max-width:920px;margin:32px auto;padding:44px 52px;background:#fff;border-radius:18px;"
        "box-shadow:0 12px 40px rgba(15,23,42,.08);border:1px solid var(--line)}"
        ".org{margin:0 0 6px;color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase;"
        "font-size:12px}"
        "h1{margin:0 0 22px;font-size:30px;line-height:1.2;letter-spacing:-.01em}"
        "h1:after{content:'';display:block;width:56px;height:4px;border-radius:4px;background:var(--accent);"
        "margin-top:14px}"
        "h2{margin:30px 0 10px;font-size:19px;color:var(--accent);padding-left:12px;"
        "border-left:4px solid var(--accent)}"
        "h3{margin:20px 0 6px;font-size:16px}"
        "p{margin:0 0 12px;color:#334155}"
        "ul{padding-left:20px}li{margin:4px 0}li::marker{color:var(--accent)}"
        "table{width:100%%;border-collapse:separate;border-spacing:0;margin:14px 0 20px;font-size:14px;"
        "border:1px solid var(--line);border-radius:12px;overflow:hidden}"
        "th{background:var(--accent);color:#fff;text-align:left;padding:10px 12px;font-weight:600}"
        "td{padding:9px 12px;border-top:1px solid var(--line)}"
        "tr:nth-child(even) td{background:#f8fafc}"
        "@media(max-width:700px){.page{margin:0;border-radius:0;padding:24px 18px}}"
    ) % (acc, soft)
    out = ["<!DOCTYPE html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           f"<title>{e(spec['title'])}</title>", f"<style>{css}</style>", "</head>", "<body>",
           '<div class="band"></div>', '<main class="page">',
           f'<p class="org">{e(spec["org"])}</p>', f"<h1>{e(spec['title'])}</h1>"]
    for kind, val in spec["blocks"]:
        if kind == "h1":
            out.append(f"<h2>{e(val)}</h2>")
        elif kind == "h2":
            out.append(f"<h3>{e(val)}</h3>")
        elif kind == "p":
            out.append(f"<p>{e(val)}</p>")
        elif kind == "ul":
            out.append("<ul>" + "".join(f"<li>{e(i)}</li>" for i in val) + "</ul>")
        elif kind == "table":
            out.append("<table>")
            out.append("<tr>" + "".join(f"<th>{e(c)}</th>" for c in val[0]) + "</tr>")
            for r in val[1:]:
                out.append("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>")
            out.append("</table>")
    out += ["</main>", "</body>", "</html>"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _pptx_bullets(paragraph, rgb):
    """Real PowerPoint bullets (not text characters), coloured with the accent"""
    from pptx.oxml.ns import qn
    from lxml import etree
    pPr = paragraph._p.get_or_add_pPr()
    pPr.set("marL", "320040")
    pPr.set("indent", "-320040")
    clr = etree.SubElement(pPr, qn("a:buClr"))
    etree.SubElement(clr, qn("a:srgbClr")).set("val", hexc(rgb))
    etree.SubElement(pPr, qn("a:buFont")).set("typeface", "Arial")
    etree.SubElement(pPr, qn("a:buChar")).set("char", "●")


def render_pptx(spec, path):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches, Pt

    acc = accent(spec["org"])
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    W, H = prs.slide_width, prs.slide_height
    prs.core_properties.author = spec["org"]
    prs.core_properties.title = spec["title"]
    prs.core_properties.created = FIXED_DATE
    prs.core_properties.modified = FIXED_DATE

    def rect(slide, x, y, w, h, rgb, shape=MSO_SHAPE.RECTANGLE):
        s = slide.shapes.add_shape(shape, x, y, w, h)
        s.fill.solid()
        s.fill.fore_color.rgb = RGBColor(*rgb)
        s.line.fill.background()
        s.shadow.inherit = False
        return s

    def background(slide, rgb):
        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = RGBColor(*rgb)

    def style_runs(tf, size, rgb, bold=False):
        for p in tf.paragraphs:
            for r in p.runs:
                r.font.size, r.font.bold, r.font.name = Pt(size), bold, "Segoe UI"
                r.font.color.rgb = RGBColor(*rgb)

    # title slide: dark canvas, accent stripe and glow
    first_title, subtitle = spec["slides"][0]
    s = prs.slides.add_slide(prs.slide_layouts[0])
    background(s, (15, 23, 42))
    rect(s, 0, 0, Inches(0.22), H, acc)
    rect(s, Inches(9.6), Inches(-1.6), Inches(5.2), Inches(5.2), tint(acc, 0.15), MSO_SHAPE.OVAL)
    rect(s, Inches(11.0), Inches(4.4), Inches(3.4), Inches(3.4), (30, 41, 59), MSO_SHAPE.OVAL)
    rect(s, Inches(0.9), Inches(4.55), Inches(1.3), Inches(0.08), acc)
    s.shapes.title.left, s.shapes.title.top = Inches(0.9), Inches(2.0)
    s.shapes.title.width, s.shapes.title.height = Inches(9.4), Inches(2.4)
    s.shapes.title.text = first_title
    tf = s.shapes.title.text_frame
    tf.word_wrap = True
    for p in tf.paragraphs:
        p.alignment = 1  # left
    style_runs(tf, 40, (255, 255, 255), bold=True)
    sub = s.placeholders[1]
    sub.left, sub.top, sub.width, sub.height = Inches(0.9), Inches(4.85), Inches(9.4), Inches(1.2)
    sub.text = subtitle
    for p in sub.text_frame.paragraphs:
        p.alignment = 1
    style_runs(sub.text_frame, 18, (148, 163, 184))
    # bring text above decorative shapes
    tree = s.shapes._spTree
    for shp in (s.shapes.title, sub):
        tree.remove(shp._element)
        tree.append(shp._element)

    for title, bullets in spec["slides"][1:]:
        s = prs.slides.add_slide(prs.slide_layouts[5])  # title only
        background(s, (248, 250, 252))
        rect(s, 0, 0, W, Inches(0.12), acc)
        rect(s, Inches(0.6), Inches(0.75), Inches(0.1), Inches(0.75), acc)
        t = s.shapes.title
        t.left, t.top, t.width, t.height = Inches(0.85), Inches(0.62), Inches(11.6), Inches(1.0)
        t.text = title
        t.text_frame.word_wrap = True
        for p in t.text_frame.paragraphs:
            p.alignment = 1
        style_runs(t.text_frame, 30, INK, bold=True)
        kpi = 2 <= len(bullets) <= 4 and all(": " in b and len(b) <= 48 for b in bullets)
        if kpi:
            # short "label: value" bullets become KPI tiles (text stays identical for extraction)
            gap, top = Inches(0.3), Inches(2.2)
            tw = int((Inches(12.13) - gap * (len(bullets) - 1)) / len(bullets))
            for k, b in enumerate(bullets):
                x = Inches(0.6) + k * (tw + gap)
                tile = rect(s, x, top, tw, Inches(2.4), (255, 255, 255), MSO_SHAPE.ROUNDED_RECTANGLE)
                tile.adjustments[0] = 0.08
                tile.line.color.rgb = RGBColor(226, 232, 240)
                rect(s, x, top, tw, Inches(0.09), acc)
                box = s.shapes.add_textbox(x + Inches(0.35), top + Inches(0.45), tw - Inches(0.7), Inches(1.8))
                tf = box.text_frame
                tf.word_wrap = True
                label, value = b.split(": ", 1)
                r1 = tf.paragraphs[0].add_run()
                r1.text = label + ":"
                r1.font.size, r1.font.name, r1.font.color.rgb = Pt(14), "Segoe UI", RGBColor(*MUTED)
                tf.paragraphs[0].space_after = Pt(6)
                r2 = tf.add_paragraph().add_run()
                r2.text = value
                r2.font.size, r2.font.bold, r2.font.name = Pt(30 if len(value) <= 14 else 24), True, "Segoe UI"
                r2.font.color.rgb = RGBColor(*acc)
        else:
            size = 22 if len(bullets) <= 3 else 20 if len(bullets) <= 5 else 17 if len(bullets) <= 7 else 15
            cpl = 11.3 * 72 / (size * 0.52)  # rough characters per line
            lines = sum(max(1, -(-len(b) // int(cpl))) for b in bullets)
            height = min(5.1, 0.75 + lines * size * 1.3 / 72 + len(bullets) * 10 / 72)
            card = rect(s, Inches(0.6), Inches(1.85), Inches(12.13), Inches(max(height, 1.6)), (255, 255, 255),
                        MSO_SHAPE.ROUNDED_RECTANGLE)
            card.adjustments[0] = 0.04
            card.line.color.rgb = RGBColor(226, 232, 240)
            card.line.width = Pt(1)
            rect(s, Inches(0.6), Inches(1.85), Inches(0.09), Inches(max(height, 1.6)), tint(acc, 0.35))
            box = s.shapes.add_textbox(Inches(1.0), Inches(2.15), Inches(11.3), Inches(max(height, 1.6) - 0.5))
            tf = box.text_frame
            tf.word_wrap = True
            for k, b in enumerate(bullets):
                p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                p.text = b
                p.space_after = Pt(10)
                _pptx_bullets(p, acc)
            style_runs(tf, size, (51, 65, 85))
        rect(s, W - Inches(1.05), H - Inches(0.62), Inches(0.5), Inches(0.08), tint(acc, 0.5))
    prs.save(str(path))


def render_csv(spec, path):
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(spec["rows"])


def render_xlsx(spec, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    acc = hexc(accent(spec["org"]))
    zebra = PatternFill("solid", fgColor=hexc(ZEBRA))
    total_fill = PatternFill("solid", fgColor=hexc(tint(accent(spec["org"]), 0.82)))
    head_fill = PatternFill("solid", fgColor=acc)
    line = Side(style="thin", color="E2E8F0")
    wb = Workbook()
    wb.properties.creator = spec["org"]
    wb.properties.title = spec["title"]
    wb.properties.created = FIXED_DATE
    wb.properties.modified = FIXED_DATE
    wb.remove(wb.active)
    for name, rows in spec["sheets"].items():
        ws = wb.create_sheet(name)
        ws.sheet_properties.tabColor = acc
        ws.sheet_view.showGridLines = False
        for r in rows:
            ws.append(list(r))
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
            cell.fill = head_fill
            cell.alignment = Alignment(vertical="center", horizontal="left", indent=1)
        ws.row_dimensions[1].height = 24
        for i, row in enumerate(ws.iter_rows(min_row=2), start=2):
            total = is_total_row([c.value for c in row])
            for cell in row:
                cell.border = Border(bottom=line)
                cell.font = Font(name="Calibri", size=10.5, bold=total, color="1E293B")
                cell.alignment = Alignment(vertical="center", indent=1)
                if total:
                    cell.fill = total_fill
                elif i % 2 == 0:
                    cell.fill = zebra
                if isinstance(cell.value, int) and not isinstance(cell.value, bool):
                    cell.number_format = "#,##0"
                elif isinstance(cell.value, float):
                    cell.number_format = "#,##0.00"
            ws.row_dimensions[i].height = 19
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(12, width + 4), 60)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    wb.save(str(path))


RENDERERS = {"docx": render_docx, "txt": render_txt, "md": render_md, "html": render_html,
             "pptx": render_pptx, "csv": render_csv, "xlsx": render_xlsx}


def _render(spec, path):
    if spec["format"] == "pdf":
        (render_scanned_pdf if "scanned_pages" in spec else render_pdf)(spec, path)
    else:
        RENDERERS[spec["format"]](spec, path)


# =========================================================================== #
#                                   HR (10)                                   #
# =========================================================================== #
_LEAVE_INTRO = (
    "This policy sets out the types of leave available to employees of Nimbus Technologies Pvt. Ltd., "
    "the entitlement attached to each type, and the process for requesting and approving time away from "
    "work. It is intended to give employees predictable rest and recovery time while allowing teams to "
    "plan delivery commitments to customers with confidence."
)
_LEAVE_SCOPE = (
    "The policy applies to all permanent and fixed-term employees on the rolls of the company in India, "
    "including the Bengaluru headquarters at Lakeview Tech Park, the Pune development centre and the "
    "Hyderabad sales office. Interns, consultants and contract staff supplied by agencies are governed by "
    "their engagement letters and are not covered. Where state Shops and Establishments legislation grants "
    "a more generous entitlement, the statutory entitlement prevails."
)

doc("HR_Leave_Policy_2025.pdf", "hr", "Employee Leave Policy 2025 (POL-HR-011)",
    "2025 leave policy: annual, sick, casual, parental, bereavement, work-from-home and sabbatical rules.",
    pages=[
        [
            H1("1. Document Control"),
            TABLE(["Field", "Detail"], ["Policy ID", "POL-HR-011"], ["Version", "3.0"],
                  ["Effective date", "1 January 2025"],
                  ["Policy owner", "Kavitha Menon, Head - People Operations"],
                  ["Approved by", "Board HR Committee on 12 December 2024"],
                  ["Next review", "December 2025"]),
            H1("2. Purpose"), P(_LEAVE_INTRO),
            H1("3. Scope and Applicability"), P(_LEAVE_SCOPE),
            H1("4. Leave Year"),
            P("The leave year runs from 1 January to 31 December. Employees who join part-way through the "
              "year receive a pro-rated entitlement from their date of joining. All leave balances are "
              "maintained in the NimbusHR portal, which is the single source of truth for balances, approvals "
              "and leave history."),
        ],
        [
            H1("5. Annual Leave"),
            P("Every confirmed employee is entitled to 18 days of paid annual leave in each leave year. Annual "
              "leave accrues at the rate of 1.5 days for every completed month of service and may be availed "
              "once it has been credited. Employees on probation may avail up to 4 days of accrued annual leave "
              "before confirmation."),
            P("A maximum of 10 days of unused annual leave may be carried forward into the next leave year; any "
              "balance above 10 days lapses on 31 December. Employees may encash up to 5 days of unused annual "
              "leave each year, calculated on basic salary and paid in the December payroll."),
            H1("6. Sick Leave"),
            P("Employees receive 10 days of paid sick leave per leave year, credited on 1 January. A medical "
              "certificate from a registered medical practitioner is required for any absence of more than 2 "
              "consecutive days. Unused sick leave cannot be carried forward or encashed. Prolonged illness "
              "beyond the sick leave balance is adjusted first against annual leave and then treated as leave "
              "without pay."),
            H1("7. Casual Leave"),
            P("Employees receive 7 days of casual leave per year for personal errands and short emergencies. "
              "Casual leave may not exceed 3 consecutive days and cannot be prefixed or suffixed to annual leave."),
        ],
        [
            H1("8. Parental Leave"),
            P("Female employees are entitled to 26 weeks of paid maternity leave for up to two children, of which "
              "not more than 8 weeks may precede the expected date of delivery, in line with the Maternity "
              "Benefit Act, 1961. For a third or subsequent child the entitlement is 12 weeks."),
            P("Male employees are entitled to 5 working days of paid paternity leave, to be availed within 3 "
              "months of the birth of the child. Employees adopting a child below the age of 3 months are "
              "entitled to 12 weeks of adoption leave."),
            H1("9. Bereavement Leave"),
            P("In the unfortunate event of the death of an immediate family member, employees may take 3 days of "
              "paid bereavement leave. Immediate family includes spouse, children, parents, parents-in-law and "
              "siblings."),
            H1("10. Work From Home"),
            P("Employees whose role permits remote working may work from home for up to 2 days per week with prior "
              "approval from their reporting manager. Requests must be raised in NimbusHR at least one working "
              "day in advance. During work-from-home days employees must be reachable during core hours of "
              "11:00 AM to 4:00 PM IST."),
            H1("11. Leave Without Pay"),
            P("Leave without pay may be granted for a maximum of 30 days in a leave year with the approval of the "
              "HR Business Partner, after all paid leave balances are exhausted."),
        ],
        [
            H1("12. Sabbatical"),
            P("Employees who have completed 5 years of continuous service may apply for an unpaid sabbatical of up "
              "to 3 months for higher education, research or personal development. Sabbaticals may be availed "
              "only once in every 5-year block, and the employee's role is held open during the sabbatical."),
            H1("13. Applying for Leave"),
            P("Planned leave of more than 3 days must be applied for at least 7 calendar days in advance through "
              "the NimbusHR portal. Managers are expected to approve or decline requests within 2 working days. "
              "Unplanned absences must be informed to the manager by 10:00 AM on the day of absence and "
              "regularised in the portal within 3 working days of returning to work."),
            H1("14. Public Holidays"),
            P("Public holidays are published each year in the company holiday calendar. Leave falling on a public "
              "holiday or a weekly off is not counted against the employee's leave balance."),
            H1("15. Grievances and Interpretation"),
            P("Questions on this policy may be addressed to people-ops@nimbustech.example. In case of any dispute "
              "on interpretation, the decision of the Head - People Operations is final. This policy will be "
              "reviewed annually by the Board HR Committee."),
        ],
    ])

doc("HR_Leave_Policy_2026.pdf", "hr", "Employee Leave Policy 2026 (POL-HR-017)",
    "Current 2026 leave policy superseding POL-HR-011, with higher entitlements and new leave types.",
    pages=[
        [
            H1("1. Document Control"),
            TABLE(["Field", "Detail"], ["Policy ID", "POL-HR-017"], ["Version", "4.0"],
                  ["Effective date", "1 January 2026"], ["Supersedes", "POL-HR-011 (Leave Policy 2025)"],
                  ["Policy owner", "Kavitha Menon, Head - People Operations"],
                  ["Approved by", "Board HR Committee on 18 November 2025"],
                  ["Next review", "November 2026"]),
            H1("2. Purpose"), P(_LEAVE_INTRO),
            P("This revision follows the 2025 employee engagement survey, in which flexibility and time off were "
              "the two most requested improvements. It enhances several existing entitlements, introduces two new "
              "leave types and withdraws the sabbatical scheme."),
            H1("3. Scope and Applicability"), P(_LEAVE_SCOPE),
            H1("4. Leave Year"),
            P("The leave year runs from 1 January to 31 December. Employees who join part-way through the year "
              "receive a pro-rated entitlement. All balances are maintained in the NimbusHR portal."),
        ],
        [
            H1("5. Annual Leave"),
            P("Every confirmed employee is entitled to 20 days of paid annual leave in each leave year. Annual "
              "leave accrues at the rate of 1.67 days for every completed month of service. Employees on "
              "probation may avail up to 5 days of accrued annual leave before confirmation."),
            P("A maximum of 12 days of unused annual leave may be carried forward into the next leave year; any "
              "balance above 12 days lapses on 31 December. Employees may encash up to 6 days of unused annual "
              "leave each year, calculated on basic salary and paid in the December payroll."),
            H1("6. Sick Leave"),
            P("Employees receive 12 days of paid sick leave per leave year, credited on 1 January. A medical "
              "certificate from a registered medical practitioner is required only for absences of more than 3 "
              "consecutive days. Unused sick leave cannot be carried forward or encashed."),
            H1("7. Casual Leave"),
            P("Employees receive 7 days of casual leave per year. Casual leave may not exceed 3 consecutive days "
              "and cannot be combined with annual leave."),
        ],
        [
            H1("8. Parental Leave"),
            P("Female employees are entitled to 26 weeks of paid maternity leave for up to two children, of which "
              "not more than 8 weeks may precede the expected date of delivery. For a third or subsequent child "
              "the entitlement is 12 weeks."),
            P("Male employees are entitled to 10 working days of paid paternity leave, which may be availed in up "
              "to two blocks within 6 months of the birth of the child. Employees adopting a child below the age "
              "of 3 months are entitled to 12 weeks of adoption leave."),
            H1("9. Bereavement Leave"),
            P("Employees may take 5 days of paid bereavement leave on the death of an immediate family member, "
              "including spouse, children, parents, parents-in-law, siblings and grandparents."),
            H1("10. Work From Home"),
            P("Employees whose role permits remote working may work from home for up to 3 days per week with prior "
              "approval from their reporting manager. Detailed equipment and connectivity rules are set out in "
              "the Remote Work Policy (POL-HR-019). Employees must be reachable during core hours of 11:00 AM to "
              "4:00 PM IST."),
            H1("11. Leave Without Pay"),
            P("Leave without pay may be granted for a maximum of 30 days in a leave year with the approval of the "
              "HR Business Partner, after all paid leave balances are exhausted."),
        ],
        [
            H1("12. Menstrual Wellness Leave (new)"),
            P("Women employees may avail 1 day of paid menstrual wellness leave per month, up to 12 days in a "
              "leave year. No medical certificate or reason is required and the leave is recorded confidentially."),
            H1("13. Caregiver Leave (new)"),
            P("Employees may take up to 5 days of paid caregiver leave per year to care for a dependent parent, "
              "spouse or child who is hospitalised or recovering from surgery."),
            H1("14. Withdrawal of Sabbatical"),
            P("The unpaid sabbatical scheme is withdrawn with effect from 1 January 2026. Sabbaticals already "
              "approved before 30 November 2025 will be honoured."),
            H1("15. Applying for Leave"),
            P("Planned leave of more than 3 days must be applied for at least 5 calendar days in advance through "
              "NimbusHR. Managers must approve or decline within 2 working days, failing which the request is "
              "auto-approved. Unplanned absences must be informed to the manager by 10:00 AM."),
            H1("16. Grievances and Interpretation"),
            P("Questions may be addressed to people-ops@nimbustech.example. The decision of the Head - People "
              "Operations on interpretation is final."),
        ],
    ])

doc("Travel_Reimbursement_Policy.docx", "hr", "Domestic & International Travel Reimbursement Policy (POL-HR-022)",
    "Per diem, hotel caps, mileage rates, advances and claim deadlines for business travel.",
    blocks=[
        H1("1. Overview"),
        P("Policy POL-HR-022 governs how employees of Nimbus Technologies Pvt. Ltd. book, undertake and claim "
          "reimbursement for business travel. It applies to all travel undertaken on company business, whether "
          "to customer sites, partner offices or industry events. Version 2.1 of the policy is effective from "
          "1 April 2026 and is owned by the Finance Controller, Mr. Rajiv Bhandari."),
        P("Employees are expected to spend company money as carefully as they would their own. Travel should be "
          "booked through the approved travel desk, TravelNest, at least 7 days in advance for domestic trips "
          "and 21 days in advance for international trips, unless an urgent customer escalation requires "
          "otherwise."),
        H1("2. Approvals"),
        UL("Domestic travel requires a travel requisition (TR form) approved by the reporting manager.",
           "International travel requires a TR form approved by the department head and the Finance Controller "
           "at least 10 days before departure.",
           "Travel that is billable to a customer must quote the customer project code on the TR form."),
        H1("3. Mode of Travel"),
        P("Air travel is permitted in economy class for all flights shorter than 4 hours. Employees in Band L7 "
          "and above may travel in business class on international flights longer than 6 hours. Train travel "
          "is reimbursed at AC 2-tier for Bands L1 to L4 and AC 1st class for Band L5 and above."),
        P("Employees using their own vehicle for official travel are reimbursed at ₹12 per kilometre for a car "
          "and ₹6 per kilometre for a two-wheeler, based on the distance recorded in the trip log. Tolls and "
          "parking are reimbursed at actuals against receipts."),
        H1("4. Per Diem and Hotel Limits"),
        P("A daily allowance (per diem) covers meals, laundry and incidental expenses. Hotel stays are "
          "reimbursed at actuals up to the cap shown below, inclusive of taxes. Tier-1 cities are Mumbai, "
          "Delhi NCR, Bengaluru, Chennai, Hyderabad, Kolkata and Pune."),
        TABLE(["Band", "Per diem - Tier-1", "Per diem - other cities", "Hotel cap - Tier-1", "Hotel cap - other cities"],
              ["L1 - L3", "₹3,500", "₹2,500", "₹6,000", "₹4,500"],
              ["L4 - L6", "₹5,000", "₹3,500", "₹9,000", "₹6,500"],
              ["L7 and above", "₹7,500", "₹5,000", "₹14,000", "₹10,000"]),
        P("For international travel, per diem is paid at USD 75 per day for Bands L1 to L6 and USD 110 per day "
          "for Band L7 and above. Local conveyance within a city is capped at ₹1,200 per day; app-based cabs "
          "are preferred over self-arranged taxis."),
        H1("5. Travel Advances"),
        P("Employees may request a travel advance of up to 75% of the estimated trip cost. Advances must be "
          "settled within 15 days of returning; unsettled advances are recovered from the next salary."),
        H1("6. Submitting Claims"),
        P("All claims must be submitted in the NimbusHR Expense module within 30 days of trip completion, with "
          "original or digital receipts for every expense above ₹500. Claims submitted after 30 days require "
          "the department head's approval, and claims submitted more than 60 days after the trip will be "
          "rejected. Approved claims are paid in the next weekly payment run, every Friday."),
        H1("7. Non-reimbursable Expenses"),
        UL("Alcohol, tobacco and personal entertainment, including in-room movies.",
           "Traffic fines, penalties and late check-out charges caused by personal choices.",
           "Upgrades to a higher class of travel or hotel without written pre-approval.",
           "Expenses of family members accompanying the employee."),
        H1("8. Policy Violations"),
        P("Falsified or inflated claims are treated as misconduct under the Code of Conduct and may lead to "
          "disciplinary action, including termination of employment and recovery of the amount involved."),
    ])

doc("Code_of_Conduct_and_POSH.md", "hr", "Code of Conduct and POSH Policy (POL-HR-005)",
    "Ethics rules on gifts, conflicts of interest, whistleblowing and prevention of sexual harassment (Internal Committee).",
    blocks=[
        H1("1. Introduction"),
        P("The Code of Conduct (policy POL-HR-005, version 5.0, effective 1 February 2026) describes the "
          "standards of behaviour that Nimbus Technologies Pvt. Ltd. expects of every employee, director, "
          "intern and contractor. It also incorporates the company's policy on the Prevention of Sexual "
          "Harassment at the workplace, framed under the Sexual Harassment of Women at Workplace (Prevention, "
          "Prohibition and Redressal) Act, 2013. Every employee must read and electronically acknowledge this "
          "Code within 15 days of joining and again every year."),
        H1("2. Integrity and Fair Dealing"),
        P("Employees must deal honestly with customers, suppliers, competitors and colleagues. Confidential "
          "information belonging to customers must only be used for the purpose for which it was shared. "
          "Company assets, including laptops, software licences and customer data, must be used only for "
          "legitimate business purposes."),
        H1("3. Gifts and Hospitality"),
        P("Employees may accept gifts or hospitality from business partners only if the value does not exceed "
          "₹2,000 per occasion and the gift is not cash or a cash equivalent such as vouchers. Any gift above "
          "₹2,000 must be declared to the Ethics Office at ethics@nimbustech.example within 5 working days and "
          "will either be returned or donated to charity. Gifts must never be solicited, and no gift of any "
          "value may be accepted from a vendor during an active tender."),
        H1("4. Conflicts of Interest"),
        UL("Employees must disclose any financial interest in a customer, supplier or competitor.",
           "Relatives may not be placed in a direct reporting line.",
           "Outside employment or paid directorships need prior written approval from the Head - People Operations.",
           "An annual conflict-of-interest declaration must be submitted in NimbusHR by 30 April each year."),
        H1("5. Speak-Up and Whistleblower Protection"),
        P("Concerns about fraud, bribery, data misuse or any breach of this Code may be raised with a manager, "
          "the Ethics Office, or anonymously through the independent Speak-Up hotline on 1800-425-7788, "
          "available 24 hours a day in English, Hindi and Kannada. Retaliation against anyone who raises a "
          "concern in good faith is itself a serious violation of the Code."),
        H1("6. Prevention of Sexual Harassment (POSH)"),
        P("Nimbus has zero tolerance for sexual harassment. Unwelcome physical contact, sexually coloured "
          "remarks, showing pornography, demands for sexual favours and any other unwelcome conduct of a sexual "
          "nature, whether in the office, at off-sites, on business travel or in online channels, are prohibited."),
        H2("6.1 Internal Committee"),
        P("The Internal Committee (IC) has 4 members. It is chaired by the Presiding Officer, Dr. Meera "
          "Krishnan, Director - Engineering, and includes an external member from the Sakhi Suraksha Foundation, "
          "a non-governmental organisation working on women's rights. At least half the members of the IC are women."),
        H2("6.2 Complaint and Inquiry Process"),
        P("A written complaint may be submitted to the IC at ic@nimbustech.example within 3 months of the incident, "
          "extendable by a further 3 months for valid reasons. The IC will offer conciliation if the complainant "
          "requests it, and will otherwise complete its inquiry within 90 days of receiving the complaint. The "
          "IC's report and recommendations are submitted to management within 10 days of completing the "
          "inquiry, and management must act on them within 60 days."),
        H2("6.3 Awareness"),
        P("POSH awareness training is mandatory for all employees every year and must be completed by 31 July. "
          "IC members receive an additional annual workshop conducted by an external expert."),
        H1("7. Consequences of Violation"),
        P("Violations of the Code may result in counselling, a written warning, suspension, withholding of "
          "increment, or termination of employment, depending on severity. Where a violation is also a criminal "
          "offence, the company will cooperate fully with law enforcement authorities."),
    ])

doc("Employee_Onboarding_Guide.html", "hr", "New Employee Onboarding Guide 2026",
    "Day-one logistics, first-week schedule, probation, mandatory trainings and documentation for new joiners.",
    blocks=[
        H1("Welcome to Nimbus"),
        P("Welcome to Nimbus Technologies Pvt. Ltd. This guide walks you through everything that happens between "
          "accepting your offer and completing your first 90 days. Your onboarding is coordinated by the People "
          "Operations team through NimbusStart, our onboarding portal, where you will find your checklist, "
          "documents to upload and the contact details of your onboarding buddy."),
        H1("Before Day One"),
        UL("Upload your PAN, Aadhaar, previous employer relieving letter and the last three salary slips to NimbusStart.",
           "Complete the background verification consent form; verification is carried out by VeriTrust Screening "
           "and is normally completed within 15 days.",
           "Share your bank account details for salary credit and your existing Universal Account Number (UAN) for "
           "Provident Fund transfer.",
           "Choose your laptop keyboard layout and preferred operating system (Windows or Ubuntu) in the IT request form."),
        H1("Your First Day"),
        P("Please report at 9:30 AM to the Tower B reception, Lakeview Tech Park, Outer Ring Road, Bellandur, "
          "Bengaluru 560103. Carry one original photo identity document. Your temporary access card will be "
          "issued at reception, and your permanent photo ID card will be ready within 2 working days. The IT "
          "service desk will hand over a Dell Latitude 7440 laptop pre-configured with disk encryption, the "
          "endpoint protection agent and the corporate VPN client."),
        H1("First-Week Schedule"),
        TABLE(["Day", "Time", "Session", "Owner"],
              ["Monday", "9:30 AM - 1:00 PM", "Welcome, documentation and laptop handover", "People Operations & IT"],
              ["Monday", "2:30 PM - 4:00 PM", "Company story, values and org structure", "Kavitha Menon"],
              ["Tuesday", "10:00 AM - 12:00 PM", "Information Security induction", "IT Security team"],
              ["Wednesday", "10:00 AM - 11:30 AM", "Code of Conduct and POSH awareness", "Internal Committee"],
              ["Thursday", "All day", "Team immersion with your manager and buddy", "Reporting manager"],
              ["Friday", "4:00 PM - 5:00 PM", "Week-one feedback circle", "HR Business Partner"]),
        H1("Mandatory Trainings"),
        P("Three e-learning modules must be completed within your first 30 days: Information Security Essentials, "
          "Prevention of Sexual Harassment (POSH), and the Code of Conduct. Completion is tracked in NimbusLearn, "
          "and access to production systems is granted only after the Information Security module is passed with "
          "a score of at least 80%."),
        H1("Your Onboarding Buddy"),
        P("Every new joiner is paired with a buddy from a neighbouring team who has been with Nimbus for at least "
          "one year. Your buddy will meet you on Day 1, take you to lunch in the first week, and check in "
          "fortnightly for the first three months. Buddies are recognised with a ₹3,000 gift voucher for each "
          "successful onboarding."),
        H1("Probation and Confirmation"),
        P("All new employees serve a probation period of 6 months. A 30-60-90 day plan is agreed with your manager "
          "during the first week, and a formal probation review is held at the end of month 5. On successful "
          "review you will receive a confirmation letter; probation may be extended once by up to 3 months. The "
          "notice period during probation is 15 days, rising to 60 days after confirmation."),
        H1("Payroll and Benefits Enrolment"),
        P("Salaries are credited on the last working day of each month. Employees who join after the 20th of a "
          "month receive their first salary along with the following month's payroll. Enrol yourself and your "
          "dependents in the group health insurance plan within 30 days of joining in NimbusHR; dependents "
          "cannot be added mid-year after this window closes, except on marriage or childbirth."),
        H1("Who to Contact"),
        UL("Onboarding queries: onboarding@nimbustech.example",
           "IT service desk: extension 4000 or itdesk@nimbustech.example",
           "Facilities and access cards: extension 4040",
           "Payroll: payroll@nimbustech.example"),
    ])

doc("Performance_Review_Process.txt", "hr", "Annual Performance Review Process (POL-HR-031)",
    "Review cycle timelines, rating scale, salary increment bands, calibration and performance improvement plans.",
    blocks=[
        H1("1. Purpose"),
        P("Policy POL-HR-031 describes how Nimbus Technologies Pvt. Ltd. sets goals, reviews performance and "
          "links outcomes to pay. The process is designed to be transparent, evidence-based and fair, and to "
          "give every employee at least two structured conversations about their growth every year."),
        H1("2. Review Cycle"),
        P("The performance year runs from 1 April to 31 March. Goals (OKRs) for the year are set in NimbusHR by "
          "30 April. A mid-year check-in is held in October, during which goals may be revised if business "
          "priorities have changed. The annual review takes place in April of the following year."),
        UL("Self-appraisal window: 1 April to 15 April.",
           "Manager assessment: 16 April to 30 April.",
           "Calibration committee meetings: first two weeks of May.",
           "Rating communication and increment letters: by 15 June, effective from 1 July."),
        H1("3. 360-Degree Feedback"),
        P("Employees in Band L4 and above receive 360-degree feedback from a minimum of 4 reviewers, including at "
          "least one peer from another department and, for people managers, at least two direct reports. "
          "Feedback is anonymised before it is shared with the employee."),
        H1("4. Rating Scale"),
        TABLE(["Rating", "Label", "Indicative distribution"],
              ["5", "Exceptional", "Up to 15% of employees"],
              ["4", "Exceeds Expectations", "About 25%"],
              ["3", "Meets Expectations", "About 50%"],
              ["2", "Partially Meets Expectations", "About 8%"],
              ["1", "Does Not Meet Expectations", "About 2%"]),
        H1("5. Link to Compensation"),
        P("Annual salary increments are determined by the final calibrated rating and the employee's position "
          "within the salary band. An employee rated 5 (Exceptional) receives an increment of between 12% and "
          "15%. An employee rated 4 receives between 8% and 10%. An employee rated 3 receives between 5% and 7%. "
          "Employees rated 2 receive a cost-of-living adjustment of 3%, and employees rated 1 are not eligible "
          "for an increment. Employees rated 5 in two consecutive cycles are automatically nominated for the "
          "promotion committee."),
        P("The annual performance bonus is paid in July. The bonus multiplier is 1.5x of target for rating 5, "
          "1.2x for rating 4, 1.0x for rating 3 and zero for ratings 1 and 2."),
        H1("6. Calibration"),
        P("Calibration committees are chaired by the department head and include the HR Business Partner and at "
          "least two managers from other teams. The committee compares evidence across teams to ensure that "
          "ratings mean the same thing everywhere in the company and that the distribution guidance is "
          "respected."),
        H1("7. Performance Improvement Plan"),
        P("Employees rated 1, or rated 2 in two consecutive cycles, are placed on a Performance Improvement Plan "
          "(PIP). A PIP lasts 60 days and sets out no more than five specific, measurable objectives. The "
          "employee meets the manager and HR Business Partner every two weeks during the PIP. At the end of the "
          "60 days the PIP is closed as successful, extended once by 30 days, or the employee may be separated "
          "with notice in accordance with the employment contract."),
        H1("8. Appeals"),
        P("An employee who disagrees with their final rating may file an appeal in NimbusHR within 10 working "
          "days of the rating being communicated. Appeals are reviewed by a panel consisting of the skip-level "
          "manager and a senior HR leader, and a decision is communicated within 21 days."),
    ])

doc("Remote_Work_Policy.docx", "hr", "Remote and Hybrid Work Policy (POL-HR-019)",
    "Eligibility, allowances, equipment, security and work-from-abroad rules for hybrid and remote work.",
    blocks=[
        H1("1. Purpose and Principles"),
        P("Nimbus Technologies Pvt. Ltd. operates a hybrid model in which teams combine focused remote work with "
          "regular in-person collaboration. Policy POL-HR-019 (version 2.0, effective 1 January 2026) sets out "
          "who can work remotely, what support the company provides, and the security rules that apply outside "
          "the office. The number of remote days permitted per week is governed by the Employee Leave Policy "
          "2026 (POL-HR-017)."),
        H1("2. Eligibility"),
        UL("Employees become eligible for hybrid work after completing their probation period.",
           "Roles that require physical presence, such as facilities, lab and front-desk roles, are not eligible.",
           "Employees on a Performance Improvement Plan work from the office for the duration of the plan.",
           "Team anchor days, when everyone attends the office, are set by each department head and are mandatory."),
        H1("3. Allowances"),
        P("Eligible employees receive a monthly internet allowance of ₹1,500, paid through payroll and requiring "
          "no bills. A one-time home-office setup grant of ₹15,000 is available to buy an ergonomic chair, desk "
          "or lighting; the grant can be claimed once every 3 years against invoices submitted in the NimbusHR "
          "Expense module. Employees working remotely for more than 15 days a month also receive a ₹500 monthly "
          "electricity allowance."),
        H1("4. Equipment Provided"),
        TABLE(["Item", "Entitlement", "Ownership"],
              ["Laptop", "Dell Latitude 7440 (standard) or MacBook Pro for design roles", "Company asset"],
              ["External monitor", "One 24-inch monitor on request", "Company asset"],
              ["Headset", "Noise-cancelling USB headset", "Company asset"],
              ["Ergonomic chair / desk", "Purchased from the ₹15,000 setup grant", "Employee-owned"],
              ["Mobile data backup", "4G dongle for employees in areas with frequent outages", "Company asset"]),
        H1("5. Information Security at Home"),
        P("All access to company systems must go through the NimbusSecure VPN with multi-factor authentication. "
          "Customer data may not be downloaded to personal devices, printed at home, or discussed in public "
          "places. Home Wi-Fi networks must use WPA2 or WPA3 encryption with a non-default password. Laptops "
          "must be locked whenever unattended, and screens must not be visible to other household members "
          "during customer calls."),
        H1("5.1 Working Hours"),
        P("Remote employees must be available during the core collaboration hours of 11:00 AM to 4:00 PM IST and "
          "must keep their status in the team chat tool up to date. Meetings should not be scheduled after "
          "7:00 PM IST except for customers in other time zones."),
        H1("6. Working From Outside India"),
        P("Employees may work from outside India for a maximum of 30 days in a calendar year, subject to written "
          "approval from the department head, the Legal team and the Finance Controller, so that tax and "
          "immigration implications can be assessed. Working from a country under international sanctions is "
          "never permitted."),
        H1("7. Health and Safety"),
        P("Employees are responsible for ensuring that their home workspace is safe. Work-related injuries at "
          "home must be reported to People Operations within 48 hours. The Employee Assistance Programme is "
          "available to remote employees in the same way as office-based employees."),
        H1("8. Review"),
        P("Managers may withdraw hybrid working for an individual if performance or availability concerns arise, "
          "after a documented conversation. The policy owner, Kavitha Menon, reviews the policy each December."),
    ])

# ----------------------------- HR tabular ---------------------------------- #
_EMPLOYEES = [
    ("Aarav Sharma", "Engineering", "Software Engineer", "Bengaluru"),
    ("Sneha Kulkarni", "Customer Success", "Customer Success Manager", "Bengaluru"),
    ("Vikram Sethi", "Engineering", "Engineering Manager", "Bengaluru"),
    ("Priya Raghavan", "People Operations", "HR Business Partner", "Bengaluru"),
    ("Mohammed Irfan", "Finance", "Accounts Executive", "Bengaluru"),
    ("Deepak Venkatesh", "Finance", "Tax & Compliance Lead", "Bengaluru"),
    ("Ritu Agarwal", "Legal", "Data Protection Officer", "Bengaluru"),
    ("Arjun Bhatt", "Leadership", "Chief Technology Officer", "Bengaluru"),
    ("Kavitha Menon", "People Operations", "Head - People Operations", "Bengaluru"),
    ("Rajiv Bhandari", "Finance", "Finance Controller", "Bengaluru"),
    ("Neha Joshi", "Product", "Product Manager", "Pune"),
    ("Harini Venkatesh", "Cloud Operations", "Cloud Engineer", "Bengaluru"),
    ("Suresh Pillai", "Sales", "Regional Sales Head", "Hyderabad"),
    ("Ananya Iyer", "Data Science", "Senior Data Scientist", "Bengaluru"),
    ("Rohit Deshmukh", "Cloud Operations", "DevOps Engineer", "Pune"),
    ("Fatima Sheikh", "Engineering", "QA Engineer", "Pune"),
    ("Gaurav Malhotra", "Sales", "Account Executive", "Hyderabad"),
    ("Lakshmi Prasad", "Customer Success", "Support Engineer", "Bengaluru"),
    ("Karthik Subramanian", "Engineering", "Senior Software Engineer", "Bengaluru"),
    ("Divya Nair", "Marketing", "Marketing Manager", "Bengaluru"),
    ("Harish Venkataraman", "Cloud Operations", "Senior Cloud Architect", "Bengaluru"),
    ("Pooja Reddy", "Engineering", "Frontend Engineer", "Hyderabad"),
    ("Sanjay Kumar Das", "IT", "IT Security Analyst", "Bengaluru"),
    ("Meera Krishnan", "Engineering", "Director - Engineering", "Bengaluru"),
    ("Nikhil Agarwal", "Product", "UX Designer", "Pune"),
    ("Shalini Gupta", "Finance", "Financial Analyst", "Bengaluru"),
    ("Abhishek Rao", "IT", "IT Support Engineer", "Bengaluru"),
    ("Tanvi Mehta", "Legal", "Legal Counsel", "Bengaluru"),
    ("Varun Chandra", "Data Science", "ML Engineer", "Bengaluru"),
    ("Isha Banerjee", "Marketing", "Content Strategist", "Pune"),
]
_DEPT_MANAGER = {"Engineering": "EMP-2026-00424", "Customer Success": "EMP-2026-00408",
                 "People Operations": "EMP-2026-00408", "Finance": "EMP-2026-00410",
                 "Legal": "EMP-2026-00410", "Leadership": "-", "Product": "EMP-2026-00408",
                 "Cloud Operations": "EMP-2026-00421", "Sales": "EMP-2026-00408",
                 "Data Science": "EMP-2026-00403", "Marketing": "EMP-2026-00408", "IT": "EMP-2026-00403"}


def _emp_id(i):
    return f"EMP-2026-{401 + i:05d}"


def _directory_rows():
    rows = [["Employee ID", "Full Name", "Department", "Designation", "Location", "Date of Joining",
             "Work Email", "Extension", "Manager ID"]]
    for i, (name, dept, desig, loc) in enumerate(_EMPLOYEES):
        doj = dt.date(2016 + (i * 3) % 10, (i * 5) % 12 + 1, (i * 7) % 27 + 1)
        # Keep joining dates consistent with the two resumes in the "general" domain.
        doj = {"Ananya Iyer": dt.date(2022, 8, 1), "Rohit Deshmukh": dt.date(2023, 3, 6)}.get(name, doj)
        email = ".".join(name.lower().split()[::len(name.split()) - 1]) + "@nimbustech.example"
        mgr = _DEPT_MANAGER[dept]
        if mgr == _emp_id(i):
            mgr = "EMP-2026-00408"
        rows.append([_emp_id(i), name, dept, desig, loc, doj.isoformat(), email, str(4100 + i * 7), mgr])
    return rows


doc("Employee_Directory.csv", "hr", "Employee Directory 2026",
    "Directory of 30 employees with IDs (EMP-2026-004xx), department, designation, location, joining date and extension.",
    rows=_directory_rows())


def _holiday_rows(items):
    rows = [["Date", "Day", "Holiday", "Applicable Locations"]]
    for (y, m, d), name, locs in items:
        day = dt.date(y, m, d)
        rows.append([day.strftime("%d-%b-%Y"), day.strftime("%A"), name, locs])
    return rows


doc("Holiday_Calendar_2026.xlsx", "hr", "Holiday Calendar 2026",
    "2026 mandatory public holidays by location and the list of optional (restricted) holidays.",
    sheets={
        "Mandatory Holidays": _holiday_rows([
            ((2026, 1, 1), "New Year's Day", "All offices"),
            ((2026, 1, 15), "Makara Sankranti / Pongal", "Bengaluru, Hyderabad"),
            ((2026, 1, 26), "Republic Day", "All offices"),
            ((2026, 3, 19), "Ugadi / Gudi Padwa", "All offices"),
            ((2026, 4, 3), "Good Friday", "All offices"),
            ((2026, 5, 1), "May Day / Maharashtra Day", "All offices"),
            ((2026, 8, 15), "Independence Day", "All offices"),
            ((2026, 9, 14), "Ganesh Chaturthi", "All offices"),
            ((2026, 10, 2), "Gandhi Jayanti", "All offices"),
            ((2026, 10, 20), "Vijayadashami (Dussehra)", "All offices"),
            ((2026, 11, 9), "Deepavali", "All offices"),
            ((2026, 11, 10), "Balipadyami", "Bengaluru"),
            ((2026, 12, 25), "Christmas Day", "All offices"),
        ]) + [["", "", "Total mandatory holidays: 13 (Bengaluru), 12 (other offices)", ""]],
        "Optional Holidays": _holiday_rows([
            ((2026, 2, 15), "Maha Shivaratri", "All offices"),
            ((2026, 3, 4), "Holi", "All offices"),
            ((2026, 3, 21), "Id-ul-Fitr (Ramzan Id)", "All offices"),
            ((2026, 3, 31), "Mahavir Jayanti", "All offices"),
            ((2026, 5, 27), "Bakrid / Id-ul-Zuha", "All offices"),
            ((2026, 8, 26), "Onam (Thiruvonam)", "All offices"),
            ((2026, 8, 28), "Raksha Bandhan", "All offices"),
            ((2026, 11, 24), "Guru Nanak Jayanti", "All offices"),
        ]) + [["", "", "Employees may choose any 2 optional holidays in a calendar year", ""]],
    })

doc("Employee_Benefits_2026.pptx", "hr", "Employee Benefits 2026",
    "Benefits overview deck: health insurance, life cover, wellness, retirement, learning and family benefits.",
    slides=[
        ("Employee Benefits 2026", "Nimbus Technologies Pvt. Ltd. | People Operations | Effective 1 April 2026"),
        ("Group Health Insurance", [
            "Family floater sum insured of ₹5,00,000 per year, fully paid by the company",
            "Covers employee, spouse and up to 2 children; no waiting period for pre-existing conditions",
            "Optional parental top-up cover at a premium of ₹9,800 per year for both parents, deducted from salary",
            "Maternity sub-limit of ₹75,000 for normal or caesarean delivery",
            "Cashless treatment at more than 6,500 network hospitals through CareLink TPA",
        ]),
        ("Life and Accident Cover", [
            "Group term life insurance of 3 times annual CTC, with no medical tests required",
            "Group personal accident cover of 5 times annual CTC, covering permanent disability",
            "Critical illness benefit of ₹10,00,000 lump sum on diagnosis of any of 32 listed illnesses",
            "Nominee details must be updated in NimbusHR within 30 days of joining",
        ]),
        ("Wellness and Mental Health", [
            "Fitness reimbursement of ₹1,000 per month for gym, yoga or sports club memberships",
            "Employee Assistance Programme through MindHaven: 6 free, confidential counselling sessions per year "
            "for each employee and their dependents",
            "Annual preventive health check-up for employees aged 30 and above, at partner diagnostic centres",
            "Quarterly wellness webinars on sleep, nutrition and financial wellbeing",
        ]),
        ("Retirement Benefits", [
            "Provident Fund contribution of 12% of basic salary by both employer and employee",
            "Gratuity payable after 5 years of continuous service as per the Payment of Gratuity Act",
            "Optional National Pension System (NPS) contribution of up to 10% of basic salary by the employer, "
            "tax-efficient under section 80CCD(2)",
        ]),
        ("Learning and Growth", [
            "Annual learning budget of ₹50,000 per employee for courses, conferences and books",
            "Professional certification fees reimbursed in full after the employee passes the exam",
            "2 paid learning days per year to attend external workshops",
            "Internal mentoring circles for women in technology, run every quarter",
        ]),
        ("Family and Lifestyle", [
            "Meal card of ₹2,200 per month, tax-exempt within statutory limits",
            "Crèche reimbursement of ₹4,000 per month per child below 6 years of age",
            "Festival advance of up to ₹25,000, recovered interest-free over 10 months",
            "Employee referral bonus of ₹40,000 for each successful hire in Band L4 and above",
        ]),
        ("How to Enrol", [
            "Benefits enrolment window: 1 April to 15 April 2026 on the NimbusHR portal",
            "New joiners must enrol dependents within 30 days of joining",
            "Mid-year changes are allowed only on marriage, childbirth or adoption",
            "Questions: benefits@nimbustech.example or the People Operations helpdesk at extension 4050",
            "Benefit statements showing the total value of your benefits are published in NimbusHR every May",
        ]),
    ])

# =========================================================================== #
#                                 LEGAL (10)                                  #
# =========================================================================== #
def _msa_blocks(v):
    blocks = [
        H1("Parties and Recitals"),
        P(f"This {v['kind']} (the \"Agreement\"), contract reference {v['ref']}, is entered into on "
          f"{v['date']} between Nimbus Technologies Pvt. Ltd., a company incorporated under the Companies Act, "
          "2013 with CIN U72900KA2015PTC081234 and its registered office at Tower B, Lakeview Tech Park, Outer "
          "Ring Road, Bellandur, Bengaluru 560103 (the \"Service Provider\"), and Orchid Retail Ventures Pvt. "
          "Ltd., having its registered office at 22 Residency Road, Bengaluru 560025 (the \"Client\")."),
        P("The Client operates a chain of 140 lifestyle retail stores and wishes to engage the Service Provider "
          "for application support, cloud managed services and an IT service desk for its store and e-commerce "
          "systems. " + v["recital"]),
        H1("1. Definitions"),
        UL("\"Services\" means the services described in Schedule A and any Statement of Work signed under this Agreement.",
           "\"Service Levels\" means the performance standards set out in the Service Level Agreement SLA-2026-118.",
           "\"Confidential Information\" means all non-public business, technical and customer information "
           "disclosed by either party.",
           "\"Effective Date\" means " + v["effective"] + "."),
        H1("2. Term"),
        P(f"This Agreement commences on the Effective Date and continues for an initial term of {v['term']} "
          f"months, unless terminated earlier in accordance with Clause 11. {v['renewal']}"),
        H1("3. Scope of Services"),
        P("The Service Provider shall provide the Services from its delivery centres in Bengaluru and Pune using "
          "suitably qualified personnel. Key personnel, including the Engagement Manager, may not be replaced "
          "without 30 days' prior written notice to the Client, except in case of resignation or ill health."),
        H1("4. Fees"),
        P(f"In consideration for the Services the Client shall pay a fixed monthly fee of ₹{v['fee']} "
          "(exclusive of GST), made up of the components below. " + v["escalation"]),
        TABLE(*v["fee_table"]),
        H1("5. Invoicing and Payment"),
        P(f"The Service Provider shall invoice monthly in arrears on the last working day of each month. "
          f"Invoices are payable within {v['payment']} days of receipt. Undisputed amounts not paid by the due date "
          f"attract interest at {v['interest']} per month. Disputed amounts must be notified in writing within "
          "10 days of receipt of the invoice."),
        H1("6. Client Responsibilities"),
        P("The Client shall provide timely access to its systems, nominate a single point of contact, and ensure "
          "that third-party vendors cooperate with the Service Provider. Delays caused by the Client shall "
          "extend affected Service Levels proportionately."),
        H1("7. Confidentiality"),
        P("Each party shall protect the other's Confidential Information with at least the same degree of care "
          "it uses for its own, and in no case less than reasonable care. These obligations survive for 3 years "
          "after termination of this Agreement."),
        H1("8. Intellectual Property"),
        P("All deliverables created specifically for the Client vest in the Client upon full payment. The "
          "Service Provider retains ownership of its pre-existing tools, accelerators and the NimbusDesk "
          "platform, and grants the Client a non-exclusive licence to use them for the duration of the Agreement."),
        H1("9. Limitation of Liability"),
        P(f"Except for breach of confidentiality, data protection obligations or wilful misconduct, each party's "
          f"aggregate liability under this Agreement shall not exceed the fees paid in the {v['cap']} months "
          "preceding the claim. Neither party is liable for indirect or consequential losses, including loss of "
          "profit."),
    ]
    blocks += v["extra_clauses"]
    blocks += [
        H1("11. Termination"),
        P(f"Either party may terminate this Agreement for convenience by giving {v['notice']} days' prior written "
          "notice to the other party. Either party may terminate immediately by written notice if the other "
          "party commits a material breach that remains uncured 30 days after notice of the breach. On "
          "termination the Service Provider shall provide reasonable exit assistance for up to 90 days at the "
          "then-current rates."),
        H1("12. Governing Law and Dispute Resolution"),
        P("This Agreement is governed by the laws of India. Disputes shall first be escalated to the Chief "
          "Executive Officers of both parties for 15 days, and thereafter referred to arbitration by a sole "
          "arbitrator under the Arbitration and Conciliation Act, 1996. The seat and venue of arbitration shall "
          "be Bengaluru and the language English."),
        H1("Signatures"),
        P("Signed for Nimbus Technologies Pvt. Ltd. by Arjun Bhatt, Chief Technology Officer, and for Orchid "
          f"Retail Ventures Pvt. Ltd. by Rakesh Khandelwal, Chief Information Officer, on {v['date']}."),
    ]
    return blocks


doc("Master_Services_Agreement_v1.docx", "legal", "Master Services Agreement - Version 1 (CNT-2026-9941)",
    "Original MSA between Nimbus and Orchid Retail Ventures: 24-month term, ₹4,50,000 monthly fee, 90-day notice.",
    blocks=_msa_blocks(dict(
        kind="Master Services Agreement", ref="CNT-2026-9941", date="10 January 2026",
        effective="1 February 2026", term=24,
        recital="This is version 1 of the Agreement.",
        renewal="The Agreement may be renewed for a further term by mutual written agreement.",
        fee="4,50,000", escalation="The fees are fixed for the entire initial term.",
        fee_table=[["Service line", "Monthly fee (₹)"], ["Application support", "2,00,000"],
                   ["Cloud managed services", "1,50,000"], ["IT service desk (store helpdesk)", "1,00,000"],
                   ["Total", "4,50,000"]],
        payment=45, interest="1.5%", cap=12, notice=90,
        extra_clauses=[
            H1("10. Exclusivity"),
            P("During the initial term the Client shall not engage any other vendor to provide application support "
              "services for the systems covered by Schedule A without the Service Provider's prior written consent."),
        ])))

doc("Master_Services_Agreement_v2.docx", "legal", "Master Services Agreement - Version 2 (CNT-2026-9941, Amended and Restated)",
    "Amended and restated MSA: 36-month term, ₹5,10,000 monthly fee, 60-day notice, new security and data clauses.",
    blocks=_msa_blocks(dict(
        kind="Amended and Restated Master Services Agreement", ref="CNT-2026-9941 (Version 2)",
        date="15 June 2026", effective="1 July 2026", term=36,
        recital=("This version 2 amends and restates in full version 1 dated 10 January 2026, and adds security "
                 "monitoring services and data localisation commitments."),
        renewal="Thereafter the Agreement renews automatically for successive 12-month periods unless either "
                "party gives notice of non-renewal at least 90 days before expiry.",
        fee="5,10,000",
        escalation="The fees shall increase by 6% on each anniversary of the Effective Date.",
        fee_table=[["Service line", "Monthly fee (₹)"], ["Application support", "2,20,000"],
                   ["Cloud managed services", "1,65,000"], ["IT service desk (store helpdesk)", "1,00,000"],
                   ["24x7 security monitoring (new)", "25,000"], ["Total", "5,10,000"]],
        payment=30, interest="1%", cap=18, notice=60,
        extra_clauses=[
            H1("10. Data Localisation and Security (new)"),
            P("All Client personal data shall be stored and processed only in data centres located in India. The "
              "Service Provider shall maintain ISO/IEC 27001 certification throughout the term, and shall notify "
              "the Client of any security incident affecting Client data within 24 hours of becoming aware of it."),
            H2("10.1 Use of AI Tools (new)"),
            P("The Service Provider shall not input Client Confidential Information into any generative AI tool "
              "hosted outside the Service Provider's controlled environment without the Client's prior written approval."),
            H2("10.2 Removal of Exclusivity"),
            P("The exclusivity clause contained in version 1 is deleted. The Client may engage other vendors for "
              "application support at its discretion."),
        ])))

doc("Mutual_NDA_Zenvia.pdf", "legal", "Mutual Non-Disclosure Agreement (CNT-2026-9914)",
    "Mutual NDA between Nimbus Technologies and Zenvia Analytics LLP for a joint analytics product evaluation.",
    pages=[
        [
            H1("Parties"),
            P("This Mutual Non-Disclosure Agreement, contract reference CNT-2026-9914, is made on 3 February 2026 "
              "between Nimbus Technologies Pvt. Ltd., Tower B, Lakeview Tech Park, Bellandur, Bengaluru 560103, and "
              "Zenvia Analytics LLP, a limited liability partnership (LLPIN AAK-4417) with its office at 5th Floor, "
              "Riverside Business Bay, Baner, Pune 411045. Each party is referred to as a \"Party\" and, as the "
              "case may be, as the \"Disclosing Party\" or the \"Receiving Party\"."),
            H1("Purpose"),
            P("The Parties wish to explore a joint offering that combines the NimbusDesk service-management platform "
              "with Zenvia's retail demand-forecasting models (the \"Purpose\"). In the course of these discussions "
              "each Party may disclose Confidential Information to the other."),
            H1("1. Definition of Confidential Information"),
            P("\"Confidential Information\" means any information disclosed by a Party, whether orally, in writing "
              "or electronically, that is marked confidential or would reasonably be understood to be confidential, "
              "including source code, model weights, product roadmaps, pricing, customer lists, financial "
              "information and the terms of this Agreement."),
        ],
        [
            H1("2. Obligations of the Receiving Party"),
            UL("Use Confidential Information solely for the Purpose.",
               "Restrict disclosure to employees and advisers who need to know and are bound by written "
               "confidentiality obligations at least as protective as this Agreement.",
               "Protect Confidential Information using at least reasonable care, including encryption of data at rest.",
               "Promptly notify the Disclosing Party, and in any case within 72 hours, of any unauthorised disclosure."),
            H1("3. Exclusions"),
            P("Obligations do not apply to information that is or becomes public through no fault of the Receiving "
              "Party, was lawfully known to it before disclosure, is independently developed without use of the "
              "Confidential Information, or is required to be disclosed by law or court order, provided that the "
              "Receiving Party gives prompt notice to allow the Disclosing Party to seek protection."),
            H1("4. Term and Survival"),
            P("This Agreement remains in force for 2 years from the date of signing. The confidentiality obligations "
              "survive for 5 years after the expiry or termination of this Agreement; obligations relating to "
              "source code and trade secrets survive indefinitely."),
            H1("5. No Licence"),
            P("No licence or other right is granted under any patent, copyright or other intellectual property by "
              "disclosure of Confidential Information, other than the limited right to use it for the Purpose."),
        ],
        [
            H1("6. Return or Destruction"),
            P("On written request, or on termination, the Receiving Party shall return or destroy all Confidential "
              "Information within 15 days and confirm destruction in writing, except copies retained in automatic "
              "backups, which remain subject to this Agreement."),
            H1("7. Non-Solicitation"),
            P("For 12 months after the date of signing, neither Party shall solicit for employment any employee of "
              "the other Party who was directly involved in the Purpose, other than through general advertisements."),
            H1("8. Remedies"),
            P("Each Party acknowledges that a breach may cause irreparable harm for which damages are not an adequate "
              "remedy, and that the Disclosing Party is entitled to seek injunctive relief in addition to any other "
              "remedy."),
            H1("9. Governing Law"),
            P("This Agreement is governed by the laws of India, and the courts at Bengaluru, Karnataka shall have "
              "exclusive jurisdiction."),
            H1("Signatures"),
            P("For Nimbus Technologies Pvt. Ltd.: Arjun Bhatt, Chief Technology Officer. For Zenvia Analytics LLP: "
              "Farah Siddiqui, Designated Partner. Witnessed by Tanvi Mehta, Legal Counsel, Nimbus Technologies."),
        ],
    ])

doc("Service_Level_Agreement.html", "legal", "Service Level Agreement SLA-2026-118",
    "SLA schedule to MSA CNT-2026-9941: availability target, incident priorities, response/resolution times and service credits.",
    blocks=[
        H1("1. Scope"),
        P("This Service Level Agreement (SLA-2026-118) forms Schedule B to the Master Services Agreement "
          "CNT-2026-9941 between Nimbus Technologies Pvt. Ltd. and Orchid Retail Ventures Pvt. Ltd. It defines "
          "the service levels for the hosted store systems, the e-commerce order platform and the IT service "
          "desk, how performance is measured, and the service credits payable when targets are missed."),
        H1("2. Availability Commitment"),
        P("The Service Provider commits to a monthly availability of 99.9% for production systems, measured "
          "from synthetic transactions executed every minute from two independent locations. Availability is "
          "calculated as total minutes in the month minus minutes of unplanned downtime, divided by total minutes "
          "in the month. Planned maintenance is excluded."),
        H1("3. Maintenance Windows"),
        P("Planned maintenance is performed on Sundays between 01:00 and 05:00 IST. The Client must be notified at "
          "least 72 hours in advance. No planned maintenance may be scheduled during the Client's blackout periods: "
          "the 10 days before Deepavali and the period from 20 December to 2 January."),
        H1("4. Incident Priorities and Targets"),
        TABLE(["Priority", "Definition", "Response time", "Resolution target"],
              ["P1 - Critical", "Production down or more than 25 stores unable to bill", "15 minutes", "4 hours"],
              ["P2 - High", "Major function degraded, workaround not available", "30 minutes", "8 hours"],
              ["P3 - Medium", "Single store or non-critical function affected", "4 hours", "3 business days"],
              ["P4 - Low", "Cosmetic issues, questions and minor requests", "1 business day", "10 business days"]),
        P("Response time is measured from the creation of the ticket in NimbusDesk to the first meaningful human "
          "response. P1 incidents are supported 24x7; all other priorities are supported from 8:00 AM to 10:00 PM "
          "IST, seven days a week."),
        H1("5. Service Credits"),
        P("If monthly availability falls below the commitment, the Client is entitled to a service credit "
          "calculated as a percentage of the monthly fee for the affected month:"),
        TABLE(["Monthly availability", "Service credit"],
              ["99.0% to below 99.9%", "5% of monthly fee"],
              ["95.0% to below 99.0%", "10% of monthly fee"],
              ["Below 95.0%", "20% of monthly fee"]),
        P("Service credits are capped at 25% of the monthly fee in any month and are applied against the next "
          "invoice. Service credits are the Client's sole financial remedy for availability shortfalls, except "
          "where availability is below 95.0% for three consecutive months, in which case the Client may terminate "
          "the Agreement for cause without paying any exit fee."),
        H1("6. Reporting and Governance"),
        UL("A monthly service report is delivered by the 5th working day of the following month.",
           "A root-cause analysis is delivered within 5 business days of every P1 incident.",
           "Quarterly service reviews are held between the Engagement Manager and the Client CIO.",
           "Customer satisfaction (CSAT) on closed tickets must remain at or above 4.2 out of 5."),
        H1("7. Exclusions"),
        P("Service levels do not apply to downtime caused by force majeure events, Client-requested changes "
          "executed against the Service Provider's advice, failures of Client-owned network links in stores, or "
          "third-party payment gateway outages."),
    ])

doc("Data_Processing_Agreement.pdf", "legal", "Data Processing Agreement DPA-2026-031",
    "DPDP Act 2023 data processing agreement with Healthbridge Diagnostics: breach notification, sub-processors, retention.",
    pages=[
        [
            H1("1. Parties and Background"),
            P("This Data Processing Agreement (DPA-2026-031) is entered into on 2 March 2026 between Healthbridge "
              "Diagnostics Pvt. Ltd., Koramangala, Bengaluru (the \"Data Fiduciary\" or \"Controller\") and Nimbus "
              "Technologies Pvt. Ltd. (the \"Data Processor\"). Nimbus hosts and operates the NimbusDesk patient "
              "helpdesk and appointment-reminder platform for Healthbridge's 46 collection centres."),
            P("This DPA supplements the services agreement between the parties and sets out the obligations of the "
              "Data Processor under the Digital Personal Data Protection Act, 2023 (the \"DPDP Act\") and the rules "
              "made under it."),
            H1("2. Categories of Data and Data Principals"),
            UL("Data principals: patients, their caregivers and Healthbridge staff.",
               "Personal data: name, mobile number, email address, appointment details, test names and report "
               "delivery status.",
               "The Processor will not process test results or diagnostic images under this DPA."),
        ],
        [
            H1("3. Processor Obligations"),
            UL("Process personal data only on documented instructions of the Controller.",
               "Ensure that personnel with access are bound by confidentiality and complete annual privacy training.",
               "Encrypt personal data at rest using AES-256 and in transit using TLS 1.2 or higher.",
               "Assist the Controller in responding to data principal requests within 7 days of receiving them."),
            H1("4. Personal Data Breach"),
            P("The Processor shall notify the Controller of any personal data breach without undue delay and in any "
              "event within 24 hours of becoming aware of it. The notification shall describe the nature of the "
              "breach, the categories and approximate number of data principals affected, the likely consequences "
              "and the measures taken. The Processor shall support the Controller in notifying the Data "
              "Protection Board of India and affected data principals."),
            H1("5. Sub-processors"),
            P("The Controller authorises the following sub-processors: (a) the Processor's cloud hosting provider "
              "for the Mumbai (ap-south-1) region; and (b) an SMS gateway provider located in India. The Processor "
              "shall give 30 days' written notice of any new sub-processor, during which the Controller may object."),
            H1("6. Data Localisation"),
            P("All personal data shall be stored in India. No personal data may be transferred outside India "
              "without the Controller's prior written consent."),
        ],
        [
            H1("7. Audit Rights"),
            P("The Controller may audit the Processor's compliance once per year on 15 business days' notice, or at "
              "any time following a personal data breach. The Processor shall also provide its current ISO/IEC 27001 "
              "certificate and the latest independent penetration test summary on request."),
            H1("8. Retention and Deletion"),
            P("On termination of the services, the Processor shall, at the Controller's choice, return all personal "
              "data in CSV format or delete it within 30 days, and shall provide a certificate of deletion signed "
              "by its Data Protection Officer. Backups are purged within 90 days under the normal backup rotation."),
            H1("9. Liability"),
            P("The Processor's liability for breach of this DPA is capped at ₹2 crore per contract year, except in "
              "case of wilful misconduct or gross negligence."),
            H1("10. Contacts"),
            P("Data Protection Officer of the Processor: Ritu Agarwal, dpo@nimbustech.example. Grievance Officer of "
              "the Controller: Dr. Arvind Kamath, Healthbridge Diagnostics."),
        ],
    ])

doc("Software_License_Agreement.txt", "legal", "Software Licence Agreement LIC-2026-0457 (NimbusDesk Enterprise)",
    "Enterprise licence of NimbusDesk to Trident Logistics: named users, fees, support, escrow and warranty.",
    blocks=[
        H1("1. Parties"),
        P("This Software Licence Agreement, reference LIC-2026-0457, is made on 20 April 2026 between Nimbus "
          "Technologies Pvt. Ltd. (the \"Licensor\") and Trident Logistics Pvt. Ltd., Plot 18, MIDC Industrial "
          "Area, Bhiwandi, Maharashtra 421302 (the \"Licensee\"). This Agreement supersedes the evaluation licence "
          "LIC-2026-0475, which permitted 25 users for a 60-day trial that ended on 31 March 2026."),
        H1("2. Grant of Licence"),
        P("The Licensor grants the Licensee a non-exclusive, non-transferable licence to use NimbusDesk Enterprise "
          "version 5.x for its internal business operations for 250 named users. A named user is an individual "
          "employee or contractor of the Licensee who is assigned a unique login. Named user licences may be "
          "reassigned no more than once per quarter per user."),
        H1("3. Fees"),
        TABLE(["Item", "Amount"],
              ["Annual subscription for 250 named users", "₹18,75,000 per year"],
              ["Each additional named user", "₹7,500 per user per year"],
              ["One-time implementation and data migration", "₹3,85,000"],
              ["Premium 24x7 support add-on (optional)", "₹2,40,000 per year"]),
        P("Fees are payable annually in advance and are exclusive of GST. Fees are fixed for the first year and "
          "may thereafter be increased by up to 7% per year with 60 days' written notice."),
        H1("4. Term"),
        P("The licence term is 3 years from 1 May 2026. The Licensee may terminate at the end of any licence year "
          "by giving 90 days' notice, without penalty."),
        H1("5. Restrictions"),
        UL("The Licensee shall not reverse engineer, decompile or disassemble the software.",
           "The software may not be used to provide service-desk services to third parties.",
           "The Licensee shall not remove proprietary notices or circumvent licence controls."),
        H1("6. Support and Maintenance"),
        P("Standard support is provided from 9:00 AM to 6:00 PM IST, Monday to Friday, through the NimbusDesk "
          "customer portal and by email. Major upgrades and security patches are included in the annual "
          "subscription. Critical security patches are released within 7 days of a vulnerability being confirmed."),
        H1("7. Source Code Escrow"),
        P("The Licensor shall deposit the source code of the licensed version with EscrowSure India, an "
          "independent escrow agent, within 30 days of signing and update the deposit with every major release. "
          "The source code will be released to the Licensee if the Licensor becomes insolvent or ceases to "
          "support the product."),
        H1("8. Warranty"),
        P("The Licensor warrants that the software will perform materially in accordance with its documentation "
          "for 90 days from go-live. The Licensee's sole remedy for breach of this warranty is correction of the "
          "defect or, if correction is not possible, a refund of the fees paid for the defective module."),
        H1("9. Licence Audit"),
        P("The Licensor may verify the number of named users once per year using the built-in usage report. "
          "Excess usage will be invoiced at the additional-user rate, pro-rated for the remaining licence year."),
        H1("10. Governing Law"),
        P("This Agreement is governed by the laws of India. The courts at Bengaluru have exclusive jurisdiction."),
    ])

doc("Office_Lease_Deed_Whitefield.pdf", "legal", "Lease Deed - Whitefield Office Premises",
    "Registered lease deed for 12,500 sq ft office at Greenfield Enclave, Whitefield: rent, deposit, escalation and lock-in.",
    pages=[
        [
            H1("1. Parties"),
            P("This Lease Deed is executed at Bengaluru on 25 July 2026 between Mr. Suresh Narayan Rao, residing at "
              "No. 14, 3rd Cross, Indiranagar, Bengaluru 560038 (the \"Lessor\"), and Nimbus Technologies Pvt. Ltd., "
              "represented by its Finance Controller Mr. Rajiv Bhandari under a board resolution dated 10 July 2026 "
              "(the \"Lessee\")."),
            H1("2. Premises"),
            P("The Lessor leases to the Lessee the entire 3rd floor of the building known as Greenfield Enclave, "
              "ITPL Main Road, Whitefield, Bengaluru 560066, admeasuring 12,500 square feet of super built-up area, "
              "together with 25 covered car parking slots and 40 two-wheeler slots in the basement, and the right "
              "to use common areas, lifts and the power back-up system (the \"Premises\")."),
            H1("3. Term"),
            P("The lease is for a period of 9 years commencing on 1 October 2026 (the \"Commencement Date\"). The "
              "Lessee is granted a rent-free fit-out period of 60 days from the Commencement Date."),
        ],
        [
            H1("4. Rent"),
            P("The monthly rent is Rs. 11,25,000 (Rupees Eleven Lakh Twenty-Five Thousand only), calculated at "
              "Rs. 90 per square foot of super built-up area, payable in advance on or before the 7th day of each "
              "English calendar month, subject to deduction of tax at source."),
            H1("5. Escalation"),
            P("The rent shall be increased by 5% every year on the anniversary of the Commencement Date, compounded "
              "on the last paid rent."),
            H1("6. Security Deposit"),
            P("The Lessee has paid an interest-free refundable security deposit of Rs. 67,50,000, equal to 6 months' "
              "rent, by RTGS on 26 July 2026. The deposit shall be refunded within 30 days of the Lessee vacating the "
              "Premises, after deduction of any undisputed dues. Delay in refund attracts interest at 12% per annum."),
            H1("7. Lock-in Period"),
            P("The parties agree to a lock-in period of 36 months from the Commencement Date. If the Lessee "
              "terminates during the lock-in, it shall pay rent for the unexpired portion of the lock-in period."),
        ],
        [
            H1("8. Maintenance and Utilities"),
            P("Common area maintenance charges of Rs. 8 per square foot per month are payable to the building "
              "facility manager. Electricity is charged at actuals based on the separate meter for the Premises. "
              "The Lessor is responsible for structural repairs, and the Lessee for internal repairs."),
            H1("9. Use and Alterations"),
            P("The Premises shall be used only as an office for software development and allied services. The "
              "Lessee may carry out internal fit-outs without structural alteration, and may remove its fixtures "
              "at the end of the lease."),
            H1("10. Termination after Lock-in"),
            P("After the lock-in period, the Lessee may terminate by giving 6 months' written notice. The Lessor may "
              "terminate only if rent remains unpaid for more than 3 consecutive months after written reminder."),
            H1("11. Registration and Stamp Duty"),
            P("This deed shall be registered at the office of the Sub-Registrar, Varthur. Stamp duty and registration "
              "charges shall be borne by the Lessee."),
            H1("12. Signatures"),
            P("Signed by the Lessor, Mr. Suresh Narayan Rao, and by Mr. Rajiv Bhandari for the Lessee, in the presence "
              "of two witnesses."),
        ],
    ])

doc("Vendor_Contract_Facility_Services.docx", "legal", "Facility Services Vendor Contract (CNT-2026-9491)",
    "Housekeeping and security services contract with CleanSpark Facility Services: staffing, fees, penalties.",
    blocks=[
        H1("1. Parties and Effective Date"),
        P("This Facility Services Agreement, contract reference CNT-2026-9491, is entered into between Nimbus "
          "Technologies Pvt. Ltd. (the \"Company\") and CleanSpark Facility Services Pvt. Ltd., No. 88, Hosur Road, "
          "Bommanahalli, Bengaluru 560068 (the \"Vendor\", vendor code VND-1042). The Agreement takes effect on "
          "1 April 2026 and continues for 12 months."),
        H1("2. Scope of Services"),
        UL("Housekeeping of the Bellandur office (Tower B, 4 floors) including pantry and washrooms, from 7:00 AM to 10:00 PM.",
           "Manned security at two entry gates and the basement parking, 24 hours a day, 7 days a week.",
           "Pest control every month and deep cleaning of carpets every quarter.",
           "Mailroom and front-desk support during business hours."),
        H1("3. Deployment"),
        P("The Vendor shall deploy 28 personnel in total: 16 housekeeping staff, 10 security guards and 2 "
          "supervisors. All security guards must be licensed under the Private Security Agencies (Regulation) "
          "Act, 2005, and at least 2 guards per shift must be women."),
        H1("4. Fees"),
        P("The Company shall pay a monthly fee of ₹6,85,000 (exclusive of GST) for the services, covering wages, "
          "statutory contributions, uniforms, consumables and the Vendor's management fee."),
        TABLE(["Component", "Monthly amount (₹)"],
              ["Housekeeping staff (16)", "3,52,000"],
              ["Security guards (10)", "2,48,000"],
              ["Supervisors (2)", "55,000"],
              ["Consumables and pest control", "30,000"],
              ["Total", "6,85,000"]),
        P("Invoices are raised on the 1st of each month for the previous month and are payable within 21 days."),
        H1("5. Statutory Compliance"),
        P("The Vendor is solely responsible for paying at least the minimum wages notified by the Government of "
          "Karnataka, and for Provident Fund, ESI and bonus contributions for its personnel. The Vendor shall "
          "submit challans of PF and ESI payments every month along with its invoice; the Company may withhold "
          "payment until the challans are received."),
        H1("6. Service Levels and Penalties"),
        P("A penalty of ₹2,000 is deducted for every shift on which a deployed position is left vacant without a "
          "replacement. Housekeeping audits are conducted weekly, and an audit score below 85% for two "
          "consecutive weeks attracts a penalty of 2% of the monthly fee. Total penalties in a month are capped "
          "at 10% of the monthly fee."),
        H1("7. Termination"),
        P("Either party may terminate this Agreement by giving 30 days' written notice. The Company may terminate "
          "immediately in case of theft, misconduct by Vendor personnel, or non-payment of statutory dues."),
        H1("8. Indemnity and Insurance"),
        P("The Vendor shall indemnify the Company against claims by its personnel and shall maintain workmen's "
          "compensation insurance and public liability insurance of at least ₹50,00,000 throughout the term."),
        H1("9. Contacts"),
        P("Company: Facilities Manager, extension 4040. Vendor: Mr. Joseph D'Souza, Operations Head, CleanSpark."),
    ])

doc("Compliance_Checklist_2026.xlsx", "legal", "Statutory Compliance Checklist 2026",
    "Statutory compliance calendar (labour, tax, corporate, data protection) with owners, plus contract renewal tracker.",
    sheets={
        "Statutory Calendar": [
            ["Item ID", "Compliance Item", "Law / Form", "Frequency", "Due Date", "Owner", "Status"],
            ["CMP-01", "Provident Fund ECR filing and payment", "EPF Act / ECR", "Monthly", "15th of next month", "Mohammed Irfan", "On track"],
            ["CMP-02", "ESI contribution payment", "ESI Act", "Monthly", "15th of next month", "Mohammed Irfan", "On track"],
            ["CMP-03", "Professional tax remittance (Karnataka)", "KTPTCE Act", "Monthly", "20th of next month", "Mohammed Irfan", "On track"],
            ["CMP-04", "GSTR-1 outward supplies return", "CGST Act / GSTR-1", "Monthly", "11th of next month", "Deepak Venkatesh", "On track"],
            ["CMP-05", "GSTR-3B summary return and tax payment", "CGST Act / GSTR-3B", "Monthly", "20th of next month", "Deepak Venkatesh", "On track"],
            ["CMP-06", "TDS return on salaries (Q2)", "Income Tax Act / Form 24Q", "Quarterly", "31-Oct-2026", "Shalini Gupta", "In progress"],
            ["CMP-07", "TDS return on non-salary payments (Q2)", "Income Tax Act / Form 26Q", "Quarterly", "31-Oct-2026", "Shalini Gupta", "In progress"],
            ["CMP-08", "GST annual return FY 2025-26", "CGST Act / GSTR-9", "Annual", "31-Dec-2026", "Deepak Venkatesh", "Not started"],
            ["CMP-09", "Annual return of the company", "Companies Act / MGT-7", "Annual", "29-Nov-2026", "Tanvi Mehta", "Not started"],
            ["CMP-10", "Filing of financial statements", "Companies Act / AOC-4", "Annual", "30-Oct-2026", "Tanvi Mehta", "In progress"],
            ["CMP-11", "Annual POSH report to District Officer", "POSH Act 2013", "Annual", "31-Jan-2027", "Priya Raghavan", "Not started"],
            ["CMP-12", "Shops & Establishments registration renewal", "Karnataka S&E Act", "Every 5 years", "15-Mar-2027", "Kavitha Menon", "Not started"],
            ["CMP-13", "DPDP consent records and notice review", "DPDP Act 2023", "Half-yearly", "30-Nov-2026", "Ritu Agarwal", "In progress"],
            ["CMP-14", "ISO/IEC 27001 surveillance audit", "ISO/IEC 27001:2022", "Annual", "18-Nov-2026", "Sanjay Kumar Das", "Scheduled"],
            ["CMP-15", "Fire safety NOC renewal - Bellandur", "Karnataka Fire Force Act", "Annual", "05-Jan-2027", "Facilities Manager", "Not started"],
            ["CMP-16", "Labour welfare fund contribution", "Karnataka LWF Act", "Annual", "15-Jan-2027", "Mohammed Irfan", "Not started"],
        ],
        "Contract Renewals": [
            ["Contract ID", "Counterparty", "Type", "Start Date", "End Date", "Renewal Notice By", "Owner"],
            ["CNT-2026-9941", "Orchid Retail Ventures Pvt. Ltd.", "Master Services Agreement (v2)", "01-Jul-2026", "30-Jun-2029", "01-Apr-2029", "Tanvi Mehta"],
            ["CNT-2026-9914", "Zenvia Analytics LLP", "Mutual NDA", "03-Feb-2026", "02-Feb-2028", "-", "Tanvi Mehta"],
            ["CNT-2026-9491", "CleanSpark Facility Services Pvt. Ltd.", "Facility services", "01-Apr-2026", "31-Mar-2027", "01-Mar-2027", "Facilities Manager"],
            ["LIC-2026-0457", "Trident Logistics Pvt. Ltd.", "Software licence (outbound)", "01-May-2026", "30-Apr-2029", "30-Jan-2027", "Suresh Pillai"],
            ["DPA-2026-031", "Healthbridge Diagnostics Pvt. Ltd.", "Data processing agreement", "02-Mar-2026", "01-Mar-2028", "01-Dec-2027", "Ritu Agarwal"],
            ["IPA-2026-012", "Kiran Joshi", "IP assignment", "21-May-2026", "-", "-", "Tanvi Mehta"],
        ],
    })

doc("IP_Assignment_Agreement.md", "legal", "Intellectual Property Assignment Agreement (IPA-2026-012)",
    "Assignment of IP in the Project Sentinel mobile SDK from independent consultant Kiran Joshi to Nimbus.",
    blocks=[
        H1("1. Parties"),
        P("This Intellectual Property Assignment Agreement (reference IPA-2026-012) is made on 21 May 2026 between "
          "Kiran Joshi, an independent software consultant residing at Kothrud, Pune 411038 (the \"Assignor\"), "
          "and Nimbus Technologies Pvt. Ltd., Bengaluru (the \"Assignee\")."),
        H1("2. Background"),
        P("Between 1 December 2025 and 30 April 2026 the Assignor developed, under a consultancy engagement with the "
          "Assignee, a mobile software development kit code-named Project Sentinel, which enables offline ticket "
          "capture and secure sync for the NimbusDesk field-service app on Android and iOS. The parties wish to "
          "record the transfer of all rights in that work to the Assignee."),
        H1("3. Assignment"),
        P("In consideration of a lump-sum payment of ₹3,20,000 (Rupees Three Lakh Twenty Thousand only), the "
          "receipt of which the Assignor acknowledges, the Assignor irrevocably assigns to the Assignee, for the "
          "entire world and for the full term of protection, all right, title and interest in the Assigned Works, "
          "including copyright in source code, object code, documentation, designs and test suites, and any "
          "inventions, improvements or know-how conceived in the course of the engagement."),
        P("The assignment is made under Section 18 of the Copyright Act, 1957. The parties expressly agree that the "
          "assignment shall not lapse if the Assignee does not exercise the rights within one year, and that the "
          "territorial extent of the assignment is worldwide."),
        H1("4. Assigned Works"),
        UL("The Project Sentinel SDK source repository as at commit tag v1.4.0.",
           "The offline encryption module using SQLCipher-compatible storage.",
           "API documentation, architecture diagrams and the automated test suite of 1,240 test cases.",
           "All interim builds delivered between December 2025 and April 2026."),
        H1("5. Excluded Prior Inventions"),
        P("The Assignor's pre-existing open-source charting library \"OpenGrid\", released under the MIT licence in "
          "2022, is excluded from this assignment. The Assignor grants the Assignee a perpetual, royalty-free "
          "licence to use OpenGrid to the extent it is incorporated into the Assigned Works."),
        H1("6. Moral Rights"),
        P("To the extent permitted by law, the Assignor waives the right to be identified as the author of the "
          "Assigned Works and agrees not to object to any modification of them."),
        H1("7. Further Assurance"),
        P("The Assignor shall sign any further documents reasonably required to register or enforce the Assignee's "
          "rights, including patent applications, for 3 years after the date of this Agreement, at the Assignee's cost."),
        H1("8. Warranties"),
        UL("The Assigned Works are original and do not infringe any third-party rights.",
           "No part of the Assigned Works has been licensed or assigned to any other person.",
           "No open-source component under a copyleft licence such as GPL has been included."),
        H1("9. Non-Solicitation and Confidentiality"),
        P("For 12 months from the date of this Agreement the Assignor shall not solicit any customer of the Assignee "
          "for which the Assignor performed work. The Assignor shall keep confidential all non-public information "
          "about the Assignee's products indefinitely."),
        H1("10. Governing Law"),
        P("This Agreement is governed by the laws of India, and disputes are subject to arbitration seated in "
          "Bengaluru. Signed by Kiran Joshi and by Arjun Bhatt, Chief Technology Officer, for the Assignee."),
    ])

# =========================================================================== #
#                              HEALTHCARE (10)                                #
# =========================================================================== #
doc("Discharge_Summary_PAT-55102.pdf", "healthcare", "Discharge Summary - Patient PAT-55102",
    "Cardiology discharge summary for Mr. Ramesh Gowda (PAT-55102): STEMI treated with stenting, medications, follow-up.",
    org=HOSPITAL,
    pages=[
        [
            H1("Patient Details"),
            TABLE(["Field", "Detail"], ["UHID", "PAT-55102"], ["Patient name", "Mr. Ramesh Gowda"],
                  ["Age / Sex", "58 years / Male"], ["Date of admission", "2 August 2026, 06:40 AM"],
                  ["Date of discharge", "7 August 2026"], ["Department", "Cardiology (Coronary Care Unit)"],
                  ["Consultant", "Dr. Sanjay Hegde, MD, DM (Cardiology)"], ["IP number", "IP-2026-30817"]),
            H1("Final Diagnosis"),
            UL("Acute inferior wall ST-elevation myocardial infarction (STEMI), Killip class I",
               "Single-vessel coronary artery disease - right coronary artery (RCA)",
               "Type 2 diabetes mellitus (known for 9 years)",
               "Systemic hypertension"),
            H1("Presenting Complaints"),
            P("Mr. Gowda presented to the emergency department with retrosternal chest pain radiating to the left arm "
              "for 2 hours, associated with sweating and breathlessness. ECG showed ST elevation in leads II, III and "
              "aVF. Troponin I was elevated at 4.8 ng/mL. He was taken up for primary angioplasty under the hospital's "
              "STEMI pathway; door-to-balloon time was 52 minutes."),
        ],
        [
            H1("Course in Hospital"),
            P("Coronary angiography on 2 August 2026 revealed a 100% thrombotic occlusion of the proximal right coronary "
              "artery. Primary percutaneous coronary intervention (PCI) was performed and one drug-eluting stent "
              "(3.0 x 28 mm) was deployed in the RCA with TIMI III flow achieved. The left anterior descending and "
              "circumflex arteries had no significant disease."),
            P("Post-procedure he was monitored in the Coronary Care Unit for 48 hours. There were no arrhythmias or "
              "bleeding complications. A 2D echocardiogram on 4 August 2026 showed inferior wall hypokinesia with a "
              "left ventricular ejection fraction (LVEF) of 45% and no mechanical complications. He was mobilised on "
              "day 3 and completed a supervised six-minute walk of 380 metres before discharge."),
            H1("Key Investigations"),
            TABLE(["Test", "Result"], ["Troponin I (admission)", "4.8 ng/mL"], ["HbA1c", "7.9%"],
                  ["LDL cholesterol", "142 mg/dL"], ["Serum creatinine", "1.1 mg/dL"],
                  ["Haemoglobin", "13.8 g/dL"], ["LVEF (echo)", "45%"]),
            H1("Condition at Discharge"),
            P("Haemodynamically stable, chest-pain free, blood pressure 128/78 mmHg, heart rate 68 per minute. "
              "Radial access site healthy."),
        ],
        [
            H1("Discharge Medications"),
            TABLE(["Medicine", "Dose", "Frequency", "Duration"],
                  ["Aspirin", "75 mg", "Once daily after lunch", "Lifelong"],
                  ["Ticagrelor", "90 mg", "Twice daily", "12 months"],
                  ["Atorvastatin", "80 mg", "Once daily at bedtime", "Long term"],
                  ["Metoprolol succinate", "25 mg", "Twice daily", "Long term"],
                  ["Ramipril", "2.5 mg", "Once daily", "Long term"],
                  ["Metformin", "500 mg", "Twice daily with meals", "Long term"],
                  ["Pantoprazole", "40 mg", "Once daily before breakfast", "While on dual antiplatelets"]),
            P("Do not stop aspirin or ticagrelor without consulting the cardiologist, even for dental procedures."),
            H1("Advice on Discharge"),
            UL("Low-salt, low-fat diabetic diet; avoid tobacco in any form.",
               "Walk 15 minutes twice daily, increasing gradually; no heavy lifting for 4 weeks.",
               "Enrol in the 12-session cardiac rehabilitation programme starting the week after discharge.",
               "Return to the emergency department immediately for chest pain, breathlessness or fainting."),
            H1("Follow-up"),
            P("Review with Dr. Sanjay Hegde at the Cardiology OPD on 21 August 2026 at 10:30 AM with a fasting lipid "
              "profile and renal function test. Emergency helpline: 080-4567-1000 (24 hours)."),
        ],
    ])

doc("Lab_Report_PAT-55120.xlsx", "healthcare", "Laboratory Report - Patient PAT-55120",
    "Biochemistry and haematology results for Ms. Lakshmi Narayanan (PAT-55120), including HbA1c and lipid profile.",
    org=HOSPITAL,
    sheets={
        "Patient Details": [
            ["Field", "Value"], ["Patient ID", "PAT-55120"], ["Patient name", "Ms. Lakshmi Narayanan"],
            ["Age / Sex", "46 years / Female"], ["Sample ID", "LAB-2026-77314"],
            ["Sample collected", "12-Sep-2026 07:55 AM"], ["Report released", "12-Sep-2026 04:20 PM"],
            ["Referring doctor", "Dr. Kavya Shetty (Endocrinology)"], ["Reported by", "Dr. Manoj Kulkarni, MD (Pathology)"],
        ],
        "Results": [
            ["Test", "Result", "Unit", "Reference Range", "Flag"],
            ["HbA1c (glycated haemoglobin)", 8.4, "%", "4.0 - 5.6", "High"],
            ["Fasting plasma glucose", 162, "mg/dL", "70 - 100", "High"],
            ["Post-prandial plasma glucose", 238, "mg/dL", "< 140", "High"],
            ["Total cholesterol", 214, "mg/dL", "< 200", "High"],
            ["LDL cholesterol", 138, "mg/dL", "< 100", "High"],
            ["HDL cholesterol", 42, "mg/dL", "> 50", "Low"],
            ["Triglycerides", 190, "mg/dL", "< 150", "High"],
            ["Serum creatinine", 0.9, "mg/dL", "0.6 - 1.1", "Normal"],
            ["eGFR", 78, "mL/min/1.73m2", "> 90", "Low"],
            ["TSH", 2.8, "mIU/L", "0.4 - 4.0", "Normal"],
            ["Haemoglobin", 11.6, "g/dL", "12.0 - 15.5", "Low"],
            ["Vitamin B12", 182, "pg/mL", "200 - 900", "Low"],
            ["Urine microalbumin", 46, "mg/g creatinine", "< 30", "High"],
        ],
    })

doc("Clinical_Trial_Protocol_Summary.pdf", "healthcare", "Clinical Trial Protocol Summary - GLYCO-SHIELD (SLH-CT-2026-07)",
    "Phase III randomised trial of Glucoverin XR in type 2 diabetes: design, sample size, eligibility and safety monitoring.",
    org=HOSPITAL,
    pages=[
        [
            H1("1. Protocol Synopsis"),
            TABLE(["Item", "Detail"], ["Protocol number", "SLH-CT-2026-07"], ["Short title", "GLYCO-SHIELD"],
                  ["Phase", "Phase III"], ["Sponsor", "Silverleaf Research Foundation"],
                  ["Registry", "CTRI/2026/03/061245"],
                  ["Principal Investigator", "Dr. Nandini Rao, Endocrinology"],
                  ["Ethics approval", "Institutional Ethics Committee, 14 March 2026"]),
            H1("2. Background and Rationale"),
            P("Glucoverin XR 500 mg is an investigational once-daily extended-release oral agent that combines "
              "hepatic glucose suppression with improved insulin sensitivity. Phase II data in 180 patients showed a "
              "mean HbA1c reduction of 0.9 percentage points over 12 weeks with a low rate of hypoglycaemia. "
              "GLYCO-SHIELD aims to confirm efficacy and safety in a larger Indian population with type 2 diabetes "
              "inadequately controlled on metformin alone."),
            H1("3. Objectives"),
            UL("Primary: to compare the change in HbA1c from baseline to week 24 between Glucoverin XR and placebo, "
               "both added to stable metformin therapy.",
               "Secondary: proportion of participants achieving HbA1c below 7.0%, change in fasting glucose and body "
               "weight, and incidence of hypoglycaemia."),
        ],
        [
            H1("4. Study Design"),
            P("GLYCO-SHIELD is a multicentre, randomised, double-blind, placebo-controlled, parallel-group study. A "
              "total of 640 participants will be enrolled across 12 sites in India and randomised in a 1:1 ratio to "
              "Glucoverin XR 500 mg once daily or a matching placebo. Randomisation is stratified by baseline HbA1c "
              "(below or above 8.5%) and by site. The treatment period is 24 weeks, followed by a 4-week safety "
              "follow-up."),
            H1("5. Key Inclusion Criteria"),
            UL("Adults aged 30 to 65 years with type 2 diabetes for at least 1 year.",
               "HbA1c between 7.5% and 10.5% at screening.",
               "On a stable metformin dose of at least 1,500 mg per day for 8 weeks.",
               "Body mass index between 22 and 40 kg/m2."),
            H1("6. Key Exclusion Criteria"),
            UL("eGFR below 45 mL/min/1.73 m2.",
               "History of diabetic ketoacidosis or type 1 diabetes.",
               "Myocardial infarction or stroke within the previous 6 months.",
               "Pregnancy, breastfeeding, or unwillingness to use contraception.",
               "ALT or AST more than 3 times the upper limit of normal."),
            H1("7. Visits and Assessments"),
            P("Participants attend 8 scheduled visits: screening, randomisation (week 0) and weeks 4, 8, 12, 16, 24 "
              "and 28. HbA1c is measured centrally at weeks 0, 12 and 24. Participants receive a glucometer and log "
              "fasting self-monitored glucose 3 times a week."),
        ],
        [
            H1("8. Safety Monitoring"),
            P("An independent Data Safety Monitoring Board (DSMB) of three members reviews unblinded safety data every "
              "6 months. Serious adverse events must be reported by the investigator to the sponsor and the ethics "
              "committee within 24 hours of the site becoming aware of them, as required by the New Drugs and "
              "Clinical Trials Rules, 2019. Severe hypoglycaemia is an adverse event of special interest."),
            H1("9. Statistical Considerations"),
            P("The sample size of 640 provides 90% power to detect a difference of 0.4 percentage points in HbA1c "
              "change at a two-sided alpha of 0.05, assuming a standard deviation of 1.1 and a 15% drop-out rate."),
            H1("10. Participant Compensation"),
            P("Participants receive Rs. 1,500 per completed visit towards travel and loss of wages. Medical management "
              "of any trial-related injury is free of cost, and compensation is paid as per the formula in the 2019 Rules."),
            H1("11. Timelines"),
            UL("First participant in: April 2026.",
               "Last participant in: June 2027.",
               "Last participant out: December 2027.",
               "Clinical study report: June 2028."),
        ],
    ])

doc("Infection_Control_Policy.html", "healthcare", "Hospital Infection Prevention and Control Policy (HIC-POL-004)",
    "Hand hygiene, PPE, biomedical waste segregation, needle-stick management and surveillance rules.",
    org=HOSPITAL,
    blocks=[
        H1("1. Purpose and Scope"),
        P("This policy (HIC-POL-004, version 6, effective 1 May 2026) sets out the infection prevention and control "
          "practices that apply to all doctors, nurses, technicians, housekeeping staff, students and visitors in "
          "all clinical and non-clinical areas of the hospital. It is overseen by the Hospital Infection Control "
          "Committee (HICC), chaired by the Medical Superintendent, which meets on the second Tuesday of every month."),
        H1("2. Hand Hygiene"),
        P("Staff must perform hand hygiene at the WHO five moments: before touching a patient, before a clean or "
          "aseptic procedure, after body fluid exposure risk, after touching a patient, and after touching patient "
          "surroundings. Alcohol-based hand rub should be applied for 20 to 30 seconds; hand washing with soap and "
          "water should take 40 to 60 seconds and is mandatory when hands are visibly soiled or after caring for "
          "patients with diarrhoea."),
        P("The hospital's target for hand hygiene compliance is 90%, measured by monthly direct observation audits "
          "of at least 200 opportunities per ward. Wards below 80% compliance for two consecutive months are placed "
          "on a focused improvement plan by the infection control nurse."),
        H1("3. Personal Protective Equipment"),
        UL("Gloves for any contact with blood, body fluids, mucous membranes or non-intact skin.",
           "Fluid-resistant gowns and face shields for procedures likely to generate splashes.",
           "N95 respirators for airborne precautions, such as suspected tuberculosis, with annual fit testing.",
           "PPE must be removed in the correct sequence and disposed of before leaving the patient area."),
        H1("4. Biomedical Waste Segregation"),
        P("Waste is segregated at the point of generation in line with the Bio-Medical Waste Management Rules, 2016:"),
        TABLE(["Category", "Container colour", "Examples"],
              ["Yellow", "Yellow bag", "Anatomical waste, soiled dressings, expired medicines"],
              ["Red", "Red bag", "Contaminated recyclable plastics: tubing, catheters, IV sets, gloves"],
              ["White", "White translucent puncture-proof container", "Needles, syringes with fixed needles, scalpels, blades"],
              ["Blue", "Blue cardboard box", "Broken or discarded glassware and metallic implants"]),
        P("Waste must not be stored in clinical areas for more than 48 hours and is collected twice daily by the "
          "authorised common biomedical waste treatment facility."),
        H1("5. Needle-Stick and Sharps Injuries"),
        P("Any needle-stick or sharps injury must be washed immediately with soap and running water and reported to "
          "the emergency medical officer within 2 hours. Post-exposure prophylaxis for HIV, when indicated, should be "
          "started as soon as possible and ideally within 2 hours, and not later than 72 hours after exposure. "
          "Every exposure is recorded in the occupational exposure register and followed up for 6 months."),
        H1("6. Surveillance"),
        P("The infection control team tracks central line-associated bloodstream infections (CLABSI), "
          "catheter-associated urinary tract infections, ventilator-associated events and surgical site infections. "
          "Rates are reported to the HICC monthly. The current CLABSI benchmark is fewer than 2 infections per "
          "1,000 central line days."),
        H1("7. Isolation"),
        P("Patients with suspected or confirmed multidrug-resistant organisms are placed in single rooms with "
          "contact precautions. Airborne infection isolation rooms on the 4th floor maintain at least 12 air changes "
          "per hour under negative pressure."),
        H1("8. Staff Health"),
        P("All healthcare workers must be vaccinated against hepatitis B, with antibody titres checked one month after "
          "the third dose. Annual influenza vaccination is offered free of charge in October."),
    ])

_FORMULARY = [
    ("Paracetamol", "500 mg", "Tablet", "Analgesic", 1.20, "N"),
    ("Aspirin", "75 mg", "Tablet", "Antiplatelet", 0.85, "N"),
    ("Ticagrelor", "90 mg", "Tablet", "Antiplatelet", 48.50, "N"),
    ("Clopidogrel", "75 mg", "Tablet", "Antiplatelet", 6.40, "N"),
    ("Atorvastatin", "80 mg", "Tablet", "Statin", 14.75, "N"),
    ("Rosuvastatin", "20 mg", "Tablet", "Statin", 18.20, "N"),
    ("Metoprolol succinate", "25 mg", "Tablet ER", "Beta blocker", 5.60, "N"),
    ("Ramipril", "2.5 mg", "Capsule", "ACE inhibitor", 4.10, "N"),
    ("Metformin", "500 mg", "Tablet", "Antidiabetic", 1.75, "N"),
    ("Glimepiride", "2 mg", "Tablet", "Antidiabetic", 3.90, "N"),
    ("Insulin glargine", "100 IU/mL", "Injection (3 mL pen)", "Antidiabetic", 612.00, "N"),
    ("Pantoprazole", "40 mg", "Tablet", "Proton pump inhibitor", 4.80, "N"),
    ("Amoxicillin-clavulanate", "625 mg", "Tablet", "Antibiotic", 22.30, "N"),
    ("Ceftriaxone", "1 g", "Injection", "Antibiotic", 58.00, "N"),
    ("Piperacillin-tazobactam", "4.5 g", "Injection", "Antibiotic", 410.00, "Y"),
    ("Meropenem", "1 g", "Injection", "Antibiotic", 1240.00, "Y"),
    ("Vancomycin", "500 mg", "Injection", "Antibiotic", 295.00, "Y"),
    ("Colistin", "1 MIU", "Injection", "Antibiotic", 1580.00, "Y"),
    ("Enoxaparin", "40 mg", "Injection", "Anticoagulant", 355.00, "N"),
    ("Heparin", "5000 IU/mL", "Injection", "Anticoagulant", 96.00, "N"),
    ("Ondansetron", "4 mg", "Injection", "Antiemetic", 12.50, "N"),
    ("Morphine", "10 mg/mL", "Injection", "Opioid analgesic", 38.00, "Y"),
    ("Salbutamol", "100 mcg", "Inhaler", "Bronchodilator", 145.00, "N"),
    ("Levothyroxine", "50 mcg", "Tablet", "Thyroid hormone", 1.60, "N"),
    ("Amlodipine", "5 mg", "Tablet", "Calcium channel blocker", 2.20, "N"),
    ("Furosemide", "40 mg", "Tablet", "Diuretic", 1.10, "N"),
    ("Dexamethasone", "4 mg/mL", "Injection", "Corticosteroid", 9.80, "N"),
    ("Tenecteplase", "40 mg", "Injection", "Thrombolytic", 38500.00, "Y"),
]


def _formulary_rows():
    rows = [["Formulary Code", "Generic Name", "Strength", "Dosage Form", "Therapeutic Class",
             "Unit Price (INR)", "Restricted (Y/N)", "Reorder Level"]]
    for i, (name, strength, form, cls, price, restricted) in enumerate(_FORMULARY):
        rows.append([f"FRM-{101 + i:03d}", name, strength, form, cls, price, restricted, 50 + (i * 37) % 450])
    return rows


doc("Pharmacy_Formulary.xlsx", "healthcare", "Hospital Pharmacy Formulary 2026",
    "Approved drug formulary with codes, strengths, dosage forms, unit prices and restricted-antibiotic flags.",
    org=HOSPITAL,
    sheets={
        "Formulary": _formulary_rows(),
        "Restriction Rules": [
            ["Rule", "Detail"],
            ["Restricted antibiotics", "Meropenem, colistin, vancomycin and piperacillin-tazobactam need infectious-disease consultant approval within 24 hours"],
            ["Opioids", "Morphine is dispensed only against a signed prescription and recorded in the narcotics register"],
            ["Thrombolytics", "Tenecteplase is stocked in the emergency department and cardiac cath lab only"],
            ["Non-formulary requests", "Approved by the Pharmacy & Therapeutics Committee, which meets every month"],
        ],
    })

_DOCTORS = [("Cardiology", "Dr. Sanjay Hegde"), ("Endocrinology", "Dr. Kavya Shetty"),
            ("Orthopaedics", "Dr. Aditya Kamath"), ("Paediatrics", "Dr. Rekha Murthy"),
            ("General Medicine", "Dr. Imran Qureshi"), ("Dermatology", "Dr. Sowmya Bhat")]
_PATIENTS = ["Ramesh Gowda", "Lakshmi Narayanan", "Anil Kumar", "Bhavana Rao", "Chetan Shah", "Deepa Iyer",
             "Elango Murugan", "Farzana Begum", "Ganesh Patil", "Hema Sundaram", "Irfan Khan", "Jyothi Reddy",
             "Kiran Hegde", "Latha Krishnamurthy", "Manjunath S", "Nandita Bose", "Omkar Joshi", "Parvathi Menon",
             "Qadir Ahmed", "Radhika Pai", "Santosh Naik", "Tara Fernandes", "Uday Shankar", "Vani Prakash",
             "Wasim Akram Shaikh", "Yamini Das", "Zubin Mistry", "Akash Verma", "Bindu Thomas", "Chandra Mohan"]


def _appointment_rows():
    rows = [["Appointment ID", "Patient ID", "Patient Name", "Department", "Doctor", "Date", "Time",
             "Mode", "Status"]]
    for i, name in enumerate(_PATIENTS):
        dept, doctor = _DOCTORS[(i * 5 + 1) % 6] if i > 1 else _DOCTORS[i]
        date = dt.date(2026, 8, 17) + dt.timedelta(days=(i * 3) % 28)
        time = f"{9 + (i * 2) % 8:02d}:{(i * 15) % 60:02d}"
        mode = "Teleconsult" if i % 4 == 3 else "In-person"
        status = ["Completed", "Completed", "No-show", "Completed", "Cancelled", "Completed"][i % 6]
        pid = f"PAT-{55100 + i * 7 + (2 if i == 0 else 0) + (13 if i == 1 else 0)}"
        rows.append([f"APT-2026-{1170 + i}", pid, name, dept, doctor, date.strftime("%d-%b-%Y"), time, mode, status])
    # The cardiology follow-up of PAT-55102 matches the discharge summary.
    rows[1][5], rows[1][6] = "21-Aug-2026", "10:30"
    return rows


doc("Patient_Appointments.csv", "healthcare", "Outpatient Appointments Register (Aug-Sep 2026)",
    "30 outpatient appointments with appointment IDs (APT-2026-11xx), patient IDs, department, doctor, date, mode and status.",
    org=HOSPITAL, rows=_appointment_rows())

doc("Diabetes_Care_Guideline.md", "healthcare", "Clinical Guideline: Management of Type 2 Diabetes in Adults (CG-END-002)",
    "Glycaemic targets, monitoring schedule, first-line therapy, hypoglycaemia management and complication screening.",
    org=HOSPITAL,
    blocks=[
        H1("1. Scope"),
        P("This guideline (CG-END-002, version 3.2, approved by the Department of Endocrinology on 9 January 2026) "
          "applies to adults aged 18 years and above with type 2 diabetes attending outpatient clinics and "
          "admitted to general wards. It does not cover pregnancy, type 1 diabetes or children, for which separate "
          "guidelines exist."),
        H1("2. Diagnosis"),
        P("Type 2 diabetes is diagnosed when any one of the following is confirmed on repeat testing: fasting plasma "
          "glucose of 126 mg/dL or higher, 2-hour plasma glucose of 200 mg/dL or higher during an oral glucose "
          "tolerance test, or HbA1c of 6.5% or higher measured by an NGSP-certified method."),
        H1("3. Treatment Targets"),
        TABLE(["Parameter", "Target for most adults", "Older or frail adults"],
              ["HbA1c", "Below 7.0%", "Below 8.0%"],
              ["Fasting capillary glucose", "80 - 130 mg/dL", "90 - 150 mg/dL"],
              ["Blood pressure", "Below 130/80 mmHg", "Below 140/90 mmHg"],
              ["LDL cholesterol", "Below 100 mg/dL (below 70 if cardiovascular disease)", "Individualised"]),
        H1("4. Monitoring Schedule"),
        UL("HbA1c every 3 months until the patient reaches the target, then every 6 months if stable.",
           "Retinal screening (dilated fundus examination or fundus photography) annually.",
           "Comprehensive foot examination annually, and at every visit for patients with neuropathy or prior ulcers.",
           "Urine albumin-to-creatinine ratio and eGFR annually.",
           "Lipid profile annually."),
        H1("5. Pharmacological Therapy"),
        P("Metformin is the first-line agent unless contraindicated. Start with 500 mg once daily with the evening "
          "meal and increase by 500 mg every 1 to 2 weeks to a usual maximum of 2,000 mg per day. Metformin is "
          "contraindicated when eGFR is below 30 mL/min/1.73 m2 and the dose should be halved when eGFR is between "
          "30 and 45. For patients with established cardiovascular disease, heart failure or chronic kidney "
          "disease, add an SGLT2 inhibitor or GLP-1 receptor agonist regardless of HbA1c. Insulin is started when "
          "HbA1c remains above 10% or symptoms of severe hyperglycaemia are present."),
        H1("6. Hypoglycaemia"),
        P("Hypoglycaemia is a blood glucose below 70 mg/dL. Conscious patients should follow the rule of 15: take 15 "
          "grams of fast-acting carbohydrate (for example 3 glucose tablets or 150 mL of fruit juice), recheck the "
          "blood glucose after 15 minutes, and repeat if it is still below 70 mg/dL. Once glucose is normal, a snack "
          "containing complex carbohydrate should be taken. Unconscious patients must receive intravenous 25% "
          "dextrose or intramuscular glucagon 1 mg and never anything by mouth."),
        H1("7. Lifestyle"),
        P("All patients are referred to the diabetes educator at diagnosis. Recommended physical activity is at least "
          "150 minutes per week of moderate-intensity exercise spread over at least 3 days, with no more than 2 "
          "consecutive days without activity. Patients who are overweight should aim for a 5 to 7 percent "
          "reduction in body weight."),
        H1("8. Referral Criteria"),
        UL("Refer to ophthalmology for any diabetic retinopathy beyond mild non-proliferative changes.",
           "Refer to the diabetic foot clinic within 24 hours for any active foot ulcer.",
           "Refer to nephrology if eGFR falls below 30 or declines by more than 25% within a year."),
    ])

doc("Telemedicine_SOP.txt", "healthcare", "Standard Operating Procedure: Telemedicine Consultations (SOP-TM-009)",
    "SOP for video/audio teleconsultations: identity checks, slot length, fees, e-prescribing limits and record keeping.",
    org=HOSPITAL,
    blocks=[
        H1("1. Purpose"),
        P("This SOP (SOP-TM-009, version 2.0, effective 15 February 2026) describes how doctors at Silverleaf "
          "Multispeciality Hospital deliver teleconsultations through the SilverConnect platform in compliance with "
          "the Telemedicine Practice Guidelines, 2020 issued under the Indian Medical Council regulations. It "
          "covers outpatient follow-ups, second opinions and post-discharge reviews."),
        H1("2. Eligibility"),
        UL("Follow-up patients with a stable, previously diagnosed condition.",
           "Post-discharge reviews within 30 days of discharge.",
           "New patients for triage and non-emergency advice only.",
           "Teleconsultation is not offered for chest pain, breathlessness, stroke symptoms or trauma; such patients "
           "are directed to the emergency department."),
        H1("3. Booking and Fees"),
        P("Patients book through the hospital app or the call centre. Each teleconsultation slot is 15 minutes. The fee "
          "for a video consultation is ₹500 and for an audio-only consultation ₹350, payable online at booking. A "
          "follow-up teleconsultation within 7 days of the original consultation for the same complaint is free of "
          "charge. Senior consultants may charge ₹800 for second-opinion consultations."),
        H1("4. Conducting the Consultation"),
        P("The doctor must log in to SilverConnect at least 5 minutes before the slot. At the start of every "
          "consultation the doctor confirms the patient's identity using two identifiers - full name and either date "
          "of birth or the hospital patient ID - and records whether the patient gave consent, which is implied when "
          "the patient initiates the consultation. For minors, a guardian must be present on the call."),
        P("If the video connection fails, the doctor or the teleconsult coordinator must call the patient back on the "
          "registered mobile number within 10 minutes. If the consultation cannot be completed, the patient is offered "
          "a free reschedule within 48 hours."),
        H1("5. Prescribing"),
        P("E-prescriptions are generated in SilverConnect and digitally signed. Doctors may prescribe List O "
          "medicines (over-the-counter) and List A medicines (re-fills and common drugs) by video, and List B "
          "add-on medicines only for follow-up of a condition already diagnosed in person. Medicines in Schedule X "
          "and narcotic and psychotropic substances must never be prescribed by teleconsultation."),
        H1("6. Records and Privacy"),
        UL("Consultation notes are entered in the electronic medical record within 2 hours of the consultation.",
           "Teleconsultation records, including chat logs and prescriptions, are retained for 3 years.",
           "Audio and video of consultations are not recorded or stored.",
           "Doctors must conduct consultations from a private room and must not use personal messaging apps."),
        H1("7. Quality Monitoring"),
        P("The Telemedicine Coordinator, Ms. Sheela Thomas, audits 5% of teleconsultations each month for "
          "documentation completeness. Patient satisfaction is measured by an SMS survey, with a target average of "
          "4.5 out of 5. Technical issues are logged with the IT helpdesk on extension 2299."),
        H1("8. Escalation"),
        P("If during a teleconsultation the doctor identifies a red-flag symptom, the doctor must advise the patient "
          "to visit the emergency department immediately, arrange an ambulance on 108 if needed, and document the advice."),
    ])

doc("Patient_Consent_Form.docx", "healthcare", "Informed Consent for Surgery and Anaesthesia (CF-SURG-011)",
    "Template informed consent form for surgical procedures: risks, alternatives, anaesthesia, blood transfusion and validity.",
    org=HOSPITAL,
    blocks=[
        H1("Part A: Patient Information"),
        P("Form CF-SURG-011, version 4.1, effective 1 March 2026. This form records the informed consent of the "
          "patient (or legally authorised representative) for the surgical procedure and anaesthesia described below. "
          "It must be completed by the operating surgeon in a language the patient understands; Kannada, Hindi, "
          "Tamil and English versions are available."),
        TABLE(["Field", "Entry"], ["Patient name", "____________________"], ["Patient ID (UHID)", "PAT-_____"],
              ["Age / Sex", "______"], ["Proposed procedure", "____________________"],
              ["Operating surgeon", "____________________"], ["Scheduled date", "____ / ____ / 2026"]),
        H1("Part B: Explanation by the Surgeon"),
        P("I, the operating surgeon, have explained to the patient the nature of the condition, the proposed "
          "procedure, its expected benefits, the material risks, the alternatives available including no treatment, "
          "and the likely consequences of declining treatment. I have answered all questions asked by the patient."),
        H2("Common and serious risks discussed"),
        UL("Bleeding that may require blood transfusion or a return to the operating theatre.",
           "Infection of the wound or deeper tissues.",
           "Blood clots in the legs or lungs.",
           "Injury to nearby organs, nerves or blood vessels.",
           "Rarely, risk to life."),
        H1("Part C: Anaesthesia"),
        P("The anaesthesiologist has explained the type of anaesthesia planned (general, regional, or local with "
          "sedation), its risks such as sore throat, nausea, allergic reaction and, rarely, awareness or cardiac "
          "events, and the requirement to fast for 6 hours for solids and 2 hours for clear fluids before surgery."),
        H1("Part D: Blood Transfusion"),
        P("I consent / do not consent (strike out whichever does not apply) to transfusion of blood or blood products "
          "if it becomes necessary. I understand that blood is screened for HIV, hepatitis B, hepatitis C, syphilis "
          "and malaria as per national guidelines."),
        H1("Part E: Patient Declaration"),
        UL("I confirm that I have read or have had read to me the information in this form.",
           "I understand that additional procedures may be performed if an unforeseen condition is found and it would be "
           "unsafe to delay them.",
           "I agree that tissue removed may be sent for examination and disposed of as per hospital policy.",
           "I understand that I may withdraw my consent at any time before the procedure begins."),
        H1("Part F: Validity and Special Situations"),
        P("This consent is valid for 30 days from the date of signing for the procedure named above. If the procedure "
          "is postponed beyond 30 days, or the planned procedure changes, a fresh consent must be taken. For high-risk "
          "procedures, the consent discussion must take place at least 24 hours before surgery, except in emergencies."),
        P("For patients below 18 years of age, consent is given by a parent or legal guardian. For patients who lack "
          "decision-making capacity, consent is given by the nominated representative. In a life-threatening emergency "
          "where no representative is available, two consultants may jointly certify the need for surgery."),
        H1("Part G: Signatures"),
        TABLE(["Role", "Name", "Signature", "Date and time"],
              ["Patient / representative", "", "", ""], ["Witness (not a member of the surgical team)", "", "", ""],
              ["Operating surgeon", "", "", ""], ["Anaesthesiologist", "", "", ""]),
        P("An interpreter must also sign if one was used. The original form is filed in the patient's medical record "
          "and a copy is offered to the patient."),
    ])

doc("Clinical_Staff_Training.pptx", "healthcare", "Clinical Staff Mandatory Training 2026",
    "Training deck for nurses and doctors: emergency codes, BLS certification, CME hours, fire safety and assessment.",
    org=HOSPITAL,
    slides=[
        ("Clinical Staff Mandatory Training 2026", "Silverleaf Multispeciality Hospital | Nursing & Medical Education Department"),
        ("Why Mandatory Training Matters", [
            "Accreditation standards require documented competency for every clinical staff member",
            "Training gaps were linked to 3 of the 11 reportable patient-safety incidents in 2025",
            "Completion is tracked in the hospital learning portal, SilverLearn",
            "All modules for 2026 must be completed by 31 December 2026",
        ]),
        ("Hospital Emergency Codes", [
            "Code Blue: cardiac or respiratory arrest - response team must reach the bedside within 3 minutes",
            "Code Red: fire or smoke - follow RACE: Rescue, Alarm, Contain, Extinguish or Evacuate",
            "Code Pink: infant or child abduction - all exits are sealed immediately",
            "Code Orange: hazardous material spill",
            "Code Yellow: mass-casualty external disaster",
            "Dial 7777 from any internal phone to announce a code",
        ]),
        ("Basic and Advanced Life Support", [
            "Basic Life Support (BLS) certification is mandatory for all clinical staff and must be renewed every 2 years",
            "Advanced Cardiac Life Support (ACLS) is mandatory for ICU, emergency and cardiology staff",
            "Chest compressions at 100-120 per minute and a depth of 5-6 cm",
            "Mock code drills are held every month in each critical-care unit",
        ]),
        ("Continuing Medical Education", [
            "Doctors must complete 30 CME credit hours per year",
            "Nurses must complete 20 hours of continuing nursing education per year",
            "Hospital-sponsored conference leave of up to 5 days per year",
            "CME certificates must be uploaded to SilverLearn within 15 days",
        ]),
        ("Fire and Patient Safety", [
            "Fire drills are conducted every quarter in every department, including one unannounced night drill",
            "Know the location of the nearest extinguisher, hose reel and fire exit",
            "Use PASS for extinguishers: Pull, Aim, Squeeze, Sweep",
            "Report every patient fall and medication error in the incident portal within 24 hours",
        ]),
        ("Infection Control Refresher", [
            "Hand hygiene audits every month with a compliance target of 90%",
            "Biomedical waste segregation as per policy HIC-POL-004",
            "Needle-stick injuries must be reported within 2 hours",
        ]),
        ("Assessment and Certification", [
            "Each module ends with an online assessment of 25 multiple-choice questions",
            "The pass mark is 80%; candidates may attempt each assessment up to 3 times",
            "Staff who fail all 3 attempts attend a classroom remedial session",
            "Certificates are valid for one year and are checked during annual appraisal",
        ]),
        ("Training Calendar and Support", [
            "January-March: BLS and ACLS refresher batches every Saturday morning in the skills lab",
            "April-June: infection control and biomedical waste modules",
            "July-September: fire safety, emergency codes and patient-safety reporting",
            "October-December: pending modules and remedial sessions",
            "Contact the Nursing & Medical Education Department on extension 2310 for batch changes",
        ]),
    ])

# =========================================================================== #
#                                FINANCE (10)                                 #
# =========================================================================== #
_SELLER = ("Nimbus Technologies Pvt. Ltd., Tower B, Lakeview Tech Park, Outer Ring Road, Bellandur, Bengaluru "
           "560103, Karnataka. GSTIN 29AAHCN4821K1Z5. PAN AAHCN4821K. CIN U72900KA2015PTC081234.")
_BANK = ("Bank: National Commerce Bank, Koramangala branch, Bengaluru. Account name: Nimbus Technologies Pvt. Ltd. "
         "Current account no. 50200018273645. IFSC NCBK0000412. Please quote the invoice number as the payment reference.")

doc("Invoice_INV-2026-8842.pdf", "finance", "Tax Invoice INV-2026-8842",
    "Tax invoice to Orchid Retail Ventures for peak-season readiness project work under CNT-2026-9941; total Rs. 4,72,000.",
    pages=[
        [
            H1("Supplier"), P(_SELLER),
            H1("Invoice Details"),
            TABLE(["Field", "Detail"], ["Invoice number", "INV-2026-8842"], ["Invoice date", "30 September 2026"],
                  ["Due date", "30 October 2026"], ["Contract reference", "CNT-2026-9941 (MSA Version 2)"],
                  ["Change request", "CR-2026-014 - E-commerce peak-season readiness"],
                  ["Bill to", "Orchid Retail Ventures Pvt. Ltd., 22 Residency Road, Bengaluru 560025"],
                  ["Customer GSTIN", "29AABCO7731M1Z2"], ["Place of supply", "Karnataka (29)"]),
            H1("Line Items"),
            TABLE(["#", "Description", "SAC", "Amount (Rs.)"],
                  ["1", "Performance and load testing of the order platform (festive season)", "998314", "1,60,000"],
                  ["2", "Cloud capacity upgrade and auto-scaling configuration", "998314", "1,40,000"],
                  ["3", "War-room support during the sale weekend, 18-21 September 2026", "998314", "1,00,000"],
                  ["", "Subtotal", "", "4,00,000"],
                  ["", "CGST @ 9%", "", "36,000"],
                  ["", "SGST @ 9%", "", "36,000"],
                  ["", "Total amount payable", "", "4,72,000"]),
            P("Amount in words: Rupees Four Lakh Seventy-Two Thousand only."),
        ],
        [
            H1("Payment Terms"),
            P("Payment is due within 30 days of the invoice date in accordance with clause 5 of the Amended and Restated "
              "Master Services Agreement CNT-2026-9941. Undisputed amounts not paid by the due date attract interest at "
              "1% per month. Any dispute regarding this invoice must be raised in writing within 10 days of receipt."),
            H1("Bank Details"), P(_BANK),
            H1("Notes"),
            UL("This invoice covers one-time project work approved under change request CR-2026-014 and is in addition "
               "to the regular monthly managed-services fee, which is invoiced separately.",
               "Work was accepted by the Client's Head of E-commerce, Ms. Pallavi Sinha, on 24 September 2026.",
               "Tax deducted at source, if any, should be deducted at 10% under section 194J and the TDS certificate "
               "shared within the statutory timeline.",
               "This is a computer-generated invoice and does not require a physical signature."),
            H1("Contact"),
            P("For billing queries contact accounts.receivable@nimbustech.example or call Mohammed Irfan, Accounts "
              "Executive, on extension 4128."),
            H1("Standard Terms of Invoice"),
            UL("Goods and services once accepted are not returnable; service disputes are resolved under the governing "
               "agreement referenced above.",
               "Payments must be made only by bank transfer to the account shown on this invoice. Nimbus never asks "
               "customers to change bank details by email; please verify any such request by phone before paying.",
               "Partial payments are applied first to interest and then to the oldest outstanding invoice.",
               "Credit notes, if any, will be issued separately and reported to the GST portal in the same return period.",
               "Subject to Bengaluru jurisdiction."),
        ],
    ])

doc("Invoice_INV-2026-8824.pdf", "finance", "Tax Invoice INV-2026-8824",
    "Tax invoice to Trident Logistics for NimbusDesk implementation and data migration under LIC-2026-0457.",
    pages=[
        [
            H1("Supplier"), P(_SELLER),
            H1("Invoice Details"),
            TABLE(["Field", "Detail"], ["Invoice number", "INV-2026-8824"], ["Invoice date", "15 September 2026"],
                  ["Due date", "15 October 2026"], ["Contract reference", "LIC-2026-0457 (Software Licence Agreement)"],
                  ["Bill to", "Trident Logistics Pvt. Ltd., Plot 18, MIDC Industrial Area, Bhiwandi, Maharashtra 421302"],
                  ["Customer GSTIN", "27AADCT5528P1ZK"], ["Place of supply", "Maharashtra (27)"]),
            H1("Line Items"),
            TABLE(["#", "Description", "SAC", "Amount (Rs.)"],
                  ["1", "NimbusDesk Enterprise implementation - workflow configuration for 6 warehouses", "998314", "2,45,000"],
                  ["2", "Data migration of 1.2 million historical tickets from the legacy helpdesk", "998314", "1,10,000"],
                  ["3", "Administrator training - 2 batches of 15 participants", "999293", "30,000"],
                  ["", "Subtotal", "", "3,85,000"],
                  ["", "IGST @ 18%", "", "69,300"],
                  ["", "Total amount payable", "", "4,54,300"]),
            P("Amount in words: Rupees Four Lakh Fifty-Four Thousand Three Hundred only."),
        ],
        [
            H1("Payment Terms"),
            P("Payment is due within 30 days of the invoice date. As this is an inter-state supply from Karnataka to "
              "Maharashtra, Integrated GST (IGST) has been charged. The one-time implementation fee is as agreed in the "
              "fee schedule of Software Licence Agreement LIC-2026-0457; the annual subscription fee is invoiced "
              "separately on 1 May each year."),
            H1("Bank Details"), P(_BANK),
            H1("Notes"),
            UL("Go-live of NimbusDesk at Trident Logistics was completed on 8 September 2026 and signed off by Mr. Nitin "
               "Wagh, IT Director, Trident Logistics.",
               "The 90-day warranty period under clause 8 of the licence agreement runs until 7 December 2026.",
               "Please deduct TDS, if applicable, under section 194J and share Form 16A quarterly.",
               "This is a computer-generated invoice and does not require a physical signature."),
            H1("Contact"),
            P("For billing queries contact accounts.receivable@nimbustech.example or call Mohammed Irfan, Accounts "
              "Executive, on extension 4128."),
            H1("Standard Terms of Invoice"),
            UL("Goods and services once accepted are not returnable; service disputes are resolved under the governing "
               "agreement referenced above.",
               "Payments must be made only by bank transfer to the account shown on this invoice. Nimbus never asks "
               "customers to change bank details by email; please verify any such request by phone before paying.",
               "Partial payments are applied first to interest and then to the oldest outstanding invoice.",
               "Credit notes, if any, will be issued separately and reported to the GST portal in the same return period.",
               "Subject to Bengaluru jurisdiction."),
        ],
    ])

_VENDORS = [
    ("VND-1031", "Apex Compute Solutions Pvt. Ltd.", "IT hardware", "Bengaluru", "Net 30", "A"),
    ("VND-1032", "TravelNest Corporate Travel LLP", "Travel management", "Bengaluru", "Net 15", "A"),
    ("VND-1033", "Bluewave Cloud Hosting Pvt. Ltd.", "Cloud infrastructure", "Mumbai", "Net 30", "A"),
    ("VND-1034", "Shree Ganesh Caterers", "Cafeteria", "Bengaluru", "Net 7", "B"),
    ("VND-1035", "Mehta Sharma & Associates", "Internal audit", "Bengaluru", "Net 30", "A"),
    ("VND-1036", "Kaveri Stationery Mart", "Office supplies", "Bengaluru", "Net 15", "C"),
    ("VND-1037", "SecureKey Identity Systems Pvt. Ltd.", "Access control", "Chennai", "Net 45", "B"),
    ("VND-1038", "CareLink TPA Services Pvt. Ltd.", "Insurance administration", "Bengaluru", "Net 30", "A"),
    ("VND-1039", "VeriTrust Screening Pvt. Ltd.", "Background verification", "Hyderabad", "Net 30", "B"),
    ("VND-1040", "MindHaven Wellness LLP", "Employee assistance", "Pune", "Net 30", "A"),
    ("VND-1041", "Lotus Print & Branding", "Printing", "Bengaluru", "Net 15", "C"),
    ("VND-1042", "CleanSpark Facility Services Pvt. Ltd.", "Facility services", "Bengaluru", "Net 21", "B"),
    ("VND-1043", "EscrowSure India Pvt. Ltd.", "Source code escrow", "Mumbai", "Advance", "A"),
    ("VND-1044", "Northstar Learning Academy", "Training", "Bengaluru", "Net 30", "B"),
    ("VND-1045", "Greenline Logistics", "Courier", "Bengaluru", "Net 15", "B"),
    ("VND-1046", "PowerGrid UPS Services", "Electrical maintenance", "Bengaluru", "Net 30", "B"),
    ("VND-1047", "Trinity Legal Advisors", "Legal services", "Bengaluru", "Net 45", "A"),
    ("VND-1048", "Orbit Furniture Works", "Office furniture", "Bengaluru", "Net 30", "B"),
    ("VND-1049", "PixelCraft Design Studio", "Design services", "Pune", "Net 30", "B"),
    ("VND-1050", "SafeHands Pest Control", "Pest control", "Bengaluru", "Net 15", "C"),
    ("VND-1051", "Zenith Telecom Services", "Telecom and internet", "Bengaluru", "Net 30", "A"),
    ("VND-1052", "Monsoon Events & Hospitality", "Events", "Bengaluru", "50% advance", "B"),
    ("VND-1053", "Quantum Software Resellers", "Software licences", "Hyderabad", "Net 30", "A"),
    ("VND-1054", "Sahyadri Water Solutions", "Drinking water", "Bengaluru", "Net 15", "C"),
    ("VND-1055", "Indus Recruitment Partners", "Recruitment", "Mumbai", "Net 45", "B"),
]
_STATE_CODE = {"Bengaluru": "29", "Mumbai": "27", "Pune": "27", "Chennai": "33", "Hyderabad": "36"}


def _vendor_rows():
    rows = [["Vendor ID", "Vendor Name", "Category", "City", "GSTIN", "Payment Terms", "Risk Rating",
             "Annual Spend FY2025-26 (INR)", "Contract Reference"]]
    for i, (vid, name, cat, city, terms, rating) in enumerate(_VENDORS):
        gstin = f"{_STATE_CODE[city]}AA{chr(65 + i % 26)}C{chr(70 + i % 20)}{4100 + i * 37:04d}{chr(65 + i % 9)}1Z{i % 10}"
        spend = 180000 + (i * 271_000) % 4_900_000
        contract = {"VND-1042": "CNT-2026-9491", "VND-1031": "PO-2026-3317", "VND-1048": "PO-2026-3371",
                    "VND-1035": "ENG-IA-2026"}.get(vid, "-")
        rows.append([vid, name, cat, city, gstin, terms, rating, f"{spend}", contract])
    return rows


doc("Approved_Vendor_Register.csv", "finance", "Approved Vendor Register FY2026-27",
    "25 approved vendors with vendor IDs (VND-10xx), category, GSTIN, payment terms, risk rating, spend and contract reference.",
    rows=_vendor_rows())

doc("Quarterly_Financial_Report_Q2_FY2026-27.pdf", "finance", "Quarterly Financial Report - Q2 FY2026-27",
    "Management report for July-September 2026: revenue, EBITDA, segment mix, headcount, cash and full-year guidance.",
    pages=[
        [
            H1("1. Highlights for the Quarter"),
            P("This report presents the unaudited results of Nimbus Technologies Pvt. Ltd. for the second quarter of "
              "financial year 2026-27, covering the period from 1 July 2026 to 30 September 2026. All amounts are in "
              "Indian Rupees; 1 crore equals 10 million."),
            UL("Revenue from operations of Rs. 48.6 crore, up 14.2% from Rs. 42.6 crore in Q2 FY2025-26.",
               "EBITDA of Rs. 9.7 crore, an EBITDA margin of 20.0% compared with 18.1% a year earlier.",
               "Profit after tax of Rs. 6.1 crore, up 22% year on year.",
               "27 new customers signed during the quarter, taking the active customer base to 312.",
               "Board approved the lease of a 12,500 sq ft office in Whitefield to support growth."),
            H1("2. Message from the CFO"),
            P("\"The second quarter was our strongest yet, driven by festive-season demand from retail customers and "
              "steady expansion of NimbusDesk subscriptions,\" said Ms. Radhika Iyengar, Chief Financial Officer. "
              "\"We improved margins despite wage increments effective 1 July, thanks to better utilisation and a "
              "higher share of recurring product revenue.\""),
        ],
        [
            H1("3. Revenue by Segment"),
            TABLE(["Segment", "Q2 FY2026-27 (Rs. crore)", "Q2 FY2025-26 (Rs. crore)", "Growth"],
                  ["Managed Services", "21.3", "19.4", "9.8%"],
                  ["NimbusDesk product subscriptions", "15.8", "12.6", "25.4%"],
                  ["Consulting and implementation", "11.5", "10.6", "8.5%"],
                  ["Total", "48.6", "42.6", "14.2%"]),
            P("Recurring revenue (managed services plus subscriptions) accounted for 76% of total revenue. The retail "
              "vertical contributed 38% of revenue, healthcare 24%, logistics 21% and others 17%. The top 10 customers "
              "contributed 41% of revenue, down from 46% a year ago, reducing concentration risk."),
            H1("4. Geographic Mix"),
            P("Domestic customers contributed 82% of revenue. Export revenue, mainly from customers in the United Arab "
              "Emirates and Singapore, was Rs. 8.7 crore, up 31% year on year."),
        ],
        [
            H1("5. Costs and Profitability"),
            P("Employee benefit expenses were Rs. 27.9 crore, or 57.4% of revenue. Cloud hosting costs rose to Rs. 3.4 "
              "crore as subscription volumes grew. Other operating expenses, including travel and facilities, were "
              "Rs. 7.6 crore. Depreciation and amortisation was Rs. 1.5 crore and the effective tax rate was 25.2%."),
            H1("6. People"),
            P("Total headcount was 1,184 employees as of 30 September 2026, compared with 1,092 at 30 June 2026. The "
              "company added 64 campus graduates during the quarter. Annualised voluntary attrition improved to 13.8% "
              "from 16.5% in the previous quarter. Utilisation in the services business was 81%."),
            H1("7. Working Capital"),
            P("Days sales outstanding (DSO) were 62 days, compared with 68 days at the end of Q1. Trade receivables "
              "stood at Rs. 33.0 crore, of which 8% were overdue by more than 90 days. The company has no long-term debt."),
        ],
        [
            H1("8. Cash Flow and Capital Expenditure"),
            P("Operating cash flow for the quarter was Rs. 7.8 crore. Capital expenditure was Rs. 2.3 crore, mainly on "
              "laptops for new joiners (purchase order PO-2026-3317) and fit-out advances for the Whitefield office. "
              "Cash and liquid investments at the end of the quarter were Rs. 32.4 crore."),
            H1("9. Outlook for FY2026-27"),
            P("Management reaffirms full-year revenue guidance of Rs. 195 crore to Rs. 205 crore and expects the EBITDA "
              "margin to remain between 19% and 21%. The third quarter will include the opening of the Whitefield office "
              "and the general availability of NimbusDesk 5.2 with AI ticket triage."),
            H1("10. Basis of Preparation"),
            P("Figures are prepared in accordance with Indian Accounting Standards (Ind AS) and are subject to review "
              "by the statutory auditors. This report is intended for the Board and shareholders and should not be "
              "distributed externally."),
        ],
    ])

_EXPENSE_CATS = [("Travel", "Flight BLR-BOM for customer workshop", 8450), ("Meals", "Team dinner after release", 3200),
                 ("Software", "Annual design tool subscription", 21240), ("Training", "Cloud certification exam fee", 15000),
                 ("Local conveyance", "Cab to customer site", 640), ("Hotel", "2 nights hotel Mumbai", 13800),
                 ("Internet", "Remote internet allowance", 1500), ("Client entertainment", "Lunch with client team", 5600)]
_LEDGER_EMP = [0, 1, 2, 10, 12, 13, 14, 16, 17, 18, 19, 21, 24, 28]


def _ledger_rows():
    rows = [["Entry ID", "Date", "Employee ID", "Employee Name", "Category", "Description", "Amount (INR)",
             "GST (INR)", "Cost Centre", "Approved By", "Status"]]
    for i in range(35):
        cat, desc, base = _EXPENSE_CATS[i % len(_EXPENSE_CATS)]
        e = _LEDGER_EMP[(i * 3) % len(_LEDGER_EMP)]
        amount = base + (i * 113) % 900
        gst = round(amount * 0.18) if cat in ("Software", "Hotel", "Training") else 0
        date = dt.date(2026, 7, 1) + dt.timedelta(days=(i * 5) % 92)
        status = "Rejected" if i % 11 == 7 else ("Pending" if i % 9 == 4 else "Paid")
        cc = {"Engineering": "CC-ENG-01", "Sales": "CC-SAL-02", "Customer Success": "CC-CS-03", "Product": "CC-PRD-04",
              "Data Science": "CC-DS-05", "Cloud Operations": "CC-CLD-06", "Marketing": "CC-MKT-07"}[_EMPLOYEES[e][1]]
        rows.append([f"EXP-2026-{601 + i:04d}", date.isoformat(), _emp_id(e), _EMPLOYEES[e][0], cat, desc,
                     str(amount), str(gst), cc, "Rajiv Bhandari" if amount > 10000 else "Line manager", status])
    return rows


doc("Expense_Ledger_Q2_2026.csv", "finance", "Employee Expense Ledger - Q2 FY2026-27",
    "35 employee expense entries (EXP-2026-06xx) for July-September 2026 with category, amount, GST, cost centre and status.",
    rows=_ledger_rows())

doc("Annual_Budget_FY2026-27.xlsx", "finance", "Annual Budget FY2026-27",
    "Board-approved department budgets (opex, capex, headcount) in INR lakh, with quarterly phasing.",
    sheets={
        "Department Budget": [
            ["Department", "Opex (INR lakh)", "Capex (INR lakh)", "Total (INR lakh)", "Planned Headcount", "Budget Owner"],
            ["Engineering", 6850, 410, 7260, 640, "Meera Krishnan"],
            ["Cloud Operations", 2240, 1180, 3420, 150, "Harish Venkataraman"],
            ["Data Science", 980, 260, 1240, 48, "Ananya Iyer"],
            ["Product", 720, 35, 755, 36, "Neha Joshi"],
            ["Sales", 1880, 40, 1920, 95, "Suresh Pillai"],
            ["Marketing", 960, 15, 975, 22, "Divya Nair"],
            ["Customer Success", 1310, 30, 1340, 120, "Sneha Kulkarni"],
            ["People Operations", 540, 10, 550, 18, "Kavitha Menon"],
            ["Finance & Legal", 610, 12, 622, 24, "Rajiv Bhandari"],
            ["IT & Facilities", 1460, 940, 2400, 31, "Sanjay Kumar Das"],
            ["Total", 17550, 2932, 20482, 1184, "Radhika Iyengar (CFO)"],
        ],
        "Quarterly Phasing": [
            ["Quarter", "Period", "Opex (INR lakh)", "Capex (INR lakh)", "Key items"],
            ["Q1", "Apr-Jun 2026", 4120, 520, "Annual increments planning; laptop refresh tranche 1"],
            ["Q2", "Jul-Sep 2026", 4310, 690, "Wage increments effective 1 July; PO-2026-3317 laptops"],
            ["Q3", "Oct-Dec 2026", 4480, 1240, "Whitefield office fit-out; GPU servers for AI triage"],
            ["Q4", "Jan-Mar 2027", 4640, 482, "Campus hiring; ISO 27001 recertification"],
            ["Total", "FY2026-27", 17550, 2932, "Approved by the Board on 18 March 2026"],
        ],
    })

doc("Purchase_Order_PO-2026-3317.docx", "finance", "Purchase Order PO-2026-3317",
    "Purchase order to Apex Compute Solutions for 40 laptops, docking stations and monitors with delivery and warranty terms.",
    blocks=[
        H1("Purchase Order Details"),
        TABLE(["Field", "Detail"], ["PO number", "PO-2026-3317"], ["PO date", "12 June 2026"],
              ["Supplier", "Apex Compute Solutions Pvt. Ltd. (vendor code VND-1031), 3rd Cross, Lalbagh Road, Bengaluru 560027"],
              ["Supplier GSTIN", "29AAACA4100A1Z0"], ["Requisition", "PR-2026-0884 raised by IT & Facilities"],
              ["Budget head", "Capex - IT hardware (Q2 FY2026-27)"], ["Buyer", "Sanjay Kumar Das, IT & Facilities"]),
        H1("Line Items"),
        TABLE(["#", "Item", "Quantity", "Unit price (₹)", "Amount (₹)"],
              ["1", "Dell Latitude 7440 laptop, Intel Core i7, 32 GB RAM, 1 TB SSD", "40", "1,12,500", "45,00,000"],
              ["2", "USB-C docking station with dual display support", "40", "14,200", "5,68,000"],
              ["3", "24-inch IPS monitor, height-adjustable stand", "20", "16,800", "3,36,000"],
              ["", "Subtotal", "", "", "54,04,000"],
              ["", "CGST 9% + SGST 9%", "", "", "9,72,720"],
              ["", "Grand total", "", "", "63,76,720"]),
        H1("Delivery"),
        P("Goods must be delivered to the IT store, Tower B, Lakeview Tech Park, Bellandur, Bengaluru no later than "
          "15 July 2026, between 10:00 AM and 5:00 PM on working days. Each laptop must be delivered with the company's "
          "standard Windows image pre-loaded, BIOS password set, and asset tags applied as per the list shared by IT. "
          "Partial deliveries are accepted only with written approval from the buyer."),
        H1("Warranty and Support"),
        UL("3 years of next-business-day onsite warranty on laptops, docking stations and monitors.",
           "Accidental damage protection for laptops for 3 years.",
           "Defective-on-arrival units to be replaced within 5 working days.",
           "Hard drives of failed units are retained by Nimbus (keep-your-drive)."),
        H1("Commercial Terms"),
        P("Prices are fixed and inclusive of delivery, insurance and installation. Payment will be released within 30 "
          "days of complete delivery, installation and receipt of a valid tax invoice quoting PO-2026-3317. A penalty "
          "of 0.5% of the order value per week of delayed delivery will apply, capped at 5%. This PO is governed by the "
          "Nimbus General Terms of Purchase version 3.2."),
        H1("Related Orders"),
        P("Ergonomic chairs and desks for the same batch of new joiners are ordered separately under PO-2026-3371 from "
          "Orbit Furniture Works and are not part of this order."),
        H1("Inspection and Acceptance"),
        P("The IT team will inspect every delivered unit within 3 working days of delivery, verify serial numbers "
          "against the delivery challan, and run a standard hardware diagnostic. Units that fail inspection will be "
          "rejected and must be collected by the supplier at its own cost. Acceptance is confirmed by a signed goods "
          "receipt note, which is a precondition for invoice processing."),
        H1("Authorisation"),
        P("Approved by Rajiv Bhandari, Finance Controller, and Arjun Bhatt, Chief Technology Officer, on 12 June 2026, "
          "in line with the delegation of authority matrix for capital purchases above ₹50 lakh."),
    ])

doc("Internal_Audit_Summary_2026.txt", "finance", "Internal Audit Summary Report IA-2026-03",
    "Summary of the FY2025-26 internal audit: scope, rating, high/medium/low observations and remediation deadlines.",
    blocks=[
        H1("1. Engagement Overview"),
        P("This summary presents the results of the internal audit of Nimbus Technologies Pvt. Ltd. for the period "
          "1 April 2025 to 31 March 2026, report reference IA-2026-03. The audit was carried out by Mehta Sharma & "
          "Associates, Chartered Accountants, between 4 May and 26 June 2026, and the report was presented to the Audit "
          "Committee on 21 July 2026."),
        H1("2. Scope"),
        UL("Procure-to-pay: vendor onboarding, purchase orders, invoice processing and payments.",
           "Order-to-cash: contract set-up, invoicing, collections and credit notes.",
           "Payroll and employee reimbursements.",
           "IT general controls: user access management, change management and backups.",
           "Statutory compliance: GST, TDS, PF and ESI."),
        H1("3. Overall Opinion"),
        P("The internal control environment was rated \"Satisfactory with improvement needed\". The auditors raised 14 "
          "observations in total: 2 rated high risk, 5 rated medium risk and 7 rated low risk. No instance of fraud was "
          "identified. Management has accepted all observations."),
        H1("4. High-Risk Observations"),
        P("Observation 1 - Duplicate vendor master records: 17 duplicate vendor records were found in the ERP vendor "
          "master, created with minor variations in name or GSTIN. Two of these duplicates had received payments "
          "totalling ₹3,46,500 against the same invoice numbers; both amounts have since been recovered. "
          "Recommendation: implement a GSTIN and PAN uniqueness check at vendor creation and perform a one-time "
          "clean-up. Owner: Rajiv Bhandari. Target date: 31 October 2026."),
        P("Observation 2 - User access reviews not performed: quarterly reviews of user access to the ERP and the "
          "production cloud console had not been performed for 3 consecutive quarters, and 9 accounts belonging to "
          "employees who had left were still active. Recommendation: automate de-provisioning through the HR system and "
          "perform reviews every quarter. Owner: Sanjay Kumar Das. Target date: 30 September 2026."),
        H1("5. Medium-Risk Observations"),
        UL("Purchase orders raised after the invoice date in 23 of 150 sampled transactions (after-the-fact POs).",
           "Credit notes above ₹1 lakh issued without CFO approval in 4 cases.",
           "Travel claims submitted after 60 days were paid in 11 cases, contrary to policy POL-HR-022.",
           "Restoration testing of backups not documented for the NimbusDesk database.",
           "Delays of up to 6 days in depositing TDS for two months, resulting in interest of ₹18,240."),
        H1("6. Low-Risk Observations"),
        P("Low-risk observations related to missing signatures on 3 vendor onboarding forms, outdated delegation of "
          "authority matrix references in the finance manual, inconsistent naming of cost centres, and minor gaps in "
          "fixed asset tagging at the Pune office. Details are provided in the full report."),
        H1("7. Status of Previous Year Observations"),
        P("Of the 12 observations raised in the previous audit (IA-2025-02), 10 have been closed and 2 remain open. "
          "The open items relate to the contract repository and are expected to close with the rollout of the "
          "contract management module."),
        H1("8. Next Steps"),
        P("All observations must be closed by 31 December 2026. The internal audit team will perform a follow-up review "
          "in January 2027 and report closure status to the Audit Committee meeting in February 2027."),
    ])

doc("GST_Compliance_Note.docx", "finance", "GST Compliance Note for Finance Team",
    "Internal note on GST registration, SAC codes and rates, e-invoicing, return deadlines, ITC reconciliation and RCM.",
    blocks=[
        H1("1. Purpose"),
        P("This note, prepared by Deepak Venkatesh, Tax & Compliance Lead, on 5 August 2026, summarises how Goods and "
          "Services Tax (GST) applies to the services of Nimbus Technologies Pvt. Ltd. and sets out the monthly "
          "compliance routine for the finance team. It should be read together with the statutory compliance "
          "checklist maintained by the Legal team."),
        H1("2. Registration"),
        P("The company is registered in Karnataka under GSTIN 29AAHCN4821K1Z5. The Pune development centre is "
          "registered separately in Maharashtra under GSTIN 27AAHCN4821K1Z9. Cross-charges between the two "
          "registrations for shared services are invoiced quarterly."),
        H1("3. Classification and Rates"),
        TABLE(["Service", "SAC code", "GST rate"],
              ["IT consulting, managed services and implementation", "998314", "18%"],
              ["NimbusDesk software subscriptions (SaaS)", "997331", "18%"],
              ["Training services", "999293", "18%"],
              ["Export of services (with LUT)", "As applicable", "0% (zero-rated)"]),
        P("For supplies within Karnataka, CGST at 9% and SGST at 9% are charged. For supplies to customers in other "
          "states, IGST at 18% is charged. Exports are made under a Letter of Undertaking (LUT) without payment of tax; "
          "the LUT for FY2026-27 was filed on 28 March 2026."),
        H1("4. E-invoicing"),
        P("As the company's aggregate turnover exceeds ₹5 crore, every B2B invoice must be reported to the Invoice "
          "Registration Portal (IRP) to obtain an Invoice Reference Number (IRN) and QR code before it is sent to the "
          "customer. Invoices must be reported within 30 days of the invoice date; the IRP will reject older invoices."),
        H1("5. Return Filing Calendar"),
        UL("GSTR-1 (outward supplies): by the 11th of the following month.",
           "GSTR-3B (summary return and tax payment): by the 20th of the following month.",
           "GSTR-9 (annual return) for FY2025-26: by 31 December 2026.",
           "GSTR-9C (reconciliation statement): by 31 December 2026."),
        H1("6. Input Tax Credit"),
        P("Input tax credit (ITC) may be claimed only when the supplier's invoice appears in GSTR-2B. The team must "
          "reconcile purchase registers with GSTR-2B every month by the 14th and follow up with vendors for missing "
          "invoices. ITC is not available on food and beverages, employee health insurance (unless statutorily "
          "required) and motor vehicles for personal use."),
        H1("7. Reverse Charge Mechanism"),
        P("GST on legal services received from advocates and law firms, and on sponsorship services, is paid by the "
          "company under the reverse charge mechanism. RCM liability must be paid in cash through GSTR-3B and cannot be "
          "set off against ITC."),
        H1("8. Interest and Penalties"),
        P("Late payment of GST attracts interest at 18% per annum on the net cash liability, calculated from the day "
          "after the due date. Late filing of GSTR-3B attracts a late fee of ₹50 per day (₹20 per day for nil returns). "
          "Excess ITC claimed and utilised attracts interest at 24% per annum."),
        H1("9. Contacts"),
        P("Queries may be addressed to tax@nimbustech.example. The company's external GST consultant is Trinity "
          "Legal Advisors (vendor VND-1047)."),
    ])

doc("Investor_Update_Q2.pptx", "finance", "Investor Update - Q2 FY2026-27",
    "Investor deck: quarterly financial highlights, SaaS metrics (ARR, NRR), customers, funding and outlook.",
    slides=[
        ("Investor Update - Q2 FY2026-27", "Nimbus Technologies Pvt. Ltd. | Quarter ended 30 September 2026 | Confidential"),
        ("Quarter at a Glance", [
            "Revenue of ₹48.6 crore, up 14.2% year on year",
            "EBITDA margin of 20.0%, up from 18.1% a year ago",
            "Profit after tax of ₹6.1 crore",
            "Operating cash flow of ₹7.8 crore; no debt on the balance sheet",
        ]),
        ("NimbusDesk SaaS Metrics", [
            "Annual recurring revenue (ARR) of ₹64 crore, up 29% year on year",
            "Net revenue retention (NRR) of 118% across subscription customers",
            "Gross logo churn of 4.1% over the trailing twelve months",
            "Average contract value of ₹20.5 lakh per year for enterprise customers",
        ]),
        ("Revenue Mix", [
            "Managed services: ₹21.3 crore, growing 9.8% year on year",
            "NimbusDesk subscriptions: ₹15.8 crore, growing 25.4% year on year - our fastest-growing line",
            "Consulting and implementation: ₹11.5 crore, growing 8.5% year on year",
            "Recurring revenue now 76% of the total, improving revenue visibility",
            "By vertical: retail 38%, healthcare 24%, logistics 21%, others 17%",
        ]),
        ("Customers and Go-to-Market", [
            "312 active customers, including 27 new logos added this quarter",
            "Largest wins: a retail chain with 140 stores and a logistics company with 6 warehouses",
            "Channel partners now source 18% of new bookings",
            "Expansion into the UAE and Singapore delivered ₹8.7 crore of export revenue",
        ]),
        ("Product Momentum", [
            "NimbusDesk 5.2 with AI ticket triage in beta with 14 customers",
            "WhatsApp channel and Hindi and Kannada language support planned for Q4 2026",
            "ISO/IEC 27001 surveillance audit scheduled for November 2026",
        ]),
        ("Funding and Capital", [
            "Series B round of ₹180 crore raised in March 2025, led by Bluepeak Ventures",
            "Cash and liquid investments of ₹32.4 crore at quarter end",
            "Runway of more than 30 months at the current burn rate in growth investments",
            "ESOP pool expanded to 8% of the fully diluted share capital",
        ]),
        ("People", [
            "Headcount of 1,184, with 64 campus graduates joining in the quarter",
            "Annualised voluntary attrition down to 13.8%",
            "New 12,500 sq ft Whitefield office opening in November 2026",
        ]),
        ("Outlook FY2026-27", [
            "Revenue guidance reaffirmed at ₹195 crore to ₹205 crore",
            "EBITDA margin expected between 19% and 21%",
            "Target of 400 active customers by March 2027",
            "Investor relations contact: ir@nimbustech.example",
        ]),
        ("Key Risks We Are Watching", [
            "Wage inflation for experienced cloud and AI engineers, partly offset by campus hiring",
            "Customer concentration in the retail vertical during festive seasons",
            "Regulatory changes under the DPDP Act affecting how customer data is processed",
            "Foreign exchange movements on the growing export revenue base",
            "Execution risk in opening the Whitefield office without disrupting delivery",
        ]),
    ])

# =========================================================================== #
#                                GENERAL (10)                                 #
# =========================================================================== #
doc("Resume_Ananya_Iyer.pdf", "general", "Ananya Iyer - Senior Data Scientist",
    "Resume of Ananya Iyer: 7 years in machine learning, churn and forecasting models, NLP, MLOps.",
    org="",
    pages=[
        [
            P("Bengaluru, Karnataka | ananya.iyer@mail.example | +91 98450 12345 | Open to senior and lead data science roles"),
            H1("Professional Summary"),
            P("Senior Data Scientist with 7 years of experience building machine learning products for customer "
              "service, retail and logistics. Experienced in taking models from prototype to production, leading small "
              "teams, and translating business problems into measurable experiments. Strong in NLP, time-series "
              "forecasting and causal inference, with hands-on MLOps on cloud platforms."),
            H1("Experience"),
            H2("Senior Data Scientist - Nimbus Technologies Pvt. Ltd., Bengaluru (August 2022 - present)"),
            UL("Lead a team of 4 data scientists building the AI ticket triage feature for the NimbusDesk platform; the "
               "classifier routes tickets to the right queue with 91% accuracy across 38 categories.",
               "Built a customer churn model for subscription accounts that helped the customer success team reduce "
               "churn by 18% over two quarters.",
               "Designed a retrieval-augmented knowledge assistant over 40,000 help articles, cutting average handling "
               "time for support agents by 23%.",
               "Introduced model monitoring with drift alerts and a monthly model review board."),
            H2("Data Scientist - Quantix Analytics, Pune (June 2019 - July 2022)"),
            UL("Developed demand-forecasting models for a grocery delivery client covering 2,300 SKUs, improving "
               "forecast accuracy (MAPE) from 31% to 19%.",
               "Built a route-time prediction service for a logistics client, deployed as a REST API serving 1.5 "
               "million requests per day.",
               "Mentored 3 interns, two of whom joined full-time."),
        ],
        [
            H1("Education"),
            UL("M.Tech in Computer Science (Machine Learning), Deccan Institute of Technology, 2019 - CGPA 8.9/10.",
               "B.E. in Information Science, Malnad College of Engineering Sciences, 2017 - First class with distinction."),
            H1("Skills"),
            UL("Languages: Python, SQL, Scala (basic).",
               "ML and NLP: scikit-learn, PyTorch, Hugging Face Transformers, sentence embeddings, LightGBM, Prophet.",
               "MLOps: Docker, Kubernetes, MLflow, Airflow, feature stores, CI/CD for models.",
               "Data: Spark, PostgreSQL, BigQuery, dbt; experimentation and A/B testing."),
            H1("Certifications"),
            UL("AWS Certified Machine Learning - Specialty (2023).",
               "Google Professional Data Engineer (2021)."),
            H1("Publications and Talks"),
            UL("\"Few-shot intent classification for multilingual support tickets\", Indian Conference on Applied NLP, 2024.",
               "Speaker at the Bengaluru Data Science Meetup on \"Monitoring models after go-live\", March 2025."),
            H1("Awards"),
            UL("Nimbus Star Performer award, FY2024-25.",
               "Winner of an internal hackathon at Quantix Analytics, 2020, for a warehouse slotting optimiser."),
            H1("Selected Projects"),
            UL("Knowledge assistant evaluation harness: built an offline benchmark of 1,200 labelled support questions to "
               "compare retrieval strategies before each release.",
               "Pro bono: built a dropout-risk model for a Bengaluru education non-profit using open data."),
            H1("Languages"),
            P("English (fluent), Tamil (native), Kannada (conversational), Hindi (conversational)."),
        ],
    ])

doc("Resume_Rohit_Deshmukh.docx", "general", "Rohit Deshmukh - DevOps Engineer",
    "Resume of Rohit Deshmukh: 5 years in DevOps and SRE, Kubernetes (CKA), CI/CD pipelines, cloud cost optimisation.",
    blocks=[
        P("Pune, Maharashtra | rohit.deshmukh@mail.example | +91 97300 54321 | github.com/rohit-d-ops (example)"),
        H1("Profile"),
        P("DevOps Engineer with 5 years of experience automating build, release and infrastructure for SaaS products. "
          "Comfortable owning production reliability end to end, from Terraform modules to on-call runbooks. "
          "Certified Kubernetes Administrator (CKA) with a strong focus on developer experience and cost efficiency."),
        H1("Experience"),
        H2("DevOps Engineer - Nimbus Technologies Pvt. Ltd., Pune (March 2023 - present)"),
        UL("Re-architected the CI/CD pipeline for the NimbusDesk monorepo using parallel test sharding and build "
           "caching, reducing the average release pipeline time from 45 minutes to 8 minutes.",
           "Migrated 64 microservices from virtual machines to managed Kubernetes with zero customer-facing downtime.",
           "Cut monthly cloud spend by 27% (about ₹11 lakh per month) through right-sizing, spot instances and "
           "scheduled shutdown of non-production environments.",
           "Introduced SLO-based alerting, reducing pager noise by 60%, and authored 40 runbooks.",
           "Member of the incident response team for INC-2026-0412; implemented automated certificate expiry monitoring "
           "as a corrective action."),
        H2("Systems Engineer - Bharat Freight Systems, Nashik (July 2021 - February 2023)"),
        UL("Automated server provisioning with Ansible for 120 Linux hosts.",
           "Set up centralised logging with the ELK stack, retaining 30 days of logs.",
           "Reduced backup restoration time from 6 hours to 90 minutes by moving to incremental snapshots."),
        H1("Technical Skills"),
        TABLE(["Area", "Tools"],
              ["Containers and orchestration", "Docker, Kubernetes, Helm, Argo CD"],
              ["Infrastructure as code", "Terraform, Ansible, Packer"],
              ["CI/CD", "GitHub Actions, Jenkins, GitLab CI"],
              ["Observability", "Prometheus, Grafana, OpenTelemetry, ELK"],
              ["Cloud", "AWS (EKS, RDS, IAM, VPC), basic Azure"],
              ["Scripting", "Bash, Python, Go (basic)"]),
        H1("Certifications"),
        UL("Certified Kubernetes Administrator (CKA), 2024.",
           "HashiCorp Certified: Terraform Associate, 2023."),
        H1("Education"),
        P("B.E. in Computer Engineering, Pune Institute of Engineering Sciences, 2021, CGPA 8.2/10. Final-year project: "
          "a self-healing deployment controller for edge devices."),
        H1("Key Projects"),
        UL("Self-service environments: built a platform that lets developers spin up a full preview environment for any "
           "pull request in under 6 minutes, used by more than 90 engineers every week.",
           "Disaster recovery: designed cross-region backups for the NimbusDesk database with a recovery point objective "
           "of 15 minutes and ran the first full failover drill.",
           "Secrets management: moved application secrets from configuration files to a central vault with automatic "
           "rotation, removing 300+ hard-coded credentials from repositories."),
        H1("Achievements"),
        UL("Nimbus \"Unsung Hero\" award for the zero-downtime Kubernetes migration, 2024.",
           "Speaker at a regional DevOps meetup in Pune on \"Pipelines under 10 minutes\", 2025."),
        H1("Languages"),
        P("English (fluent), Marathi (native), Hindi (fluent). Notice period: 60 days."),
    ])

doc("Product_Roadmap_2026-27.pptx", "general", "NimbusDesk Product Roadmap 2026-27",
    "Product roadmap deck: release plan (5.2, 5.3, 6.0), AI triage, channels, languages, deprecations and targets.",
    slides=[
        ("NimbusDesk Product Roadmap 2026-27", "Product Management | Neha Joshi | Updated 1 September 2026"),
        ("Vision and Themes", [
            "Make every support agent 30% more productive through AI assistance",
            "Meet customers on the channels they already use",
            "Enterprise-grade trust: security, compliance and 99.95% uptime",
            "Build for Bharat: Indian languages and low-bandwidth experiences",
        ]),
        ("Release 5.2 - Q3 2026 (October)", [
            "AI ticket triage: automatic category, priority and queue prediction",
            "Suggested replies grounded in the customer's knowledge base",
            "SLA breach prediction alerts for supervisors",
            "General availability on 27 October 2026",
        ]),
        ("Release 5.3 - Q4 2026 (December)", [
            "WhatsApp Business channel integration",
            "Hindi and Kannada language support in the agent and customer portals",
            "Offline field-service app built on the Project Sentinel SDK",
            "Custom report builder with scheduled email delivery",
        ]),
        ("Release 6.0 - Q1 2027 (March)", [
            "Multi-tenant analytics warehouse with 2 years of history",
            "Workflow automation studio with no-code triggers and actions",
            "Data residency options for UAE and Singapore customers",
            "Database platform upgrade to PostgreSQL 16",
        ]),
        ("Deprecations", [
            "On-premise NimbusDesk 3.x reaches end of support on 31 March 2027",
            "Legacy SOAP API retired on 30 June 2027; customers must move to REST API v4",
            "Internet Explorer mode no longer supported from release 5.2",
        ]),
        ("Success Metrics for FY2026-27", [
            "Platform uptime of 99.95% measured monthly",
            "AI triage adoption by 60% of active customers within 6 months of GA",
            "Median first-response time reduced by 25% for customers using AI features",
            "Net Promoter Score of 45 or above",
        ]),
        ("What Customers Are Asking For", [
            "Faster answers for agents: suggested replies and knowledge search were the top requests in the 2026 survey",
            "Better reporting: supervisors want custom dashboards without exporting data to spreadsheets",
            "Regional languages: retail and logistics customers serve large Hindi- and Kannada-speaking audiences",
            "Mobile-first field service: technicians often work in areas with weak connectivity",
        ]),
        ("Release Governance", [
            "Every release goes through a beta with at least 10 customers before general availability",
            "Feature flags allow gradual rollout and instant rollback without redeployment",
            "Release notes are published on the customer portal 2 weeks before each release",
            "Breaking API changes require 6 months' notice to customers",
            "A product council of 8 enterprise customers reviews the roadmap every quarter",
        ]),
        ("Dependencies and Risks", [
            "GPU capacity for AI features depends on the Q3 capex approval of 6 GPU instances",
            "WhatsApp channel subject to Meta business verification for each customer",
            "Language models for Kannada need an additional 50,000 labelled tickets",
            "PostgreSQL 16 upgrade must complete before analytics warehouse work starts in January 2027",
            "Hiring of 4 additional mobile engineers for the offline field-service app",
        ]),
    ])

doc("Meeting_Minutes_Engineering_Sync.txt", "general", "Minutes of Meeting - Weekly Engineering Sync (MOM-ENG-2026-41)",
    "Engineering sync minutes: release 5.2 code freeze, PostgreSQL 16 migration decision, on-call changes and action items.",
    blocks=[
        H1("Meeting Details"),
        UL("Reference: MOM-ENG-2026-41",
           "Date and time: Wednesday, 9 September 2026, 11:00 AM - 12:15 PM IST",
           "Location: Conference room Kaveri, 4th floor, Tower B, and video bridge",
           "Chair: Meera Krishnan, Director - Engineering",
           "Minutes recorded by: Fatima Sheikh, QA Engineer"),
        H1("Attendees"),
        P("Meera Krishnan, Vikram Sethi, Harish Venkataraman, Karthik Subramanian, Rohit Deshmukh, Ananya Iyer, Neha "
          "Joshi, Pooja Reddy, Fatima Sheikh and Sanjay Kumar Das. Apologies: Aarav Sharma (on leave)."),
        H1("1. Release 5.2 Status"),
        P("Neha Joshi reported that 41 of 46 stories planned for release 5.2 are complete. The AI ticket triage model "
          "achieves 91% accuracy in the beta with 14 customers. Two defects of severity 2 remain open in the suggested "
          "replies feature. The team agreed that the code freeze for release 5.2 will be on 25 September 2026, with "
          "general availability on 27 October 2026. Pooja Reddy will complete the accessibility fixes before the freeze."),
        H1("2. Database Migration"),
        P("Vikram Sethi presented the evaluation of PostgreSQL 16 against the current PostgreSQL 12 cluster. Benchmarks "
          "showed 18% faster reporting queries and lower replication lag. Decision: the production NimbusDesk database "
          "will be migrated to PostgreSQL 16 by 30 November 2026, using logical replication to keep downtime under 15 "
          "minutes. Vikram Sethi owns the migration plan, and the rehearsal will be run in staging during the week of "
          "26 October."),
        H1("3. GPU Capacity for AI Features"),
        P("Ananya Iyer requested 6 GPU instances for model training and inference for AI triage. The estimated cost "
          "is ₹14 lakh for the rest of the financial year. Meera Krishnan approved the request subject to Finance "
          "sign-off, and asked Harish Venkataraman to set up auto-scaling so that idle instances are shut down at night."),
        H1("4. On-call and Reliability"),
        P("Following incident INC-2026-0412, Rohit Deshmukh confirmed that automated certificate expiry monitoring is "
          "live, with alerts 30, 14 and 3 days before expiry. The on-call rotation will change from two weeks to one "
          "week per engineer from 1 October 2026 to reduce fatigue, and each on-call engineer will get a compensatory "
          "day off after their rotation."),
        H1("5. Security"),
        P("Sanjay Kumar Das reminded the team that the ISO/IEC 27001 surveillance audit is scheduled for 18 November "
          "2026 and that all engineers must complete the secure coding refresher by 31 October 2026."),
        H1("Action Items"),
        TABLE(["#", "Action", "Owner", "Due date"],
              ["1", "Prepare and rehearse the PostgreSQL 16 migration plan", "Vikram Sethi", "30-Nov-2026"],
              ["2", "Close the two severity-2 defects in suggested replies", "Karthik Subramanian", "22-Sep-2026"],
              ["3", "Accessibility fixes for the agent console", "Pooja Reddy", "24-Sep-2026"],
              ["4", "Raise capex request for 6 GPU instances", "Ananya Iyer", "16-Sep-2026"],
              ["5", "Configure GPU auto-scaling and night shutdown", "Harish Venkataraman", "30-Sep-2026"],
              ["6", "Publish new one-week on-call roster", "Rohit Deshmukh", "25-Sep-2026"]),
        H1("Next Meeting"),
        P("Wednesday, 16 September 2026, 11:00 AM IST, same location."),
    ])

SCANNED_PAGES = [
    [
        "# NIMBUS TECHNOLOGIES PVT. LTD.",
        "# IT Security and Visitor Access Policy - Notice ITS-2026-05",
        "Issued by: Sanjay Kumar Das, IT Security Analyst, on behalf of the Information Security Steering Committee. "
        "Effective from 1 June 2026. This notice is displayed at all reception desks and must be followed by all "
        "employees, contractors and visitors.",
        "# Part A - Visitor Access",
        "1. Every visitor must register at the Tower B reception and show a government photo identity card. "
        "Walk-in visitors without a host employee are not permitted beyond the reception area.",
        "2. Visitors receive a numbered orange visitor badge, which must be worn visibly at all times. The badge "
        "is valid only for the date of issue and must be returned at reception before leaving.",
        "3. Visitors must be escorted by their host employee at all times inside the office. Visitors are not "
        "allowed in the server room, the network operations centre or the finance records room.",
        "4. Photography and video recording inside the office are prohibited for visitors unless approved in "
        "writing by the Facilities Manager.",
        "5. The visitor register, including CCTV footage of the reception area, is retained for 180 days and then "
        "securely deleted.",
        "6. Visitor laptops must be declared at reception with their serial number. Visitors may connect only to "
        "the guest Wi-Fi network NIMBUS-GUEST. Guest Wi-Fi vouchers are valid for 8 hours.",
    ],
    [
        "# Part B - IT Security Rules for Employees",
        "7. Passwords must be at least 14 characters long and must be changed every 90 days. The last 5 passwords "
        "cannot be reused. Multi-factor authentication is mandatory for email, VPN and all customer systems.",
        "8. USB storage devices are blocked on all company laptops. Exceptions require approval from the IT Security "
        "team and are valid for a maximum of 7 days.",
        "9. Laptops must be locked when unattended. Screens lock automatically after 5 minutes of inactivity.",
        "10. Company data must never be uploaded to personal cloud storage or public AI chat tools.",
        "11. Report phishing emails using the Report Phish button. Report lost laptops or suspected security "
        "incidents immediately to the Security Operations desk on extension 4455, available 24 x 7.",
        "12. Tailgating through access-controlled doors is not allowed. Each employee must swipe their own card.",
        "# Part C - Compliance",
        "Violations of this notice may lead to disciplinary action under the Code of Conduct. Visitor-related "
        "violations will be recorded by the security supervisor and reported to the host employee's manager.",
        "Approved by: Arjun Bhatt, Chief Technology Officer. Next review: May 2027.",
    ],
]

doc("IT_Security_Policy_Scanned.pdf", "general", "IT Security and Visitor Access Policy (Scanned Notice ITS-2026-05)",
    "Scanned image-only notice (requires OCR): visitor badges, escort rules, visitor log retention, password and USB rules.",
    scanned_pages=SCANNED_PAGES)

doc("Incident_Postmortem_INC-2026-0412.docx", "general", "Incident Postmortem: INC-2026-0412 NimbusDesk API Outage",
    "Blameless postmortem of the 14 August 2026 NimbusDesk outage caused by an expired TLS certificate.",
    blocks=[
        H1("Summary"),
        P("On Friday, 14 August 2026, the NimbusDesk platform suffered a partial outage lasting 2 hours and 47 minutes, "
          "from 10:12 AM to 12:59 PM IST. During this time customers could not log in to the agent console, and email "
          "and web tickets were queued but not processed. The incident was classified as P1 and tracked as INC-2026-0412. "
          "This postmortem follows the blameless format. It should not be confused with INC-2026-0421, a minor "
          "reporting delay on 19 August 2026 caused by a slow analytics query."),
        H1("Impact"),
        UL("38% of active customers were affected, primarily those served through the Mumbai region.",
           "4,210 customer tickets were delayed by more than 30 minutes.",
           "SLA service credits of ₹6.2 lakh were issued to 9 customers, including Orchid Retail Ventures.",
           "No data was lost or exposed."),
        H1("Root Cause"),
        P("The root cause was an expired TLS certificate on the internal API gateway that terminates traffic between "
          "the web tier and the authentication service. The certificate had been issued manually two years earlier and "
          "was not managed by the automated certificate renewal system. When it expired at 10:00 AM, the web tier "
          "rejected connections to the authentication service, so new logins failed and background workers could not "
          "obtain tokens."),
        H1("Timeline (IST)"),
        TABLE(["Time", "Event"],
              ["10:00 AM", "Internal gateway certificate expires"],
              ["10:12 AM", "Synthetic login monitor fails; on-call engineer paged"],
              ["10:31 AM", "Incident declared P1; status page updated"],
              ["11:20 AM", "Investigation narrows to authentication service connectivity"],
              ["12:05 PM", "Expired certificate identified by Rohit Deshmukh"],
              ["12:41 PM", "New certificate deployed to the gateway"],
              ["12:59 PM", "Ticket queues drained; incident resolved"]),
        H1("What Went Well"),
        UL("The synthetic login monitor detected the problem within 12 minutes.",
           "Customer communication through the status page was updated every 30 minutes.",
           "Queued tickets were processed without loss once service was restored."),
        H1("What Went Wrong"),
        UL("The certificate was outside automated renewal and had no expiry alert.",
           "Error messages in the web tier logged a generic connection failure, which slowed diagnosis.",
           "The on-call runbook did not include certificate checks."),
        H1("Corrective Actions"),
        TABLE(["#", "Action", "Owner", "Status"],
              ["1", "Move all internal certificates to automated renewal", "Harish Venkataraman", "Done"],
              ["2", "Alert 30, 14 and 3 days before any certificate expires", "Rohit Deshmukh", "Done"],
              ["3", "Improve TLS error logging in the web tier", "Karthik Subramanian", "In progress"],
              ["4", "Add certificate checks to the P1 runbook", "Vikram Sethi", "Done"]),
        H1("Lessons Learned"),
        P("Manual exceptions to automation become hidden risks over time. All infrastructure secrets and certificates "
          "must now be inventoried quarterly, and any manual exception must have an owner and an expiry alert."),
    ])

doc("User_Manual_NimbusDesk.html", "general", "NimbusDesk 5.1 User Manual",
    "End-user manual for NimbusDesk 5.1: requirements, roles, tickets, SLAs, attachments, shortcuts and exports.",
    blocks=[
        H1("1. Introduction"),
        P("NimbusDesk is a service-management platform used by support teams to receive, track and resolve customer "
          "requests across email, web, chat and phone. This manual covers version 5.1 for agents, supervisors and "
          "administrators. For API documentation, see the developer portal."),
        H1("2. System Requirements"),
        UL("Google Chrome 120 or later, Microsoft Edge 120 or later, or Firefox 121 or later.",
           "Minimum screen resolution of 1366 x 768.",
           "A stable internet connection of at least 2 Mbps per agent.",
           "Pop-ups must be allowed for the NimbusDesk domain to receive call notifications."),
        H1("3. User Roles"),
        TABLE(["Role", "Can do"],
              ["Agent", "View and update assigned tickets, reply to customers, use macros"],
              ["Supervisor", "Everything an agent can do, plus reassign tickets, view team dashboards and approve refunds"],
              ["Administrator", "Configure queues, SLAs, users, integrations and data exports"]),
        H1("4. Signing In"),
        P("Sign in with your work email and password or through single sign-on. After 5 failed attempts the account is "
          "locked for 15 minutes. A password reset link is valid for 30 minutes. Sessions expire after 12 hours of "
          "inactivity."),
        H1("5. Working with Tickets"),
        P("Create a ticket from the New button or by pressing N. Every ticket has a unique number in the format "
          "ND-YYYY-NNNNNN. Ticket statuses are New, Open, Pending, On Hold, Resolved and Closed. Resolved tickets close "
          "automatically after 72 hours if the customer does not reply."),
        P("Files can be attached to tickets by drag-and-drop. The maximum attachment size is 25 MB per file and 10 files "
          "per reply. Executable files (.exe, .bat, .msi) are blocked for security reasons."),
        H1("6. SLA Timers"),
        P("Each ticket displays a first-response timer and a resolution timer based on its priority and the customer's "
          "SLA policy. Timers turn amber when 75% of the allowed time has elapsed and red when breached. Timers pause "
          "while a ticket is in Pending status waiting for the customer."),
        H1("7. Keyboard Shortcuts"),
        TABLE(["Shortcut", "Action"],
              ["Ctrl + K", "Open the command palette"], ["N", "New ticket"], ["R", "Reply to customer"],
              ["Shift + I", "Add internal note"], ["Ctrl + Enter", "Send reply"], ["G then Q", "Go to queues"]),
        H1("8. Reports and Exports"),
        P("Supervisors and administrators can export ticket lists to CSV from any view. A single export is limited to "
          "50,000 rows; larger exports should be scheduled from the Reports module and are delivered by email as a "
          "secure link valid for 7 days."),
        H1("9. Getting Help"),
        P("Use the in-app Help button to search the knowledge base or raise a request with Nimbus support. Standard "
          "support hours are 9:00 AM to 6:00 PM IST on weekdays; customers with the premium add-on receive 24x7 support."),
    ])

doc("Company_Newsletter_Oct_2026.html", "general", "Nimbus Pulse - Company Newsletter, October 2026 (Issue 18)",
    "Internal newsletter: Whitefield office opening, HackNimbus 2026 winners, CSR drive, awards and new joiners.",
    blocks=[
        H1("From the CEO's Desk"),
        P("Dear Nimbians, the festive season has brought record numbers for us. Our second quarter revenue grew 14.2% "
          "and we welcomed 64 new colleagues from campus. Thank you for the energy you bring every day. Wishing you and "
          "your families a joyful Deepavali. - Vivek Ramachandran, Chief Executive Officer"),
        H1("Our New Whitefield Office Opens on 2 November"),
        P("Our second Bengaluru office, on the 3rd floor of Greenfield Enclave on ITPL Main Road, Whitefield, opens on "
          "2 November 2026. The 12,500 sq ft space has 220 workstations, 14 meeting rooms, a podcast studio and a "
          "wellness room. The Cloud Operations and Data Science teams will move first. A shuttle will run every 30 "
          "minutes between the Bellandur and Whitefield offices from 8:00 AM to 8:00 PM."),
        H1("HackNimbus 2026: And the Winner Is..."),
        P("Forty-two teams took part in HackNimbus 2026, our annual 36-hour hackathon, held on 19 and 20 September. The "
          "winning team, ByteBrigade, built a voice-based ticket logging assistant in Kannada and Hindi for field "
          "technicians, and took home the first prize of ₹2,50,000. The runner-up, Team QueueBusters, built a tool that "
          "predicts SLA breaches from ticket text, and the People's Choice award went to Team GreenOps for a cloud carbon "
          "dashboard."),
        UL("Winner: ByteBrigade - ₹2,50,000",
           "Runner-up: QueueBusters - ₹1,25,000",
           "People's Choice: GreenOps - ₹50,000"),
        H1("CSR: 5,000 Saplings Planted"),
        P("Over three weekends in August, 380 employee volunteers planted 5,000 native saplings near Hesaraghatta lake "
          "in partnership with a local environmental trust. Volunteers will return in February to check on survival rates."),
        H1("Employee of the Quarter"),
        P("Sneha Kulkarni, Customer Success Manager, is our Employee of the Quarter for leading the peak-season "
          "readiness programme for Orchid Retail Ventures, which handled a record 3.2 lakh orders during the festive sale "
          "weekend without a single P1 incident."),
        H1("Welcome Aboard"),
        P("We welcomed 64 new joiners this quarter across Engineering, Cloud Operations and Customer Success. Please say "
          "hello when you see a new face at the cafeteria."),
        H1("Upcoming Events"),
        TABLE(["Date", "Event", "Venue"],
              ["31 October 2026", "Deepavali celebration and rangoli competition", "Bellandur cafeteria"],
              ["2 November 2026", "Whitefield office opening ceremony", "Greenfield Enclave"],
              ["14 November 2026", "Children's Day family open house", "Both offices"],
              ["5 December 2026", "Annual sports day", "Sports arena, Sarjapur Road"]),
        P("Have a story to share? Write to pulse@nimbustech.example."),
    ])

doc("Project_Proposal_SmartClaims.pptx", "general", "Project Proposal: SmartClaims AI Claims Automation",
    "Proposal deck for SmartClaims, an AI claims-processing solution for Suraksha Shield General Insurance: scope, budget, timeline.",
    slides=[
        ("Project Proposal: SmartClaims", "Prepared by Nimbus Technologies for Suraksha Shield General Insurance Ltd. | 4 August 2026"),
        ("The Problem", [
            "Motor and health claims currently take an average of 9 days from intimation to settlement decision",
            "38% of claims need at least one manual follow-up for missing documents",
            "Claims staff spend about 40% of their time re-keying data from scanned forms",
            "Customer satisfaction for claims stands at 3.4 out of 5",
        ]),
        ("Proposed Solution", [
            "Document intelligence to extract data from claim forms, bills and discharge summaries with OCR",
            "Automatic completeness checks that request missing documents through WhatsApp and email",
            "Rules plus machine-learning fraud scoring for every claim",
            "Claims workbench built on the NimbusDesk platform for adjusters",
        ]),
        ("Expected Outcomes", [
            "Reduce average claim processing time from 9 days to 2 days for straight-through claims",
            "Automate 60% of document data entry",
            "Flag high-risk claims for investigation within 1 hour of submission",
            "Raise claims customer satisfaction to 4.2 out of 5",
        ]),
        ("Delivery Plan - 7 Months", [
            "Phase 1 (Months 1-2): discovery, data access and OCR model tuning",
            "Phase 2 (Months 3-5): build of the workbench, integrations with the core policy system",
            "Phase 3 (Months 6-7): pilot with the motor claims team in Bengaluru, then rollout",
            "Dedicated team of 12: 1 delivery lead, 5 engineers, 3 data scientists, 2 QA, 1 business analyst",
        ]),
        ("Investment", [
            "Total project budget requested: ₹1.85 crore",
            "Build and implementation: ₹1.32 crore",
            "Cloud infrastructure and licences for year one: ₹38 lakh",
            "Change management and training: ₹15 lakh",
            "Payment milestones: 20% at kickoff, 40% at UAT sign-off, 40% at go-live",
        ]),
        ("Risks and Mitigations", [
            "Poor scan quality of legacy forms - mitigated by image pre-processing and human-in-the-loop review",
            "Integration delays with the core policy system - mitigated by early API sandbox access",
            "Regulatory requirements on data privacy - all data hosted in India and processed under a DPA",
        ]),
        ("Why Nimbus", [
            "More than 300 customers run their service operations on NimbusDesk today",
            "Proven document intelligence and AI triage capabilities already in production",
            "ISO/IEC 27001 certified delivery centres in Bengaluru and Pune with India-only data hosting",
            "Experience delivering for healthcare and logistics customers with strict data processing agreements",
            "A fixed-price commitment for the build phase, so budget risk stays with Nimbus",
        ]),
        ("Next Steps", [
            "Approval of the proposal by the client steering committee by 30 August 2026",
            "Signing of the Statement of Work under a new Master Services Agreement",
            "Kickoff workshop planned for the week of 14 September 2026",
            "Nimbus point of contact: Sneha Kulkarni, Customer Success Manager, with Ananya Iyer as data science lead",
        ]),
    ])

_INVENTORY = [
    ("Dell Latitude 7440 laptop", "IT hardware", "VND-1031", 112500),
    ("MacBook Pro 14-inch (design team)", "IT hardware", "VND-1053", 189900),
    ("24-inch IPS monitor", "IT peripherals", "VND-1031", 16800),
    ("USB-C docking station", "IT peripherals", "VND-1031", 14200),
    ("Noise-cancelling USB headset", "IT peripherals", "VND-1031", 6400),
    ("Wireless keyboard and mouse combo", "IT peripherals", "VND-1031", 2350),
    ("4G USB data dongle", "IT peripherals", "VND-1051", 1800),
    ("Laptop backpack with Nimbus logo", "Merchandise", "VND-1041", 1450),
    ("Nimbus hoodie (assorted sizes)", "Merchandise", "VND-1041", 950),
    ("Steel water bottle with logo", "Merchandise", "VND-1041", 420),
    ("Ergonomic office chair", "Furniture", "VND-1048", 18500),
    ("Height-adjustable desk", "Furniture", "VND-1048", 32000),
    ("Visitor badge holder (orange)", "Security supplies", "VND-1037", 35),
    ("Employee access card (blank)", "Security supplies", "VND-1037", 120),
    ("A4 copier paper (ream of 500)", "Stationery", "VND-1036", 285),
    ("Whiteboard marker set", "Stationery", "VND-1036", 180),
    ("Spiral notebook A5", "Stationery", "VND-1036", 65),
    ("HDMI to USB-C adapter", "IT peripherals", "VND-1031", 1150),
    ("Cat6 patch cable 2 m", "Networking", "VND-1051", 210),
    ("Wi-Fi 6 access point", "Networking", "VND-1051", 24500),
    ("Rack-mount UPS 3 kVA", "Electrical", "VND-1046", 68000),
    ("First-aid kit (office)", "Safety", "VND-1036", 1250),
    ("Fire extinguisher CO2 4.5 kg", "Safety", "VND-1046", 5200),
    ("Hand sanitiser 500 mL", "Housekeeping", "VND-1042", 210),
    ("Tissue box (pack of 12)", "Housekeeping", "VND-1042", 540),
    ("Coffee beans 1 kg", "Pantry", "VND-1034", 1350),
    ("Green tea bags (box of 100)", "Pantry", "VND-1034", 390),
    ("Conference speakerphone", "IT peripherals", "VND-1053", 21500),
    ("Webcam 1080p", "IT peripherals", "VND-1031", 4300),
    ("Encrypted USB drive 64 GB (approved exceptions)", "IT peripherals", "VND-1053", 3900),
]


def _inventory_rows():
    rows = [["SKU", "Item Description", "Category", "Location", "Quantity On Hand", "Reorder Level",
             "Unit Cost (INR)", "Supplier Vendor ID", "Last Stock Check"]]
    for i, (item, cat, vendor, cost) in enumerate(_INVENTORY):
        loc = ["Bellandur IT store", "Bellandur basement store", "Pune office store"][i % 3]
        qty = (i * 29 + 7) % 140 + 3
        reorder = 10 + (i * 7) % 40
        rows.append([f"NIM-SKU-{1031 + i}", item, cat, loc, str(qty), str(reorder), str(cost), vendor,
                     (dt.date(2026, 9, 1) + dt.timedelta(days=i % 20)).isoformat()])
    return rows


doc("Product_Inventory.csv", "general", "Office Inventory Register (September 2026)",
    "30 inventory SKUs (NIM-SKU-10xx) for IT hardware, peripherals, merchandise and supplies with stock, reorder level and cost.",
    rows=_inventory_rows())


# =========================================================================== #
#                                    Main                                     #
# =========================================================================== #
EVAL_PATH = ROOT / "evaluation" / "eval_dataset.json"


def _write_eval_dataset(generated, corpus_size):
    """Keep the 50 hand-written questions and (re)append the generated ones after them"""
    data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    cases = [c for c in data["test_cases"] if c.get("source") != "generated"]
    for i, g in enumerate(generated, start=len(cases) + 1):
        cases.append({"id": f"Q{i:03d}", "source": "generated", **g})
    for c in cases:  # uniform ids (Q001...) and field order
        c["id"] = f"Q{int(c['id'][1:]):03d}"
    meta = data["benchmark_metadata"]
    meta["total_questions"] = len(cases)
    meta["corpus_size"] = corpus_size
    cats = {}
    for c in cases:
        cats[c["category"]] = cats.get(c["category"], 0) + 1
    meta["categories"] = cats
    meta["description"] = (f"{len(cases)} questions over the {corpus_size}-document fictional corpus generated by "
                           "scripts/generate_sample_data.py (10 organisations x 20 documents). The first 50 questions "
                           "are hand-written; the rest are generated together with their documents "
                           "(source = generated). answer_keywords are case-insensitive substrings that must appear in "
                           "a correct answer; expected_page is the PDF page or PPTX slide number.")
    data["test_cases"] = cases
    EVAL_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} benchmark questions ({len(generated)} generated) to {EVAL_PATH}")


def main():
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    for d in DOMAINS:
        (OUT_DIR / d).mkdir(parents=True)

    specs = [rebrand(d) for d in DOCS]
    assert len(specs) == 50, len(specs)
    from corpus_expansion import DOCS_PER_ORG, PROFILES, expand

    def strings(o):
        if isinstance(o, str):
            yield o
        elif isinstance(o, dict):
            for v in o.values():
                yield from strings(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                yield from strings(v)

    extra_specs, extra_questions = expand(specs, " ".join(strings(specs)))
    specs += extra_specs
    names = [d["filename"] for d in specs]
    assert len(specs) == DOCS_PER_ORG * len(PROFILES), len(specs)
    assert len(set(names)) == len(names), "duplicate filenames"
    _write_eval_dataset(extra_questions, len(specs))

    manifest = []
    for spec in specs:
        path = OUT_DIR / spec["domain"] / spec["filename"]
        _render(spec, path)
        manifest.append({k: spec[k] for k in ("filename", "domain", "format", "title", "description")})

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    by_domain, by_format = {}, {}
    for m in manifest:
        by_domain[m["domain"]] = by_domain.get(m["domain"], 0) + 1
        by_format[m["format"]] = by_format.get(m["format"], 0) + 1
    print(f"Wrote {len(manifest)} documents to {OUT_DIR}")
    print("By domain:", by_domain)
    print("By format:", by_format)


if __name__ == "__main__":
    main()
