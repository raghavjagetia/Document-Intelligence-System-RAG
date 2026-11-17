"""
Intelligent Structure-Aware Chunking Module
Implements hierarchical, structure-aware chunking:
Document -> Section -> Subsection -> Paragraph -> Table -> Chunk
Preserves sentence boundaries, page numbers, element types, and table relationships.
"""
import re
from typing import List, Dict, Any, Optional

from .text_utils import split_prose


class IntelligentChunker:
    """Structure-aware chunker for multi-format documents"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_structured_elements(self, elements: List[Dict[str, Any]], doc_id: str) -> List[Dict[str, Any]]:
        """
        Chunk a list of structured extracted document elements.
        Each element is expected to have:
        - text: string content
        - page_number: int
        - element_type: 'heading', 'paragraph', 'table', 'slide', 'list'
        - section: Optional[str]
        - subsection: Optional[str]
        - metadata: Optional[Dict]
        """
        chunks = []
        current_chunk_text = ""
        current_page = 1
        current_section = "General"
        current_subsection = ""
        current_element_type = "text"
        current_metadata = {}
        chunk_index = 0

        for el in elements:
            el_text = el.get("text", "").strip()
            if not el_text:
                continue

            page_num = el.get("page_number", current_page)
            el_type = el.get("element_type", "paragraph")
            section = el.get("section", current_section)
            subsection = el.get("subsection", current_subsection)
            metadata = el.get("metadata", {})

            # Update section context if heading
            if el_type == "heading":
                # Section boundary: flush the pending chunk so chunks never straddle sections.
                # Consecutive headings (e.g. "Invoice Details" then "Field Detail") are kept together
                # instead of producing heading-only micro-chunks.
                only_headings = all(l.startswith("## ") for l in current_chunk_text.strip().split("\n") if l.strip())
                if current_chunk_text.strip() and not only_headings:
                    chunks.append(self._build_chunk_dict(
                        doc_id=doc_id,
                        chunk_index=chunk_index,
                        page_number=current_page,
                        section=current_section,
                        subsection=current_subsection,
                        element_type=current_element_type,
                        content=current_chunk_text.strip(),
                        metadata=current_metadata
                    ))
                    chunk_index += 1
                    current_chunk_text = ""
                current_section = el_text
                current_subsection = ""
                section = el_text
                current_page = page_num
                # Also include heading in text flow
                el_text = f"## {el_text}"

            # If element is a table, preserve table integrity as a single chunk (or chunk rows if massive)
            if el_type == "table":
                # A pending heading-only chunk becomes the table's caption instead of a micro-chunk
                pending = current_chunk_text.strip()
                if pending and all(l.startswith("## ") for l in pending.split("\n") if l.strip()):
                    el_text = f"{pending}\n{el_text}"
                    current_chunk_text = ""
                # Flush pending chunk before table if exists
                if current_chunk_text.strip():
                    chunks.append(self._build_chunk_dict(
                        doc_id=doc_id,
                        chunk_index=chunk_index,
                        page_number=current_page,
                        section=current_section,
                        subsection=current_subsection,
                        element_type=current_element_type,
                        content=current_chunk_text.strip(),
                        metadata=current_metadata
                    ))
                    chunk_index += 1
                    current_chunk_text = ""

                # Table chunk
                chunks.append(self._build_chunk_dict(
                    doc_id=doc_id,
                    chunk_index=chunk_index,
                    page_number=page_num,
                    section=section or current_section,
                    subsection=subsection,
                    element_type="table",
                    content=el_text,
                    metadata=metadata
                ))
                chunk_index += 1
                current_page = page_num
                continue

            # Text paragraph/slide splitting by sentences
            sentences = self._split_sentences(el_text)
            # line-structured elements (lists, key/value blocks) keep their line breaks
            inner_sep = "\n" if "\n" in el_text else " "
            for s_idx, sentence in enumerate(sentences):
                sep = "\n" if s_idx == 0 else inner_sep
                potential_len = len(current_chunk_text) + len(sentence) + (1 if current_chunk_text else 0)

                if potential_len > self.chunk_size and current_chunk_text.strip():
                    # Emit current chunk
                    chunks.append(self._build_chunk_dict(
                        doc_id=doc_id,
                        chunk_index=chunk_index,
                        page_number=current_page,
                        section=current_section,
                        subsection=current_subsection,
                        element_type=current_element_type,
                        content=current_chunk_text.strip(),
                        metadata=current_metadata
                    ))
                    chunk_index += 1

                    # Compute overlap from previous text
                    overlap_text = self._get_overlap_text(current_chunk_text, self.chunk_overlap)
                    current_chunk_text = f"{overlap_text}{sep}{sentence}".strip() if overlap_text else sentence
                    current_page = page_num
                    current_section = section or current_section
                    current_subsection = subsection or current_subsection
                    current_element_type = el_type
                    current_metadata = metadata
                else:
                    if current_chunk_text:
                        current_chunk_text += sep + sentence
                    else:
                        current_chunk_text = sentence
                        current_page = page_num
                        current_section = section or current_section
                        current_subsection = subsection or current_subsection
                        current_element_type = el_type
                        current_metadata = metadata

        # Emit remaining chunk
        if current_chunk_text.strip():
            chunks.append(self._build_chunk_dict(
                doc_id=doc_id,
                chunk_index=chunk_index,
                page_number=current_page,
                section=current_section,
                subsection=current_subsection,
                element_type=current_element_type,
                content=current_chunk_text.strip(),
                metadata=current_metadata
            ))

        return chunks

    def chunk_raw_text(self, raw_text: str, doc_id: str, default_page: int = 1) -> List[Dict[str, Any]]:
        """Fallback chunker for unstructured text with page boundary markers"""
        # Check for page markers like --- Page 2 ---
        page_pattern = re.compile(r'---\s*Page\s*(\d+)\s*---', re.IGNORECASE)
        parts = page_pattern.split(raw_text)

        elements = []
        if len(parts) > 1:
            # First element might be before Page 1
            if parts[0].strip():
                elements.append({"text": parts[0].strip(), "page_number": default_page, "element_type": "paragraph"})
            
            for i in range(1, len(parts), 2):
                p_num = int(parts[i])
                p_text = parts[i+1].strip() if i+1 < len(parts) else ""
                if p_text:
                    # Detect headings
                    paragraphs = p_text.split('\n\n')
                    for p in paragraphs:
                        clean_p = p.strip()
                        if not clean_p:
                            continue
                        if len(clean_p) < 80 and not clean_p.endswith('.'):
                            elements.append({"text": clean_p, "page_number": p_num, "element_type": "heading"})
                        else:
                            elements.append({"text": clean_p, "page_number": p_num, "element_type": "paragraph"})
        else:
            paragraphs = raw_text.split('\n\n')
            for p in paragraphs:
                clean_p = p.strip()
                if not clean_p:
                    continue
                elements.append({"text": clean_p, "page_number": default_page, "element_type": "paragraph"})

        return self.chunk_structured_elements(elements, doc_id=doc_id)

    def chunk_fixed_size(self, elements: List[Dict[str, Any]], doc_id: str) -> List[Dict[str, Any]]:
        """
        Naive baseline used in the evaluation: concatenate all text and cut it into
        fixed-size character windows, ignoring sections, sentences and tables.
        """
        full_text = " ".join(el.get("text", "").strip() for el in elements if el.get("text"))
        step = max(1, self.chunk_size - self.chunk_overlap)
        chunks = []
        for idx, start in enumerate(range(0, len(full_text), step)):
            piece = full_text[start:start + self.chunk_size].strip()
            if piece:
                chunks.append(self._build_chunk_dict(doc_id, idx, 1, "General", "", "text", piece))
            if start + self.chunk_size >= len(full_text):
                break
        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences while respecting abbreviations and numbers"""
        # Split on period/question/exclamation followed by space and capital or digit
        return split_prose(text)

    def _get_overlap_text(self, text: str, overlap_chars: int) -> str:
        """Extract approximate overlap without breaking words"""
        if len(text) <= overlap_chars:
            return text
        tail = text[-overlap_chars:]
        # Find first space to avoid cutting word in half
        space_idx = tail.find(' ')
        if space_idx != -1:
            return tail[space_idx+1:]
        return tail

    def _build_chunk_dict(
        self,
        doc_id: str,
        chunk_index: int,
        page_number: int,
        section: str,
        subsection: str,
        element_type: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        return {
            "chunk_id": f"{doc_id}_{chunk_index}",
            "doc_id": doc_id,
            "chunk_index": chunk_index,
            "page_number": page_number,
            "section": section or "General",
            "subsection": subsection or "",
            "element_type": element_type,
            "content": content,
            "text": content,  # backward compatibility alias
            "char_count": len(content),
            "token_count": len(content.split()),
            "metadata": metadata or {}
        }
