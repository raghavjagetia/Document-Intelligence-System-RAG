"""
Database Layer (SQLite, WAL mode)
Tables: users, sessions, documents, chunks, conversations, messages, citations, evaluation_runs.
Every read/write that touches user data takes a user_id so ownership is enforced in SQL.
"""
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_hash TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT 'general',
    page_count INTEGER NOT NULL DEFAULT 1,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    tables_count INTEGER NOT NULL DEFAULT 0,
    ocr_pages INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    parent_doc_id TEXT,
    status TEXT NOT NULL DEFAULT 'indexed',
    uploaded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER NOT NULL DEFAULT 1,
    section TEXT,
    element_type TEXT,
    content TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    token_count INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT 'all',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    rewritten_query TEXT,
    retrieval_mode TEXT,
    grounded INTEGER,
    grounding_score REAL,
    confidence_score REAL,
    latency_seconds REAL,
    model_name TEXT,
    generation_mode TEXT,
    abstained INTEGER NOT NULL DEFAULT 0,
    answer_style TEXT,
    feedback INTEGER,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
CREATE TABLE IF NOT EXISTS citations (
    citation_id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
    citation_number INTEGER NOT NULL,
    doc_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    page_number INTEGER,
    section TEXT,
    chunk_id TEXT,
    source_snippet TEXT,
    relevance_score REAL,
    found_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_citations_msg ON citations(message_id);
CREATE TABLE IF NOT EXISTS evaluation_runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    total_queries INTEGER NOT NULL,
    report_json TEXT NOT NULL
);
"""

DOC_COLUMNS = ("doc_id, filename, file_type, file_size, domain, page_count, chunk_count, tables_count, "
               "ocr_pages, version, parent_doc_id, status, uploaded_at")


# DOC_COLUMNS qualified with the documents alias `d` for joins
DOC_COLUMNS_D = ", ".join("d." + c.strip() for c in DOC_COLUMNS.split(","))


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Database:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self.conn() as c:
            c.executescript(SCHEMA)
            # migration: account suspension flag (added after the first release)
            if "disabled" not in {r[1] for r in c.execute("PRAGMA table_info(users)")}:
                c.execute("ALTER TABLE users ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0")
            # migration: which search method(s) found a cited passage ("meaning,words")
            if "found_by" not in {r[1] for r in c.execute("PRAGMA table_info(citations)")}:
                c.execute("ALTER TABLE citations ADD COLUMN found_by TEXT")
            # migration: answer style (quick/detailed/quote) and user feedback (1 helpful, -1 not helpful)
            message_cols = {r[1] for r in c.execute("PRAGMA table_info(messages)")}
            if "answer_style" not in message_cols:
                c.execute("ALTER TABLE messages ADD COLUMN answer_style TEXT")
            if "feedback" not in message_cols:
                c.execute("ALTER TABLE messages ADD COLUMN feedback INTEGER")

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            con = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA foreign_keys = ON")
            con.execute("PRAGMA journal_mode = WAL")
            try:
                yield con
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def _one(self, sql: str, params=()) -> Optional[Dict[str, Any]]:
        with self.conn() as c:
            row = c.execute(sql, params).fetchone()
            return dict(row) if row else None

    def _all(self, sql: str, params=()) -> List[Dict[str, Any]]:
        with self.conn() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]

    # ------------------------------------------------------------ users & sessions
    def create_user(self, username: str, email: str, password_hash: str, role: str = "user",
                    user_id: Optional[str] = None) -> Dict[str, Any]:
        user_id = user_id or f"usr_{uuid.uuid4().hex[:12]}"
        with self.conn() as c:
            c.execute("INSERT INTO users (user_id, username, email, password_hash, role, created_at) "
                      "VALUES (?, ?, ?, ?, ?, ?)", (user_id, username, email, password_hash, role, now_iso()))
        return self.get_user(user_id)

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        user = self._one("SELECT user_id, username, email, role, disabled, created_at FROM users WHERE user_id = ?",
                         (user_id,))
        if user:
            user["disabled"] = bool(user["disabled"])
        return user

    def get_user_with_hash(self, username_or_email: str) -> Optional[Dict[str, Any]]:
        return self._one("SELECT * FROM users WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE", (username_or_email, username_or_email))

    def user_exists(self, username: str, email: str) -> bool:
        return self._one("SELECT 1 AS x FROM users WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE", (username, email)) is not None

    def count_users(self) -> int:
        return self._one("SELECT COUNT(*) AS n FROM users")["n"]

    def create_session(self, token_hash: str, user_id: str, ttl_hours: int) -> None:
        expires = (datetime.now() + timedelta(hours=ttl_hours)).isoformat(timespec="seconds")
        with self.conn() as c:
            c.execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                      (token_hash, user_id, now_iso(), expires))

    def get_session_user(self, token_hash: str) -> Optional[Dict[str, Any]]:
        row = self._one("SELECT s.expires_at, u.user_id, u.username, u.email, u.role, u.created_at "
                        "FROM sessions s JOIN users u ON u.user_id = s.user_id "
                        "WHERE s.token_hash = ? AND u.disabled = 0", (token_hash,))
        if not row:
            return None
        if row.pop("expires_at") < now_iso():
            self.delete_session(token_hash)
            return None
        return row

    def delete_session(self, token_hash: str) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    # ------------------------------------------------------------ documents
    def save_document(self, meta: Dict[str, Any], chunks: List[Dict[str, Any]]) -> None:
        with self.conn() as c:
            c.execute(
                "INSERT INTO documents (doc_id, user_id, filename, file_path, file_type, file_size, file_hash, domain, "
                "page_count, chunk_count, tables_count, ocr_pages, version, parent_doc_id, status, uploaded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (meta["doc_id"], meta["user_id"], meta["filename"], meta["file_path"], meta["file_type"],
                 meta["file_size"], meta["file_hash"], meta["domain"], meta["page_count"], meta["chunk_count"],
                 meta["tables_count"], meta["ocr_pages"], meta["version"], meta["parent_doc_id"],
                 meta["status"], meta["uploaded_at"]))
            c.executemany(
                "INSERT INTO chunks (chunk_id, doc_id, chunk_index, page_number, section, element_type, content, "
                "char_count, token_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(ch["chunk_id"], meta["doc_id"], ch["chunk_index"], ch.get("page_number", 1), ch.get("section"),
                  ch.get("element_type"), ch["content"], len(ch["content"]), len(ch["content"].split()))
                 for ch in chunks])

    def list_documents(self, user_id: Optional[str], domain: Optional[str] = None, search: Optional[str] = None,
                       owner: Optional[str] = None) -> List[Dict]:
        """Documents of one user, or of every user when user_id is None (administrators)"""
        sql = (f"SELECT {DOC_COLUMNS_D}, d.user_id, u.username AS owner FROM documents d "
               "JOIN users u ON u.user_id = d.user_id WHERE 1 = 1")
        params: List[Any] = []
        if user_id:
            sql += " AND d.user_id = ?"
            params.append(user_id)
        if owner:
            sql += " AND u.username = ?"
            params.append(owner)
        if domain and domain != "all":
            sql += " AND d.domain = ?"
            params.append(domain)
        if search:
            sql += " AND d.filename LIKE ?"
            params.append(f"%{search}%")
        return self._all(sql + " ORDER BY d.uploaded_at DESC, d.filename", params)

    def get_document(self, doc_id: str, user_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """A document owned by user_id; any document when user_id is None (administrators)"""
        sql = (f"SELECT {DOC_COLUMNS_D}, d.user_id, u.username AS owner, d.file_path, d.file_hash FROM documents d "
               "JOIN users u ON u.user_id = d.user_id WHERE d.doc_id = ?")
        return self._one(sql + (" AND d.user_id = ?" if user_id else ""), (doc_id, user_id) if user_id else (doc_id,))

    def find_by_hash(self, file_hash: str, user_id: str) -> Optional[Dict[str, Any]]:
        return self._one("SELECT doc_id, filename FROM documents WHERE file_hash = ? AND user_id = ?",
                         (file_hash, user_id))

    def latest_version(self, filename: str, user_id: str) -> Optional[Dict[str, Any]]:
        return self._one("SELECT doc_id, version FROM documents WHERE filename = ? AND user_id = ? "
                          "ORDER BY version DESC LIMIT 1", (filename, user_id))

    def document_versions(self, filename: str, user_id: str) -> List[Dict[str, Any]]:
        return self._all(f"SELECT {DOC_COLUMNS} FROM documents WHERE filename = ? AND user_id = ? ORDER BY version",
                         (filename, user_id))

    def get_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        return self._all("SELECT * FROM chunks WHERE doc_id = ? ORDER BY chunk_index", (doc_id,))

    def all_chunks_with_docs(self) -> List[Dict[str, Any]]:
        return self._all("SELECT c.*, d.user_id, d.domain, d.filename FROM chunks c JOIN documents d "
                         "ON d.doc_id = c.doc_id ORDER BY d.uploaded_at, c.chunk_index")

    def delete_document(self, doc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        doc = self.get_document(doc_id, user_id)
        if not doc:
            return None
        with self.conn() as c:
            c.execute("DELETE FROM documents WHERE doc_id = ? AND user_id = ?", (doc_id, user_id))
            c.execute("UPDATE documents SET parent_doc_id = NULL WHERE parent_doc_id = ?", (doc_id,))
        return doc

    # ------------------------------------------------------------ conversations
    def create_conversation(self, user_id: str, title: str = "New chat", domain: str = "all") -> Dict[str, Any]:
        cid = uuid.uuid4().hex
        ts = now_iso()
        with self.conn() as c:
            c.execute("INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?)", (cid, user_id, title, domain, ts, ts))
        return self.get_conversation(cid, user_id)

    _CONV_SELECT = ("SELECT c.*, u.username AS owner, (SELECT COUNT(*) FROM messages m "
                    "WHERE m.conversation_id = c.conversation_id) AS message_count "
                    "FROM conversations c JOIN users u ON u.user_id = c.user_id ")

    def get_conversation(self, cid: str, user_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """A conversation owned by user_id; any conversation when user_id is None (administrators)"""
        sql = self._CONV_SELECT + "WHERE c.conversation_id = ?"
        return self._one(sql + (" AND c.user_id = ?" if user_id else ""), (cid, user_id) if user_id else (cid,))

    def list_conversations(self, user_id: Optional[str]) -> List[Dict[str, Any]]:
        if user_id:
            return self._all(self._CONV_SELECT + "WHERE c.user_id = ? ORDER BY c.updated_at DESC", (user_id,))
        return self._all(self._CONV_SELECT + "ORDER BY c.updated_at DESC")

    def rename_conversation(self, cid: str, user_id: Optional[str], title: str) -> Optional[Dict[str, Any]]:
        if not self.get_conversation(cid, user_id):
            return None
        with self.conn() as c:
            c.execute("UPDATE conversations SET title = ? WHERE conversation_id = ?", (title[:120], cid))
        return self.get_conversation(cid, user_id)

    def delete_conversation(self, cid: str, user_id: Optional[str]) -> bool:
        if not self.get_conversation(cid, user_id):
            return False
        with self.conn() as c:
            return c.execute("DELETE FROM conversations WHERE conversation_id = ?", (cid,)).rowcount > 0

    def add_message(self, conversation_id: str, role: str, content: str, **fields) -> Dict[str, Any]:
        mid = uuid.uuid4().hex
        ts = fields.pop("timestamp", None) or now_iso()
        citations = fields.pop("citations", []) or []
        cols = ["rewritten_query", "retrieval_mode", "grounded", "grounding_score", "confidence_score",
                "latency_seconds", "model_name", "generation_mode", "abstained", "answer_style"]
        values = [fields.get(c) for c in cols]
        values[cols.index("abstained")] = 1 if fields.get("abstained") else 0
        if fields.get("grounded") is not None:
            values[cols.index("grounded")] = 1 if fields["grounded"] else 0
        with self.conn() as c:
            c.execute(f"INSERT INTO messages (message_id, conversation_id, role, content, {', '.join(cols)}, timestamp) "
                      f"VALUES (?, ?, ?, ?, {', '.join('?' * len(cols))}, ?)",
                      (mid, conversation_id, role, content, *values, ts))
            c.executemany(
                "INSERT INTO citations (citation_id, message_id, citation_number, doc_id, filename, page_number, "
                "section, chunk_id, source_snippet, relevance_score, found_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(uuid.uuid4().hex, mid, ct["citation_number"], ct["doc_id"], ct["filename"], ct.get("page_number"),
                  ct.get("section"), ct.get("chunk_id"), ct.get("source_snippet"), ct.get("relevance_score"),
                  ",".join(ct.get("found_by") or []) or None)
                 for ct in citations])
            c.execute("UPDATE conversations SET updated_at = ? WHERE conversation_id = ?", (ts, conversation_id))
        return self.get_message(mid)

    def get_message(self, mid: str) -> Dict[str, Any]:
        msg = self._one("SELECT * FROM messages WHERE message_id = ?", (mid,))
        return self._decorate_message(msg, self._all(
            "SELECT * FROM citations WHERE message_id = ? ORDER BY citation_number", (mid,)))

    def get_messages(self, cid: str) -> List[Dict[str, Any]]:
        msgs = self._all("SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp, rowid", (cid,))
        cits = self._all("SELECT c.* FROM citations c JOIN messages m ON m.message_id = c.message_id "
                         "WHERE m.conversation_id = ? ORDER BY c.citation_number", (cid,))
        by_msg: Dict[str, List[Dict]] = {}
        for ct in cits:
            by_msg.setdefault(ct["message_id"], []).append(ct)
        return [self._decorate_message(m, by_msg.get(m["message_id"], [])) for m in msgs]

    @staticmethod
    def _decorate_message(msg: Dict[str, Any], citations: List[Dict[str, Any]]) -> Dict[str, Any]:
        msg["grounded"] = bool(msg["grounded"]) if msg.get("grounded") is not None else False
        msg["abstained"] = bool(msg["abstained"])
        for k in ("grounding_score", "confidence_score", "latency_seconds"):
            msg[k] = msg.get(k) or 0.0
        msg["citations"] = [{k: v for k, v in ct.items() if k not in ("citation_id", "message_id")} for ct in citations]
        for ct in msg["citations"]:
            ct["found_by"] = ct["found_by"].split(",") if ct.get("found_by") else []
        return msg

    def last_answer(self, cid: str) -> Optional[str]:
        """The latest assistant answer in a conversation (context for interpreting follow-up questions)"""
        row = self._one("SELECT content FROM messages WHERE conversation_id = ? AND role = 'assistant' "
                        "AND abstained = 0 ORDER BY timestamp DESC, rowid DESC LIMIT 1", (cid,))
        return row["content"] if row else None

    def set_feedback(self, mid: str, user_id: str, rating: int) -> Optional[Dict[str, Any]]:
        """Record the asker's rating of an answer (1 helpful, -1 not helpful, 0 clears it).
        Only the owner of the conversation may rate; returns None if the message is not theirs."""
        owned = self._one("SELECT m.message_id FROM messages m JOIN conversations c ON c.conversation_id = "
                          "m.conversation_id WHERE m.message_id = ? AND c.user_id = ? AND m.role = 'assistant'",
                          (mid, user_id))
        if not owned:
            return None
        with self.conn() as c:
            c.execute("UPDATE messages SET feedback = ? WHERE message_id = ?", (rating or None, mid))
        return self.get_message(mid)

    def user_questions(self, cid: str, limit: int = 3) -> List[str]:
        rows = self._all("SELECT content FROM messages WHERE conversation_id = ? AND role = 'user' "
                         "ORDER BY timestamp DESC, rowid DESC LIMIT ?", (cid, limit))
        return [r["content"] for r in reversed(rows)]

    # ------------------------------------------------------------ analytics
    @staticmethod
    def _owner_filter(user_id: Optional[str]):
        """SQL filter on conversations alias `c`; None means every user (administrator scope)"""
        return ("c.user_id = ?", (user_id,)) if user_id else ("1 = 1", ())

    def statistics(self, user_id: Optional[str]) -> Dict[str, Any]:
        """Statistics for one user, or for the whole system when user_id is None"""
        where, params = self._owner_filter(user_id)
        docs = self.list_documents(user_id) if user_id else self._all(
            f"SELECT {', '.join('d.' + c.strip() for c in DOC_COLUMNS.split(','))}, u.username AS owner "
            "FROM documents d JOIN users u ON u.user_id = d.user_id ORDER BY d.uploaded_at DESC, d.filename")
        q = self._one(
            "SELECT COUNT(*) AS n, AVG(m.confidence_score) AS conf, AVG(m.latency_seconds) AS lat, "
            "AVG(CASE WHEN m.abstained = 0 THEN m.grounded END) AS grounded, AVG(m.abstained) AS abstained "
            "FROM messages m JOIN conversations c ON c.conversation_id = m.conversation_id "
            f"WHERE {where} AND m.role = 'assistant'", params)
        by_domain: Dict[str, int] = {}
        by_format: Dict[str, int] = {}
        for d in docs:
            by_domain[d["domain"]] = by_domain.get(d["domain"], 0) + 1
            by_format[d["file_type"]] = by_format.get(d["file_type"], 0) + 1
        return {
            "total_documents": len(docs),
            "total_chunks": sum(d["chunk_count"] for d in docs),
            "total_conversations": self._one(f"SELECT COUNT(*) AS n FROM conversations c WHERE {where}", params)["n"],
            "total_questions": q["n"] or 0,
            "avg_confidence": round(q["conf"] or 0.0, 3),
            "avg_latency": round(q["lat"] or 0.0, 3),
            "grounded_rate": round(q["grounded"] or 0.0, 3),
            "abstention_rate": round(q["abstained"] or 0.0, 3),
            "by_domain": by_domain,
            "by_format": by_format,
            "recent_documents": docs[:6],
            "scope": "user" if user_id else "system",
            "total_users": None if user_id else self.count_users(),
        }

    def analytics(self, user_id: Optional[str]) -> Dict[str, Any]:
        """Charts data for one user, or for the whole system when user_id is None"""
        where, p = self._owner_filter(user_id)
        base = ("FROM messages m JOIN conversations c ON c.conversation_id = m.conversation_id "
                f"WHERE {where} AND m.role = 'assistant'")
        per_day = self._all(f"SELECT substr(m.timestamp, 1, 10) AS date, COUNT(*) AS count {base} "
                            f"GROUP BY date ORDER BY date", p)
        history = self._all(f"SELECT m.timestamp, m.confidence_score AS confidence, m.grounding_score AS grounding, "
                            f"m.latency_seconds AS latency {base} AND m.abstained = 0 "
                            f"ORDER BY m.timestamp DESC LIMIT 60", p)
        top_docs = self._all("SELECT ct.filename, COUNT(*) AS citations FROM citations ct "
                             "JOIN messages m ON m.message_id = ct.message_id "
                             "JOIN conversations c ON c.conversation_id = m.conversation_id "
                             f"WHERE {where} GROUP BY ct.filename ORDER BY citations DESC LIMIT 8", p)
        modes = self._all(f"SELECT COALESCE(m.retrieval_mode, 'hybrid') AS mode, COUNT(*) AS n {base} GROUP BY mode", p)
        by_style = self._all(f"SELECT COALESCE(m.answer_style, 'quick') AS style, COUNT(*) AS answers, "
                             f"SUM(m.feedback = 1) AS helpful, SUM(m.feedback = -1) AS not_helpful "
                             f"{base} GROUP BY style", p)
        for r in by_style:
            r["helpful"], r["not_helpful"] = r["helpful"] or 0, r["not_helpful"] or 0
        helpful = sum(r["helpful"] for r in by_style)
        not_helpful = sum(r["not_helpful"] for r in by_style)
        lat = [r["latency_seconds"] or 0 for r in self._all(f"SELECT m.latency_seconds {base}", p)]
        buckets = [("<0.25s", 0, 0.25), ("0.25-0.5s", 0.25, 0.5), ("0.5-1s", 0.5, 1), ("1-2s", 1, 2),
                   ("2-5s", 2, 5), (">5s", 5, 1e9)]
        return {
            "queries_per_day": per_day,
            "confidence_history": list(reversed(history)),
            "top_documents": top_docs,
            "retrieval_modes": {r["mode"]: r["n"] for r in modes},
            "latency_histogram": [{"bucket": b, "count": sum(1 for x in lat if lo <= x < hi)} for b, lo, hi in buckets],
            # thumbs up / down given to answers
            "feedback": {
                "helpful": helpful, "not_helpful": not_helpful, "rated": helpful + not_helpful,
                "answers": sum(r["answers"] for r in by_style),
                "satisfaction": round(helpful / (helpful + not_helpful), 3) if helpful + not_helpful else None,
                "by_style": sorted(by_style, key=lambda r: ("quick", "detailed", "quote").index(r["style"])
                                   if r["style"] in ("quick", "detailed", "quote") else 9),
            },
        }

    # ------------------------------------------------------------ administration
    def admin_overview_users(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Per-account statistics (documents, storage, chats, questions, sessions, last activity)"""
        users = self._all(
            "SELECT u.user_id, u.username, u.email, u.role, u.disabled, u.created_at, "
            "(SELECT COUNT(*) FROM sessions s WHERE s.user_id = u.user_id AND s.expires_at > ?) AS sessions, "
            "(SELECT COUNT(*) FROM documents d WHERE d.user_id = u.user_id) AS documents, "
            "(SELECT COALESCE(SUM(d.chunk_count), 0) FROM documents d WHERE d.user_id = u.user_id) AS chunks, "
            "(SELECT COALESCE(SUM(d.file_size), 0) FROM documents d WHERE d.user_id = u.user_id) AS storage_bytes, "
            "(SELECT COUNT(*) FROM conversations c WHERE c.user_id = u.user_id) AS conversations, "
            "(SELECT COUNT(*) FROM messages m JOIN conversations c ON c.conversation_id = m.conversation_id "
            " WHERE c.user_id = u.user_id AND m.role = 'user') AS questions, "
            "(SELECT MAX(m.timestamp) FROM messages m JOIN conversations c ON c.conversation_id = m.conversation_id "
            " WHERE c.user_id = u.user_id) AS last_active "
            "FROM users u " + ("WHERE u.user_id = ? " if user_id else "") +
            "ORDER BY u.role = 'admin' DESC, documents DESC, questions DESC, u.username",
            (now_iso(), user_id) if user_id else (now_iso(),))
        for u in users:
            u["disabled"] = bool(u["disabled"])
        return users

    def admin_overview(self) -> Dict[str, Any]:
        """System-wide view for administrators: every user, every document, recent questions"""
        users = self.admin_overview_users()
        documents = self._all(
            f"SELECT {', '.join('d.' + c.strip() for c in DOC_COLUMNS.split(','))}, u.username AS owner "
            "FROM documents d JOIN users u ON u.user_id = d.user_id ORDER BY d.uploaded_at DESC LIMIT 500")
        recent = self._all(
            "SELECT a.timestamp, u.username, a.conversation_id, q.content AS question, a.content AS answer, "
            "a.confidence_score, a.abstained, a.latency_seconds, a.generation_mode FROM messages a "
            "JOIN conversations c ON c.conversation_id = a.conversation_id "
            "JOIN users u ON u.user_id = c.user_id "
            "JOIN messages q ON q.conversation_id = a.conversation_id AND q.role = 'user' AND q.rowid = ("
            "  SELECT MAX(q2.rowid) FROM messages q2 WHERE q2.conversation_id = a.conversation_id "
            "  AND q2.role = 'user' AND q2.rowid < a.rowid) "
            "WHERE a.role = 'assistant' ORDER BY a.timestamp DESC LIMIT 50")
        for r in recent:
            r["abstained"] = bool(r["abstained"])
        totals = self._one(
            "SELECT (SELECT COUNT(*) FROM users) AS users, (SELECT COUNT(*) FROM documents) AS documents, "
            "(SELECT COALESCE(SUM(chunk_count), 0) FROM documents) AS chunks, "
            "(SELECT COALESCE(SUM(file_size), 0) FROM documents) AS storage_bytes, "
            "(SELECT COUNT(*) FROM conversations) AS conversations, "
            "(SELECT COUNT(*) FROM messages WHERE role = 'user') AS questions, "
            "(SELECT COUNT(*) FROM sessions WHERE expires_at > ?) AS active_sessions", (now_iso(),))
        return {"totals": totals, "users": users, "documents": documents, "recent_questions": recent}

    def admin_user_detail(self, user_id: str, days: int = 14) -> Dict[str, Any]:
        """Everything the administrator's activity view shows for one account"""
        user = next(iter(self.admin_overview_users(user_id)), None)
        base = ("FROM messages m JOIN conversations c ON c.conversation_id = m.conversation_id "
                "WHERE c.user_id = ? AND m.role = 'assistant'")
        q = self._one(f"SELECT AVG(m.confidence_score) AS conf, AVG(m.latency_seconds) AS lat, "
                      f"SUM(m.abstained) AS abstained, AVG(CASE WHEN m.abstained = 0 THEN m.grounded END) AS grounded "
                      f"{base}", (user_id,))
        counts = {r["date"]: r["n"] for r in self._all(
            f"SELECT substr(m.timestamp, 1, 10) AS date, COUNT(*) AS n {base} GROUP BY date", (user_id,))}
        today = datetime.now().date()
        activity = [{"date": (today - timedelta(days=i)).isoformat(),
                     "count": counts.get((today - timedelta(days=i)).isoformat(), 0)}
                    for i in range(days - 1, -1, -1)]
        by_domain: Dict[str, int] = {}
        docs = self.list_documents(user_id)
        for d in docs:
            by_domain[d["domain"]] = by_domain.get(d["domain"], 0) + 1
        return {
            "user": user,
            "stats": {"avg_confidence": round(q["conf"] or 0.0, 3), "avg_latency": round(q["lat"] or 0.0, 3),
                      "abstained": int(q["abstained"] or 0), "grounded_rate": round(q["grounded"] or 0.0, 3)},
            "activity": activity,
            "by_domain": by_domain,
            "documents": docs,
            "conversations": self.list_conversations(user_id),
        }

    def set_user_role(self, user_id: str, role: str) -> None:
        with self.conn() as c:
            c.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))

    def set_user_disabled(self, user_id: str, disabled: bool) -> None:
        with self.conn() as c:
            c.execute("UPDATE users SET disabled = ? WHERE user_id = ?", (1 if disabled else 0, user_id))
            if disabled:
                c.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def set_password_hash(self, user_id: str, password_hash: str) -> None:
        with self.conn() as c:
            c.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (password_hash, user_id))

    def delete_user_sessions(self, user_id: str) -> int:
        with self.conn() as c:
            return c.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,)).rowcount

    def count_admins(self) -> int:
        return self._one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND disabled = 0")["n"]

    def delete_user(self, user_id: str) -> None:
        """Removes the account; documents, chunks, chats and sessions cascade"""
        with self.conn() as c:
            c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

    def document_owner(self, doc_id: str) -> Optional[str]:
        row = self._one("SELECT user_id FROM documents WHERE doc_id = ?", (doc_id,))
        return row["user_id"] if row else None

    def conversation_any(self, cid: str) -> Optional[Dict[str, Any]]:
        """A conversation with its owner's username, whoever owns it (administrator view)"""
        return self._one("SELECT c.*, u.username FROM conversations c JOIN users u ON u.user_id = c.user_id "
                         "WHERE c.conversation_id = ?", (cid,))

    # ------------------------------------------------------------ evaluation
    def save_evaluation(self, report: Dict[str, Any]) -> str:
        rid = uuid.uuid4().hex
        with self.conn() as c:
            c.execute("INSERT INTO evaluation_runs VALUES (?, ?, ?, ?)",
                      (rid, report["created_at"], report["total_queries"], json.dumps(report)))
        return rid

    def latest_evaluation(self) -> Optional[Dict[str, Any]]:
        row = self._one("SELECT report_json FROM evaluation_runs ORDER BY created_at DESC LIMIT 1")
        return json.loads(row["report_json"]) if row else None
