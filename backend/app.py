"""
FastAPI application - DocuMind AI Document Intelligence & Hybrid RAG System
All endpoints live under /api (see docs/API.md). The built React frontend is
served from / with single-page-app fallback.

Run:  python -m uvicorn backend.app:app --port 8000
"""
import json
import logging
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .auth import LoginLimiter, RateLimiter, hash_password, password_problem
from .config import Config
from .models import warm_up
from .services import DuplicateDocument, Services, get_services

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("documind")


@asynccontextmanager
async def lifespan(_: FastAPI):
    warm_up()
    get_services()
    logger.info("DocuMind ready: %s", get_services().system_status())
    yield


app = FastAPI(title="DocuMind API", version=Config.VERSION, lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=Config.ALLOWED_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",          # the browser must not guess file types (e.g. run an upload as script)
    "X-Frame-Options": "DENY",                    # the app cannot be embedded in another site (clickjacking)
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


login_limiter = LoginLimiter(max_failures=Config.LOGIN_MAX_FAILURES, lockout=Config.LOGIN_LOCKOUT_MINUTES * 60)
signup_limiter = RateLimiter(limit=Config.SIGNUPS_PER_HOUR_PER_IP, window=3600)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
api = APIRouter(prefix="/api")


# ============================================================ dependencies
def svc() -> Services:
    return get_services()


def bearer_token(authorization: Optional[str] = Header(None)) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def current_user(token: Optional[str] = Depends(bearer_token), s: Services = Depends(svc)) -> Dict[str, Any]:
    user = s.auth.user_for_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    return user


def scope(user: Dict[str, Any]) -> Optional[str]:
    """Data scope of a request: administrators see every user's data (None), others only their own"""
    return None if user.get("role") == "admin" else user["user_id"]


def admin_user(user=Depends(current_user)) -> Dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


# ============================================================ schemas
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    domain: str = "all"


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    domain: str = "all"
    doc_id: Optional[str] = None
    retrieval_mode: str = "hybrid"
    # quick: 1-4 cited sentences · detailed: structured explanation · quote: verbatim sentences from the documents
    answer_style: str = Field("quick", pattern="^(quick|detailed|quote)$")


class SummarizeRequest(BaseModel):
    summary_type: str = "detailed"
    refresh: bool = False  # recompute instead of returning the remembered result


class ExtractRequest(BaseModel):
    document_type: str = "auto"
    refresh: bool = False


class CompareRequest(BaseModel):
    doc_id_a: str
    doc_id_b: str


class SourceViewRequest(BaseModel):
    chunk_id: Optional[str] = None
    page_number: Optional[int] = None
    # the answer text that cites this source; decides which sentence of the passage is highlighted
    focus: str = Field("", max_length=6000)


class FeedbackRequest(BaseModel):
    rating: int = Field(ge=-1, le=1)  # 1 helpful, -1 not helpful, 0 clears the rating


# ============================================================ auth
@api.post("/auth/register")
def register(req: RegisterRequest, request: Request, s: Services = Depends(svc)):
    error = s.auth.validate_registration(req.username, req.email, req.password)
    if error:
        raise HTTPException(400, error)
    if not signup_limiter.allow(client_ip(request)):
        raise HTTPException(429, "Too many new accounts from this network. Please try again later.")
    user = s.auth.register(req.username, req.email, req.password)
    return {"user": user, "token": s.auth.create_session(user["user_id"])}


@api.post("/auth/login")
def login(req: LoginRequest, request: Request, s: Services = Depends(svc)):
    ip = client_ip(request)
    wait = login_limiter.retry_after(req.username, ip)
    if wait:
        raise HTTPException(429, f"Too many failed sign-in attempts. Try again in {max(1, round(wait / 60))} minute(s).",
                            headers={"Retry-After": str(wait)})
    try:
        user = s.auth.authenticate(req.username, req.password)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    if not user:
        login_limiter.failed(req.username, ip)
        raise HTTPException(401, "Invalid username or password")
    login_limiter.succeeded(req.username)
    return {"user": user, "token": s.auth.create_session(user["user_id"])}


@api.post("/auth/logout")
def logout(token: Optional[str] = Depends(bearer_token), s: Services = Depends(svc)):
    if token:
        s.auth.logout(token)
    return {"ok": True}


@api.get("/auth/me")
def me(user=Depends(current_user)):
    return {"user": user}


# ============================================================ system
@api.get("/health")
def health():
    return {"status": "online", "version": Config.VERSION}


@api.get("/system/status")
def system_status(s: Services = Depends(svc)):
    return s.system_status()


@api.get("/statistics")
def statistics(user=Depends(current_user), s: Services = Depends(svc)):
    # administrators see system-wide numbers, everyone else only their own
    return s.db.statistics(None if user["role"] == "admin" else user["user_id"])


@api.get("/analytics")
def analytics(user=Depends(current_user), s: Services = Depends(svc)):
    return s.db.analytics(None if user["role"] == "admin" else user["user_id"])


# ============================================================ administration
@api.get("/admin/overview")
def admin_overview(_=Depends(admin_user), s: Services = Depends(svc)):
    return s.db.admin_overview()


class AdminUserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = Field("user", pattern="^(user|admin)$")


class AdminUserUpdate(BaseModel):
    role: Optional[str] = Field(None, pattern="^(user|admin)$")
    disabled: Optional[bool] = None
    password: Optional[str] = None


def _managed_user(user_id: str, s: Services) -> Dict[str, Any]:
    target = s.db.get_user(user_id)
    if not target:
        raise HTTPException(404, "User not found")
    return target


@api.post("/admin/users")
def admin_create_user(req: AdminUserCreate, _=Depends(admin_user), s: Services = Depends(svc)):
    error = s.auth.validate_registration(req.username, req.email, req.password)
    if error:
        raise HTTPException(400, error)
    return s.auth.register(req.username, req.email, req.password, role=req.role)


@api.patch("/admin/users/{user_id}")
def admin_update_user(user_id: str, req: AdminUserUpdate, admin=Depends(admin_user), s: Services = Depends(svc)):
    target = _managed_user(user_id, s)
    if user_id == admin["user_id"] and (req.disabled or (req.role and req.role != "admin")):
        raise HTTPException(400, "You cannot suspend or demote your own administrator account")
    if req.password is not None:
        problem = password_problem(req.password)
        if problem:
            raise HTTPException(400, problem)
        s.db.set_password_hash(user_id, hash_password(req.password))
        s.db.delete_user_sessions(user_id)
    if req.role and req.role != target["role"]:
        s.db.set_user_role(user_id, req.role)
    if req.disabled is not None:
        s.db.set_user_disabled(user_id, req.disabled)
    return s.db.get_user(user_id)


@api.post("/admin/users/{user_id}/logout")
def admin_logout_user(user_id: str, _=Depends(admin_user), s: Services = Depends(svc)):
    _managed_user(user_id, s)
    return {"ok": True, "sessions_revoked": s.db.delete_user_sessions(user_id)}


@api.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: str, admin=Depends(admin_user), s: Services = Depends(svc)):
    _managed_user(user_id, s)
    if user_id == admin["user_id"]:
        raise HTTPException(400, "You cannot delete your own administrator account")
    s.admin_delete_user(user_id)
    return {"ok": True}


