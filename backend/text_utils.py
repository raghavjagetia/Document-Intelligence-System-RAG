"""Shared text helpers"""
import re
from pathlib import Path
from typing import List

# Abbreviations that end with a period but do not end a sentence
ABBREVIATIONS = [
    "Pvt", "Ltd", "Rs", "No", "Nos", "Dr", "Mr", "Mrs", "Ms", "Prof", "Co", "Inc", "Corp", "St", "Sr", "Jr",
    "vs", "approx", "Fig", "Ref", "Rev", "Govt", "Dept", "Ave", "Rd", "Sec", "Cl", "Art", "Vol", "Est", "Max",
    "Min", "Mt", "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec", "e.g", "i.e",
    "etc", "Ph.D", "B.Tech", "M.Tech", "U.S",
]
_ABBR_RE = re.compile(r"\b(" + "|".join(re.escape(a) for a in ABBREVIATIONS) + r")\.(?=\s)")
_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9₹(\"'])")
_PLACEHOLDER = "․"  # one-dot leader, restored after splitting


def split_prose(text: str) -> List[str]:
    """Split prose into sentences without breaking on abbreviations like 'Pvt. Ltd.' or 'Rs. 500'"""
    protected = _ABBR_RE.sub(lambda m: m.group(1) + _PLACEHOLDER, text)
    # list / clause numbers such as "3. Item" or "4.2. Rent"
    protected = re.sub(r"(?:(?<=\s)|^)(\d{1,2}(?:\.\d{1,2})*)\.(?=\s)", lambda m: m.group(1) + _PLACEHOLDER, protected)
    return [s.replace(_PLACEHOLDER, ".").strip() for s in _SPLIT_RE.split(protected) if s.strip()]


def doc_title(filename: str) -> str:
    """Human-readable document title used as chunk context: 'Invoice_INV-2026-8842.pdf' -> 'Invoice INV-2026-8842'"""
    return Path(filename or "").stem.replace("_", " ").strip()
