"""
Application Services
Single place where the database, vector index, RAG pipeline and document
intelligence are wired together. Used by the API, the seeding script and tests.
"""
import logging
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .auth import AuthService
from .config import Config
from .database import Database
from .document_intelligence import DocumentIntelligence
from .document_processor import DocumentProcessor
from .llm import LLMClient
from .models import get_embedder, get_ocr
from .rag_pipeline import PipelineSettings, RAGPipeline
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class DuplicateDocument(Exception):
    def __init__(self, existing: Dict[str, Any]):
        super().__init__("duplicate")
        self.existing = existing


class Services:
    def __init__(self):
        Config.ensure_directories()
        self.db = Database(Config.DB_PATH)
        self.auth = AuthService(self.db)
        self.llm = LLMClient()
        self.store = VectorStore(Config.INDEX_DIR)
        self.processor = DocumentProcessor(Config.CHUNK_SIZE, Config.CHUNK_OVERLAP)
        self.pipeline = RAGPipeline(self.store, llm=self.llm)
        self.intelligence = DocumentIntelligence(llm=self.llm)
        self._ingest_lock = threading.Lock()
        # summaries, entities and key fields per document; documents never change (a re-upload is a new
        # version with a new id), so each result is computed once and then served instantly
        self._insights: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self._insights_lock = threading.Lock()
        self.auth.ensure_demo_user()
        self.auth.ensure_admin_user()
        self._sync_index()

    # ------------------------------------------------------------------ index
    def _sync_index(self) -> None:
        """Rebuild the vector index from SQLite if it is missing or out of date"""
        db_chunks = self.db.all_chunks_with_docs()
        if len(db_chunks) == len(self.store.metadata) and \
                {c["chunk_id"] for c in db_chunks} == {m["chunk_id"] for m in self.store.metadata.values()}:
            return
        logger.info("Rebuilding vector index from database (%d chunks)", len(db_chunks))
        self.store.clear()
        by_doc: Dict[str, List[Dict[str, Any]]] = {}
        for c in db_chunks:
            by_doc.setdefault(c["doc_id"], []).append(c)
        for doc_id, chunks in by_doc.items():
            first = chunks[0]
            self.store.add_chunks(chunks, {"doc_id": doc_id, "user_id": first["user_id"],
                                           "domain": first["domain"], "filename": first["filename"]})
        self.store.save()

    # ------------------------------------------------------------------ status
    def system_status(self) -> Dict[str, Any]:
        emb = get_embedder()
        return {
            "embedding": {"model": emb.model_name, "type": emb.kind, "dimension": emb.dim},
            "reranker": {"model": self.pipeline.reranker.model_name, "type": self.pipeline.reranker.kind},
            "llm": {"provider": self.llm.provider, "model": self.llm.model, "available": self.llm.available,
                    # > 0 while the provider's rate limit is in force; answers are produced offline meanwhile
                    "paused_seconds": round(self.llm.paused_seconds) if self.llm.available else 0},
            "ocr": {"available": get_ocr() is not None, "engine": "RapidOCR (ONNX)" if get_ocr() else "none"},
            "vector_index": self.store.backend,
            "indexed_chunks": len(self.store.metadata),
            "supported_formats": [e.lstrip(".").upper() for e in Config.ALLOWED_EXTENSIONS if e not in (".htm", ".jpeg")],
        }

    # ------------------------------------------------------------------ documents
    def ingest_file(self, user_id: str, src_path: Path, filename: str, domain: str) -> Dict[str, Any]:
        """
        Process and index one file. `src_path` is a temporary file that this method
        moves into permanent storage. Raises DuplicateDocument / ValueError.
        """
        ext = Path(filename).suffix.lower()
        if ext not in Config.ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type '{ext or 'none'}'")
        if domain not in Config.DOMAINS:
            domain = "general"
        file_hash = self.processor.calculate_file_hash(str(src_path))
        with self._ingest_lock:
            existing = self.db.find_by_hash(file_hash, user_id)
            if existing:
                raise DuplicateDocument(existing)
            previous = self.db.latest_version(filename, user_id)
            version = previous["version"] + 1 if previous else 1
            parent = previous["doc_id"] if previous else None

            result = self.processor.process_document(str(src_path), domain=domain, user_id=user_id,
                                                     filename=filename, version=version, parent_doc_id=parent)
            meta = result["metadata"]
            dest_dir = Config.UPLOAD_DIR / user_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{meta['doc_id']}{ext}"
            shutil.copyfile(src_path, dest)
            meta["file_path"] = str(dest)
            try:
                self.db.save_document(meta, result["chunks"])
                self.store.add_chunks(result["chunks"], meta)
                self.store.save()
            except Exception:
                dest.unlink(missing_ok=True)
                self.db.delete_document(meta["doc_id"], user_id)
                self.store.remove_document(meta["doc_id"])
                raise
        return self.db.get_document(meta["doc_id"], user_id)

    def cached_insight(self, doc_id: str, kind: str, variant: str, compute, refresh: bool = False) -> Dict[str, Any]:
        """
        Return a remembered insight, computing it on first use. A result produced offline only because the
        configured LLM was unavailable at that moment (e.g. rate-limited) is not remembered, so the LLM
        version is produced once the LLM is back. `refresh` (the Regenerate button) always recomputes.
        """
        key = (doc_id, kind, variant)
        if not refresh:
            with self._insights_lock:
                if key in self._insights:
                    return self._insights[key]
        value = compute()
        method = str(value.get("method", ""))
        fell_back = self.llm.available and kind != "entities" and "llm" not in method
        if not fell_back:
            with self._insights_lock:
                self._insights[key] = value
        return value

    def forget_insights(self, doc_id: str) -> None:
        with self._insights_lock:
            for key in [k for k in self._insights if k[0] == doc_id]:
                del self._insights[key]

    def delete_document(self, user_id: str, doc_id: str) -> bool:
        doc = self.db.delete_document(doc_id, user_id)
        if not doc:
            return False
        self.forget_insights(doc_id)
        self.store.remove_document(doc_id)
        self.store.save()
        Path(doc["file_path"]).unlink(missing_ok=True)
        return True

    def admin_delete_document(self, doc_id: str) -> bool:
        owner = self.db.document_owner(doc_id)
        return bool(owner) and self.delete_document(owner, doc_id)

    def admin_delete_user(self, user_id: str) -> None:
        """Deletes an account with all of its documents, vectors, files and chats"""
        for doc in self.db.list_documents(user_id):
            self.store.remove_document(doc["doc_id"])
            self.forget_insights(doc["doc_id"])
        self.store.save()
        self.db.delete_user(user_id)
        shutil.rmtree(Config.UPLOAD_DIR / user_id, ignore_errors=True)

    def document_text(self, doc_id: str) -> Tuple[List[Dict[str, Any]], str]:
        chunks = self.db.get_chunks(doc_id)
        return chunks, "\n\n".join(c["content"] for c in chunks)

    # ------------------------------------------------------------------ chat
    def _prepare_question(self, user_id: str, question: str, conversation_id: Optional[str], domain: str):
        question = (question or "").strip()
        if not question:
            raise ValueError("Question must not be empty")
        if len(question) > 2000:
            raise ValueError("Question is too long (max 2000 characters)")
        if conversation_id:
            conv = self.db.get_conversation(conversation_id, user_id)
            if not conv:
                raise LookupError("Conversation not found")
        else:
            title = question if len(question) <= 60 else question[:57].rsplit(" ", 1)[0] + "…"
            conv = self.db.create_conversation(user_id, title=title, domain=domain or "all")
        history = self.db.user_questions(conv["conversation_id"], limit=3)
        previous_answer = self.db.last_answer(conv["conversation_id"])
        user_msg = self.db.add_message(conv["conversation_id"], "user", question)
        return question, conv, history, previous_answer, user_msg

    def ask_stream(self, user_id: str, question: str, conversation_id: Optional[str] = None,
                   domain: str = "all", doc_id: Optional[str] = None,
                   retrieval_mode: str = "hybrid", search_all: bool = False,
                   answer_style: str = "quick") -> Iterator[Tuple[str, Dict[str, Any]]]:
        """
        Yields ("meta", ...), ("token", ...), ("done", ...) events and persists messages.
        `search_all` (administrators) retrieves from every user's documents instead of only the asker's.
        """
        scope = None if search_all else user_id
        if doc_id and not self.db.get_document(doc_id, scope):
            raise LookupError("Document not found")
        question, conv, history, previous_answer, user_msg = self._prepare_question(user_id, question,
                                                                                    conversation_id, domain)
        settings = PipelineSettings.for_mode(retrieval_mode)
        settings.answer_style = answer_style if answer_style in ("quick", "detailed", "quote") else "quick"
        result = None
        for event, payload in self.pipeline.stream(question, scope, domain, doc_id, history, settings,
                                                   previous_answer=previous_answer):
            if event == "meta":
                yield "meta", {"conversation_id": conv["conversation_id"], "user_message": user_msg,
                               "rewritten_query": payload["rewritten_query"], "citations": payload["citations"]}
            elif event == "token":
                yield "token", {"text": payload}
            else:
                result = payload
        assistant = self.db.add_message(
            conv["conversation_id"], "assistant", result.answer,
            rewritten_query=result.rewritten_query if result.rewritten_query != question else None,
            retrieval_mode=result.retrieval_mode, grounded=result.grounded, grounding_score=result.grounding_score,
            confidence_score=result.confidence_score, latency_seconds=result.latency_seconds,
            model_name=self.llm.label if result.generation_mode.startswith("llm") else self.pipeline.reranker.model_name,
            generation_mode=result.generation_mode, abstained=result.abstained, citations=result.citations,
            answer_style=settings.answer_style,
        )
        yield "done", {"assistant_message": assistant, "conversation_id": conv["conversation_id"],
                       "user_message": user_msg}

    def ask(self, user_id: str, **kwargs) -> Dict[str, Any]:
        final = None
        for event, payload in self.ask_stream(user_id, **kwargs):
            if event == "done":
                final = payload
        return final


_services: Optional[Services] = None
_services_lock = threading.Lock()


def get_services() -> Services:
    global _services
    with _services_lock:
        if _services is None:
            _services = Services()
        return _services