@api.delete("/admin/documents/{doc_id}")
def admin_delete_document(doc_id: str, _=Depends(admin_user), s: Services = Depends(svc)):
    if not s.admin_delete_document(doc_id):
        raise HTTPException(404, "Document not found")
    return {"ok": True}


@api.get("/admin/users/{user_id}/conversations")
def admin_user_conversations(user_id: str, _=Depends(admin_user), s: Services = Depends(svc)):
    _managed_user(user_id, s)
    return {"conversations": s.db.list_conversations(user_id)}


@api.get("/admin/users/{user_id}")
def admin_user_detail(user_id: str, _=Depends(admin_user), s: Services = Depends(svc)):
    _managed_user(user_id, s)
    return s.db.admin_user_detail(user_id)


@api.get("/admin/conversations/{cid}")
def admin_conversation(cid: str, _=Depends(admin_user), s: Services = Depends(svc)):
    conv = s.db.conversation_any(cid)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return {"conversation": conv, "messages": s.db.get_messages(cid)}


# ============================================================ documents
@api.post("/documents/upload")
def upload_documents(files: List[UploadFile] = File(...), domain: str = Form("general"),
                     user=Depends(current_user), s: Services = Depends(svc)):
    processed, duplicates, errors = [], [], []
    limit = Config.max_file_size_bytes()
    for f in files:
        name = Path(f.filename or "file").name
        tmp_path = None
        try:
            ext = Path(name).suffix.lower()
            if ext not in Config.ALLOWED_EXTENSIONS:
                raise ValueError(f"Unsupported file type '{ext or 'none'}'. "
                                 f"Allowed: {', '.join(Config.ALLOWED_EXTENSIONS)}")
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp_path = Path(tmp.name)
                size = 0
                while chunk := f.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise ValueError(f"File exceeds the {Config.MAX_FILE_SIZE_MB} MB limit")
                    tmp.write(chunk)
            if size == 0:
                raise ValueError("File is empty")
            processed.append(s.ingest_file(user["user_id"], tmp_path, name, domain))
        except DuplicateDocument as d:
            duplicates.append({"filename": name, "existing_doc_id": d.existing["doc_id"]})
        except Exception as e:
            logger.warning("Upload failed for %s: %s", name, e)
            errors.append({"filename": name, "error": str(e)})
        finally:
            if tmp_path:
                tmp_path.unlink(missing_ok=True)
    return {"processed": processed, "duplicates": duplicates, "errors": errors}


