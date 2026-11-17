"""
Model Registry
Loads each ML model exactly once and shares it across the application:
- Dense embedder: SentenceTransformer (all-MiniLM-L6-v2) with a hashing fallback
- Cross-encoder reranker: ms-marco-MiniLM-L-6-v2 (lexical fallback lives in reranker.py)
- OCR engine: RapidOCR (ONNX runtime, no system binary needed)

Every component reports whether the real model or a fallback is active, so the
UI and the evaluation can state honestly what produced a result.
"""
import hashlib
import logging
import threading
from typing import List, Optional

import numpy as np

from .config import Config

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_embedder = None
_cross_encoder = None
_cross_encoder_loaded = False
_ocr = None
_ocr_loaded = False


class HashingEmbedder:
    """
    Fallback embedder used only when sentence-transformers is unavailable.
    Feature hashing of words and character n-grams: lexical, NOT semantic.
    """
    kind = "hashing"

    def __init__(self, dim: int = 384):
        self.dim = dim
        self.model_name = "hashing-ngram-384"

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in (text or "").lower().split():
                out[row, int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim] += 1.5
                for n in (3, 4):
                    for i in range(max(0, len(word) - n + 1)):
                        h = int(hashlib.md5(word[i:i + n].encode()).hexdigest(), 16) % self.dim
                        out[row, h] += 0.5
        return _normalize(out)


class NeuralEmbedder:
    """Sentence-BERT bi-encoder producing L2-normalised dense vectors"""
    kind = "neural"

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name, device="cpu")
        self.model_name = model_name
        get_dim = getattr(self.model, "get_embedding_dimension", None) or self.model.get_sentence_embedding_dimension
        self.dim = get_dim()

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vecs = self.model.encode(
            texts, batch_size=batch_size, convert_to_numpy=True,
            normalize_embeddings=True, show_progress_bar=False
        )
        return vecs.astype(np.float32)


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (m / norms).astype(np.float32)


def get_embedder():
    global _embedder
    with _lock:
        if _embedder is None:
            if Config.ENABLE_NEURAL_MODELS:
                try:
                    _embedder = NeuralEmbedder(Config.EMBEDDING_MODEL)
                    logger.info("Loaded neural embedder %s", Config.EMBEDDING_MODEL)
                except Exception as e:  # pragma: no cover - depends on environment
                    logger.warning("Neural embedder unavailable (%s); using hashing fallback", e)
            if _embedder is None:
                _embedder = HashingEmbedder()
        return _embedder


def get_cross_encoder():
    """Returns a sentence_transformers.CrossEncoder or None when unavailable"""
    global _cross_encoder, _cross_encoder_loaded
    with _lock:
        if not _cross_encoder_loaded:
            _cross_encoder_loaded = True
            if Config.ENABLE_NEURAL_MODELS:
                try:
                    from sentence_transformers import CrossEncoder
                    _cross_encoder = CrossEncoder(Config.RERANKER_MODEL, device="cpu")
                    logger.info("Loaded cross-encoder %s", Config.RERANKER_MODEL)
                except Exception as e:  # pragma: no cover
                    logger.warning("Cross-encoder unavailable (%s); using lexical reranker", e)
        return _cross_encoder


def get_ocr():
    """Returns a RapidOCR engine or None when OCR is unavailable/disabled"""
    global _ocr, _ocr_loaded
    with _lock:
        if not _ocr_loaded:
            _ocr_loaded = True
            if Config.ENABLE_OCR:
                try:
                    from rapidocr_onnxruntime import RapidOCR
                    _ocr = RapidOCR()
                    logger.info("Loaded RapidOCR engine")
                except Exception as e:  # pragma: no cover
                    logger.warning("OCR unavailable (%s)", e)
        return _ocr


def ocr_image(image) -> str:
    """Run OCR on a PIL image / numpy array / path. Returns text in reading order."""
    engine = get_ocr()
    if engine is None:
        return ""
    if hasattr(image, "convert"):
        image = np.array(image.convert("RGB"))
    result, _ = engine(image)
    if not result:
        return ""
    # result rows: [box, text, score]; sort top-to-bottom then left-to-right
    rows = sorted(result, key=lambda r: (round(r[0][0][1] / 12), r[0][0][0]))
    lines: List[str] = []
    last_y: Optional[float] = None
    for box, text, _score in rows:
        y = box[0][1]
        if last_y is not None and abs(y - last_y) < 12 and lines:
            lines[-1] += " " + text
        else:
            lines.append(text)
        last_y = y
    return "\n".join(lines)


def warm_up() -> None:
    """Load all models eagerly (called on server start)"""
    get_embedder()
    get_cross_encoder()
    get_ocr()
