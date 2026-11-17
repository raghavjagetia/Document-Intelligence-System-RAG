"""
Vector Store
Dense vector index over document chunks.
- FAISS IndexIDMap2(IndexFlatIP) with exact inner-product search on L2-normalised
  vectors (= cosine similarity). Falls back to an equivalent NumPy implementation.
- Metadata filtering (user, domain, document) is applied *inside* the search via
  a FAISS IDSelector, so filtered queries remain exact.
- Supports deletion of a document's vectors and persistence to disk.
"""
import logging
import pickle
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from .models import get_embedder
from .text_utils import doc_title

logger = logging.getLogger(__name__)

try:
    import faiss
    HAS_FAISS = True
except Exception:  # pragma: no cover - depends on environment
    HAS_FAISS = False

# Bump when the text that gets embedded changes, so stale on-disk indexes are rebuilt
INDEX_FORMAT = 2


class VectorStore:
    def __init__(self, index_dir: Optional[Path] = None):
        self.index_dir = Path(index_dir) if index_dir else None
        self.embedder = get_embedder()
        self.dim = self.embedder.dim
        self.lock = threading.RLock()
        self.metadata: Dict[int, Dict[str, Any]] = {}   # vector id -> chunk metadata
        self.vectors: Dict[int, np.ndarray] = {}        # vector id -> embedding (for NumPy path / rebuilds)
        self.next_id = 0
        self.version = 0                                # bumped on every mutation (BM25 cache key)
        self.index = self._new_index()
        if self.index_dir:
            self.load()

    @property
    def backend(self) -> str:
        return "faiss" if HAS_FAISS else "numpy"

    def _new_index(self):
        if HAS_FAISS:
            return faiss.IndexIDMap2(faiss.IndexFlatIP(self.dim))
        return None

    # ---------- mutation ----------
    def add_chunks(self, chunks: List[Dict[str, Any]], doc_meta: Dict[str, Any]) -> int:
        """Embed and index chunks of one document. Returns number of vectors added."""
        texts, metas = [], []
        for c in chunks:
            text = (c.get("content") or "").strip()
            if not text:
                continue
            # Contextual chunk header: document title + section, so a chunk such as an invoice's
            # "Line Items" table is still findable by the invoice number that only the title carries
            section = c.get("section") or ""
            header = doc_title(doc_meta.get("filename", ""))
            if section and section not in text[:200]:
                header = f"{header} | {section}" if header else section
            texts.append(f"{header}\n{text}" if header else text)
            metas.append({
                "chunk_id": c["chunk_id"],
                "doc_id": doc_meta["doc_id"],
                "user_id": doc_meta["user_id"],
                "domain": doc_meta.get("domain", "general"),
                "filename": doc_meta.get("filename", ""),
                "page_number": c.get("page_number", 1),
                "section": section or "General",
                "element_type": c.get("element_type", "paragraph"),
                "content": text,
            })
        if not texts:
            return 0
        vecs = self.embedder.encode(texts)
        with self.lock:
            ids = np.arange(self.next_id, self.next_id + len(texts), dtype=np.int64)
            self.next_id += len(texts)
            if HAS_FAISS:
                self.index.add_with_ids(vecs, ids)
            for i, vid in enumerate(ids):
                self.metadata[int(vid)] = metas[i]
                self.vectors[int(vid)] = vecs[i]
            self.version += 1
        return len(texts)

    def remove_document(self, doc_id: str) -> int:
        with self.lock:
            ids = [vid for vid, m in self.metadata.items() if m["doc_id"] == doc_id]
            if not ids:
                return 0
            if HAS_FAISS:
                self.index.remove_ids(np.array(ids, dtype=np.int64))
            for vid in ids:
                self.metadata.pop(vid, None)
                self.vectors.pop(vid, None)
            self.version += 1
            return len(ids)

    def clear(self) -> None:
        with self.lock:
            self.index = self._new_index()
            self.metadata.clear()
            self.vectors.clear()
            self.next_id = 0
            self.version += 1

    # ---------- query ----------
    def filter_ids(self, user_id: Optional[str], domain: Optional[str] = None,
                   doc_id: Optional[str] = None) -> List[int]:
        out = []
        for vid, m in self.metadata.items():
            if user_id is not None and m["user_id"] != user_id:
                continue
            if domain and domain != "all" and m["domain"] != domain:
                continue
            if doc_id and m["doc_id"] != doc_id:
                continue
            out.append(vid)
        return out

    def search(self, query: str, top_k: int = 30, user_id: Optional[str] = None,
               domain: Optional[str] = None, doc_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.lock:
            allowed = self.filter_ids(user_id, domain, doc_id)
            if not allowed:
                return []
            q = self.embedder.encode([query])
            k = min(top_k, len(allowed))
            if HAS_FAISS:
                sel = faiss.IDSelectorBatch(np.array(allowed, dtype=np.int64))
                scores, ids = self.index.search(q, k, params=faiss.SearchParameters(sel=sel))
                pairs = [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]
            else:
                mat = np.stack([self.vectors[v] for v in allowed])
                sims = mat @ q[0]
                order = np.argsort(-sims)[:k]
                pairs = [(allowed[i], float(sims[i])) for i in order]
            results = []
            for rank, (vid, score) in enumerate(pairs, start=1):
                item = dict(self.metadata[vid])
                item["dense_score"] = score
                item["dense_rank"] = rank
                results.append(item)
            return results

    def iter_chunks(self, user_id: Optional[str] = None) -> Iterable[Dict[str, Any]]:
        with self.lock:
            for m in self.metadata.values():
                if user_id is None or m["user_id"] == user_id:
                    yield m

    def stats(self) -> Dict[str, Any]:
        return {"vectors": len(self.metadata), "dimension": self.dim, "backend": self.backend}

    # ---------- persistence ----------
    def save(self) -> None:
        if not self.index_dir:
            return
        with self.lock:
            self.index_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.index_dir / "store.pkl.tmp"
            with open(tmp, "wb") as f:
                pickle.dump({
                    "format": INDEX_FORMAT, "embedder": self.embedder.model_name, "dim": self.dim,
                    "next_id": self.next_id,
                    "metadata": self.metadata, "vectors": self.vectors,
                }, f)
            tmp.replace(self.index_dir / "store.pkl")

    def load(self) -> bool:
        path = self.index_dir / "store.pkl" if self.index_dir else None
        if not path or not path.exists():
            return False
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            if (data.get("format") != INDEX_FORMAT or data.get("embedder") != self.embedder.model_name
                    or data.get("dim") != self.dim):
                logger.warning("Index was built with %s; embedder is now %s - index must be rebuilt",
                               data.get("embedder"), self.embedder.model_name)
                return False
            with self.lock:
                self.metadata = data["metadata"]
                self.vectors = data["vectors"]
                self.next_id = data["next_id"]
                self.index = self._new_index()
                if HAS_FAISS and self.vectors:
                    ids = np.array(list(self.vectors.keys()), dtype=np.int64)
                    self.index.add_with_ids(np.stack([self.vectors[int(i)] for i in ids]), ids)
                self.version += 1
            return True
        except Exception as e:
            logger.error("Failed to load vector index: %s", e)
            return False