@api.get("/documents")
def list_documents(domain: Optional[str] = None, search: Optional[str] = None, owner: Optional[str] = None,
                   user=Depends(current_user), s: Services = Depends(svc)):
    docs = s.db.list_documents(scope(user), domain, search, owner if scope(user) is None else None)
    return {"documents": docs, "total": len(docs)}


def _owned_document(doc_id: str, user: Dict, s: Services) -> Dict[str, Any]:
    doc = s.db.get_document(doc_id, scope(user))
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


def _public(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in doc.items() if k not in ("file_path", "file_hash")}


@api.get("/documents/{doc_id}")
def get_document(doc_id: str, user=Depends(current_user), s: Services = Depends(svc)):
    doc = _owned_document(doc_id, user, s)
    return {"document": _public(doc), "chunks": s.db.get_chunks(doc_id)}


@api.get("/documents/{doc_id}/file")
def download_document(doc_id: str, user=Depends(current_user), s: Services = Depends(svc)):
    doc = _owned_document(doc_id, user, s)
    if not Path(doc["file_path"]).exists():
        raise HTTPException(404, "Original file is no longer available")
    return FileResponse(doc["file_path"], filename=doc["filename"])


@api.get("/documents/{doc_id}/versions")
def document_versions(doc_id: str, user=Depends(current_user), s: Services = Depends(svc)):
    doc = _owned_document(doc_id, user, s)
    return {"versions": s.db.document_versions(doc["filename"], doc["user_id"])}


@api.delete("/documents/{doc_id}")
def delete_document(doc_id: str, user=Depends(current_user), s: Services = Depends(svc)):
    ok = s.admin_delete_document(doc_id) if scope(user) is None else s.delete_document(user["user_id"], doc_id)
    if not ok:
        raise HTTPException(404, "Document not found")
    return {"ok": True}


@api.post("/documents/{doc_id}/summarize")
def summarize(doc_id: str, req: SummarizeRequest, user=Depends(current_user), s: Services = Depends(svc)):
    doc = _owned_document(doc_id, user, s)
    kind = "short" if req.summary_type == "short" else "detailed"
    summary = s.cached_insight(doc_id, "summary", kind,
                               lambda: s.intelligence.generate_summary(s.document_text(doc_id)[0], kind), req.refresh)
    return {"doc_id": doc_id, "filename": doc["filename"], "summary": summary}


