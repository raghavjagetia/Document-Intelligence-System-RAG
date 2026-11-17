"""
Configuration Manager
Reads settings from environment variables (and an optional .env file).
All relative paths are resolved against the project root so the app works
regardless of the current working directory.
"""
import os
from pathlib import Path
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _path(env_name: str, default: str) -> Path:
    p = Path(os.getenv(env_name, default))
    return p if p.is_absolute() else PROJECT_ROOT / p


def _bool(env_name: str, default: str) -> bool:
    return os.getenv(env_name, default).strip().lower() in ("1", "true", "yes", "on")


class Config:
    """Application configuration"""

    APP_NAME: str = "DocuMind - AI Document Intelligence & Hybrid RAG"
    VERSION: str = "3.0.0"

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    ALLOWED_ORIGINS: List[str] = [
        o.strip() for o in os.getenv(
            "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000"
        ).split(",") if o.strip()
    ]

    # Storage
    DATA_DIR: Path = _path("DATA_DIR", "data")
    DB_PATH: Path = DATA_DIR / "app.db"
    UPLOAD_DIR: Path = DATA_DIR / "uploads"
    INDEX_DIR: Path = DATA_DIR / "index"
    FRONTEND_DIST: Path = _path("FRONTEND_DIST", "frontend/dist")
    SAMPLE_DOCS_DIR: Path = _path("SAMPLE_DOCS_DIR", "data/sample_documents")
    EVAL_DATASET: Path = _path("EVAL_DATASET", "evaluation/eval_dataset.json")
    EVAL_RESULTS_DIR: Path = _path("EVAL_RESULTS_DIR", "evaluation/results")

    # Auth
    SESSION_TTL_HOURS: int = int(os.getenv("SESSION_TTL_HOURS", "168"))
    # No built-in passwords: set these in .env, or leave them empty and a random password is generated when the
    # account is first created and written to data/initial_credentials.txt (private, never committed)
    DEMO_USERNAME: str = os.getenv("DEMO_USERNAME", "demo")
    DEMO_PASSWORD: str = os.getenv("DEMO_PASSWORD", "")
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
    # password of the sample accounts created by scripts/seed_demo.py (random if empty)
    SEED_USER_PASSWORD: str = os.getenv("SEED_USER_PASSWORD", "")
    # brute-force protection: lock an account for LOGIN_LOCKOUT_MINUTES after LOGIN_MAX_FAILURES wrong passwords
    LOGIN_MAX_FAILURES: int = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
    LOGIN_LOCKOUT_MINUTES: int = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))
    SIGNUPS_PER_HOUR_PER_IP: int = int(os.getenv("SIGNUPS_PER_HOUR_PER_IP", "10"))

    # Models
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    RERANKER_MODEL: str = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    ENABLE_OCR: bool = _bool("ENABLE_OCR", "true")
    # Set to "false" to force the lightweight fallbacks (useful for fast unit tests)
    ENABLE_NEURAL_MODELS: bool = _bool("ENABLE_NEURAL_MODELS", "true")

    # LLM: "auto" picks the first configured provider: groq -> gemini -> anthropic -> none
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto").lower()
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "600"))
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "60"))
    # on a rate limit (HTTP 429) wait and retry this many times before falling back to offline answers
    LLM_RATE_LIMIT_RETRIES: int = int(os.getenv("LLM_RATE_LIMIT_RETRIES", "2"))
    LLM_RETRY_MAX_WAIT: float = float(os.getenv("LLM_RETRY_MAX_WAIT", "5"))
    # Number of top passages given to the LLM as numbered sources
    LLM_CONTEXT_CHUNKS: int = int(os.getenv("LLM_CONTEXT_CHUNKS", "4"))
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    # Any OpenAI-compatible endpoint works here (Groq by default)
    GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    # Document processing
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "700"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "25"))
    ALLOWED_EXTENSIONS: List[str] = [
        ".pdf", ".docx", ".txt", ".md", ".html", ".htm", ".csv", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg"
    ]

    # Retrieval
    TOP_K: int = int(os.getenv("TOP_K", "5"))
    CANDIDATE_K: int = int(os.getenv("CANDIDATE_K", "30"))
    RRF_K: int = int(os.getenv("RRF_K", "60"))
    # Minimum cross-encoder relevance (sigmoid of logit) required to answer instead of abstaining
    ABSTAIN_THRESHOLD: float = float(os.getenv("ABSTAIN_THRESHOLD", "0.05"))
    # ...and minimum dense cosine similarity; abstain only when BOTH signals are weak
    ABSTAIN_DENSE_THRESHOLD: float = float(os.getenv("ABSTAIN_DENSE_THRESHOLD", "0.40"))
    # coverage rule: abstain when >=2 key question terms (>=40%) are missing AND top dense similarity is below this
    ABSTAIN_COVERAGE_DENSE: float = float(os.getenv("ABSTAIN_COVERAGE_DENSE", "0.60"))
    # ...and at least one missing noun has no evidence word with embedding similarity >= this (no synonym)
    ABSTAIN_SYNONYM_SIM: float = float(os.getenv("ABSTAIN_SYNONYM_SIM", "0.65"))
    # Same idea for the lexical fallback reranker, whose scores live on a different scale
    ABSTAIN_THRESHOLD_LEXICAL: float = float(os.getenv("ABSTAIN_THRESHOLD_LEXICAL", "0.35"))

    DOMAINS: List[str] = ["general", "hr", "legal", "healthcare", "finance"]

    @classmethod
    def max_file_size_bytes(cls) -> int:
        return cls.MAX_FILE_SIZE_MB * 1024 * 1024

    @classmethod
    def ensure_directories(cls) -> None:
        for d in (cls.DATA_DIR, cls.UPLOAD_DIR, cls.INDEX_DIR):
            d.mkdir(parents=True, exist_ok=True)