@api.post("/documents/{doc_id}/entities")
def entities(doc_id: str, refresh: bool = False, user=Depends(current_user), s: Services = Depends(svc)):
    doc = _owned_document(doc_id, user, s)
    out = s.cached_insight(doc_id, "entities", "",
                           lambda: s.intelligence.extract_entities(s.document_text(doc_id)[1]), refresh)
    return {"doc_id": doc_id, "filename": doc["filename"], **out}


@api.post("/documents/{doc_id}/extract")
def extract(doc_id: str, req: ExtractRequest, user=Depends(current_user), s: Services = Depends(svc)):
    doc = _owned_document(doc_id, user, s)
    data = s.cached_insight(
        doc_id, "extract", req.document_type,
        lambda: s.intelligence.extract_structured_info(s.document_text(doc_id)[1], req.document_type), req.refresh)
    return {"doc_id": doc_id, "filename": doc["filename"], "structured_data": data}


@api.post("/documents/compare")
def compare(req: CompareRequest, user=Depends(current_user), s: Services = Depends(svc)):
    a = _owned_document(req.doc_id_a, user, s)
    b = _owned_document(req.doc_id_b, user, s)
    _, ta = s.document_text(a["doc_id"])
    _, tb = s.document_text(b["doc_id"])
    return s.intelligence.compare_documents(ta, tb, f"{a['filename']} (v{a['version']})",
                                            f"{b['filename']} (v{b['version']})")


@api.post("/documents/{doc_id}/source-view")
def source_view(doc_id: str, req: SourceViewRequest, user=Depends(current_user), s: Services = Depends(svc)):
    """The cited passage shown inside its document (rendered PDF page or text) with the sentence highlighted"""
    from .source_view import build_source_view
    doc = _owned_document(doc_id, user, s)
    return build_source_view(doc, s.db.get_chunks(doc_id), req.chunk_id, req.page_number, req.focus)


@api.post("/messages/{message_id}/feedback")
def message_feedback(message_id: str, req: FeedbackRequest, user=Depends(current_user), s: Services = Depends(svc)):
    """Thumbs up / down on an answer; only the person who asked can rate it"""
    msg = s.db.set_feedback(message_id, user["user_id"], req.rating)
    if not msg:
        raise HTTPException(404, "Answer not found")
    return {"message": msg}


# ============================================================ conversations & query
@api.get("/conversations")
def list_conversations(user=Depends(current_user), s: Services = Depends(svc)):
    return {"conversations": s.db.list_conversations(scope(user))}


@api.post("/conversations")
def create_conversation(req: ConversationCreate, user=Depends(current_user), s: Services = Depends(svc)):
    return s.db.create_conversation(user["user_id"], req.title or "New chat", req.domain)


@api.get("/conversations/{cid}")
def get_conversation(cid: str, user=Depends(current_user), s: Services = Depends(svc)):
    conv = s.db.get_conversation(cid, scope(user))
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return {"conversation": conv, "messages": s.db.get_messages(cid)}


@api.patch("/conversations/{cid}")
def rename_conversation(cid: str, req: ConversationRename, user=Depends(current_user), s: Services = Depends(svc)):
    conv = s.db.rename_conversation(cid, scope(user), req.title)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@api.delete("/conversations/{cid}")
def delete_conversation(cid: str, user=Depends(current_user), s: Services = Depends(svc)):
    if not s.db.delete_conversation(cid, scope(user)):
        raise HTTPException(404, "Conversation not found")
    return {"ok": True}


@api.get("/suggestions")
def suggestions(domain: Optional[str] = None, user=Depends(current_user), s: Services = Depends(svc)):
    return {"questions": s.pipeline.suggested_questions(scope(user), domain)}


@api.post("/query")
def query(req: QueryRequest, user=Depends(current_user), s: Services = Depends(svc)):
    try:
        return s.ask(user["user_id"], question=req.question, conversation_id=req.conversation_id,
                     domain=req.domain, doc_id=req.doc_id, retrieval_mode=req.retrieval_mode, answer_style=req.answer_style,
                     search_all=scope(user) is None)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@api.post("/query/stream")
def query_stream(req: QueryRequest, user=Depends(current_user), s: Services = Depends(svc)):
    # Validate synchronously so errors become proper HTTP status codes
    if req.conversation_id and not s.db.get_conversation(req.conversation_id, user["user_id"]):
        raise HTTPException(404, "Conversation not found")
    if req.doc_id and not s.db.get_document(req.doc_id, scope(user)):
        raise HTTPException(404, "Document not found")

    def events():
        try:
            for event, payload in s.ask_stream(user["user_id"], question=req.question,
                                               conversation_id=req.conversation_id, domain=req.domain,
                                               doc_id=req.doc_id, retrieval_mode=req.retrieval_mode, answer_style=req.answer_style,
                                               search_all=scope(user) is None):
                yield f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"
        except Exception as e:
            logger.exception("Streaming query failed")
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ============================================================ evaluation
_eval_state: Dict[str, Any] = {"status": "idle", "progress": 0.0, "message": ""}
_eval_lock = threading.Lock()


@api.get("/evaluation/dataset")
def evaluation_dataset(user=Depends(current_user)):
    if not Config.EVAL_DATASET.exists():
        raise HTTPException(404, "Evaluation dataset not found")
    return json.loads(Config.EVAL_DATASET.read_text(encoding="utf-8"))


@api.post("/evaluation/run")
def run_evaluation(user=Depends(admin_user), s: Services = Depends(svc)):
    # administrators only: a run keeps the CPU busy for many minutes
    with _eval_lock:
        if _eval_state["status"] == "running":
            raise HTTPException(409, "An evaluation is already running")
        _eval_state.update(status="running", progress=0.0, message="Preparing benchmark corpus…")

    def progress(fraction: float, message: str):
        _eval_state.update(progress=round(fraction, 3), message=message)

    def worker():
        try:
            from .evaluation import run_benchmark
            report = run_benchmark(progress=progress)
            s.db.save_evaluation(report)
            _eval_state.update(status="done", progress=1.0, message="Benchmark complete")
        except Exception as e:
            logger.exception("Evaluation failed")
            _eval_state.update(status="error", message=str(e))

    threading.Thread(target=worker, daemon=True).start()
    return {"status": "running"}


@api.get("/evaluation/status")
def evaluation_status(user=Depends(current_user)):
    return dict(_eval_state)


@api.get("/evaluation/advanced")
def evaluation_advanced(user=Depends(current_user)):
    """Baselines, error bars, error analysis and the multilingual benchmark (python evaluation/run_advanced.py)"""
    path = Config.EVAL_RESULTS_DIR / "advanced_eval.json"
    return {"report": json.loads(path.read_text(encoding="utf-8")) if path.exists() else None}


@api.get("/evaluation/results")
def evaluation_results(user=Depends(current_user), s: Services = Depends(svc)):
    # runs started from the UI are stored in the database, command-line runs only in latest.json:
    # show whichever is newer
    latest = s.db.latest_evaluation()
    saved = Config.EVAL_RESULTS_DIR / "latest.json"
    if saved.exists():
        on_disk = json.loads(saved.read_text(encoding="utf-8"))
        if latest is None or on_disk.get("created_at", "") > latest.get("created_at", ""):
            latest = on_disk
    return {"latest": latest}


app.include_router(api)


@app.exception_handler(404)
async def not_found(request, exc):
    # Unknown API routes -> JSON 404; everything else -> SPA index.html (client-side routing)
    if request.url.path.startswith("/api") or not (Config.FRONTEND_DIST / "index.html").exists():
        detail = getattr(exc, "detail", "Not found")
        return JSONResponse({"detail": detail}, status_code=404)
    return FileResponse(Config.FRONTEND_DIST / "index.html")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    dist = Config.FRONTEND_DIST
    target = (dist / full_path).resolve()
    if full_path and target.is_file() and dist.resolve() in target.parents:
        return FileResponse(target)
    index = dist / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"message": "DocuMind API is running. Build the frontend (cd frontend && npm run build) "
                                    "or open the API docs at /api/docs."})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host=Config.API_HOST, port=Config.API_PORT)
