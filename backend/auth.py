"""
Authentication
- Passwords: PBKDF2-HMAC-SHA256, 16-byte random salt, 200k iterations, constant-time verify
- Sessions: 256-bit random bearer tokens; only their SHA-256 hash is stored in the
  database, so a leaked database does not leak usable tokens. Tokens expire.
- No built-in passwords: the administrator and demo accounts get their password from the
  environment (.env), or a random one generated on first start and written to a private file
  (data/initial_credentials.txt) - never to the code, the docs or the log.
- Brute-force protection: an account is locked for 15 minutes after 5 wrong passwords, and one
  network address can make only a limited number of failed logins and sign-ups.
"""
import hashlib
import hmac
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .config import Config
from .database import Database

logger = logging.getLogger(__name__)

ITERATIONS = 200_000
PASSWORD_MIN_LENGTH = 8
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str, salt: Optional[bytes] = None, iterations: int = ITERATIONS) -> str:
    salt = salt or os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, key_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(key, bytes.fromhex(key_hex))
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_problem(password: str) -> Optional[str]:
    """Why a new password is not acceptable (None if it is)"""
    if len(password or "") < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
    return None


def initial_password(kind: str, username: str, configured: str) -> str:
    """The password for an account created automatically: the configured one, or a random one that is written
    (once) to data/initial_credentials.txt so the owner can sign in and change it"""
    if configured:
        return configured
    password = secrets.token_urlsafe(12)
    path = Config.DATA_DIR / "initial_credentials.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')}  {kind} account  {username}  {password}\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    logger.warning("Created the %s account with a random password; it is in %s (set it in .env to choose your own)",
                   kind, path)
    return password


class LoginLimiter:
    """Counts failed sign-ins in a sliding window: per account (locks it for `lockout` seconds after
    `max_failures`) and per network address (stops one machine from trying many accounts)"""

    def __init__(self, max_failures: int = 5, window: float = 900, lockout: float = 900, max_per_ip: int = 30):
        self.max_failures, self.window, self.lockout, self.max_per_ip = max_failures, window, lockout, max_per_ip
        self._fails: Dict[str, List[float]] = {}
        self._locked_until: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> List[float]:
        times = [t for t in self._fails.get(key, []) if now - t < self.window]
        self._fails[key] = times
        return times

    def retry_after(self, username: str, ip: str) -> int:
        """Seconds until a sign-in may be tried again (0 = allowed now)"""
        now = time.monotonic()
        with self._lock:
            wait = self._locked_until.get("u:" + username.lower(), 0) - now
            if len(self._recent("ip:" + ip, now)) >= self.max_per_ip:
                wait = max(wait, self._fails["ip:" + ip][0] + self.window - now)
            return max(0, int(wait + 0.999))

    def failed(self, username: str, ip: str) -> None:
        now = time.monotonic()
        with self._lock:
            for key in ("u:" + username.lower(), "ip:" + ip):
                self._recent(key, now).append(now)
            if len(self._fails["u:" + username.lower()]) >= self.max_failures:
                self._locked_until["u:" + username.lower()] = now + self.lockout
                self._fails["u:" + username.lower()] = []

    def succeeded(self, username: str) -> None:
        with self._lock:
            self._fails.pop("u:" + username.lower(), None)
            self._locked_until.pop("u:" + username.lower(), None)


class RateLimiter:
    """At most `limit` events per `window` seconds per key (e.g. sign-ups per network address)"""

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self._events: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            events = [t for t in self._events.get(key, []) if now - t < self.window]
            if len(events) >= self.limit:
                self._events[key] = events
                return False
            events.append(now)
            self._events[key] = events
            return True


class AuthService:
    def __init__(self, db: Database):
        self.db = db

    def validate_registration(self, username: str, email: str, password: str) -> Optional[str]:
        if not USERNAME_RE.match(username or ""):
            return "Username must be 3-32 characters: letters, digits, '.', '_' or '-'"
        if not EMAIL_RE.match(email or ""):
            return "Please enter a valid email address"
        return password_problem(password) or self._taken(username, email)

    def _taken(self, username: str, email: str) -> Optional[str]:
        if self.db.user_exists(username, email):
            return "Username or email is already registered"
        return None

    def register(self, username: str, email: str, password: str, role: str = "user") -> Dict:
        return self.db.create_user(username.strip(), email.strip().lower(), hash_password(password), role)

    def authenticate(self, username_or_email: str, password: str) -> Optional[Dict]:
        row = self.db.get_user_with_hash((username_or_email or "").strip())
        if not row or not verify_password(password or "", row["password_hash"]):
            return None
        if row.get("disabled"):
            raise PermissionError("This account has been suspended by an administrator")
        return self.db.get_user(row["user_id"])

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self.db.create_session(_token_hash(token), user_id, Config.SESSION_TTL_HOURS)
        return token

    def user_for_token(self, token: Optional[str]) -> Optional[Dict]:
        if not token:
            return None
        return self.db.get_session_user(_token_hash(token))

    def logout(self, token: str) -> None:
        self.db.delete_session(_token_hash(token))

    def ensure_demo_user(self) -> Tuple[Dict, bool]:
        """Create the demo account if missing. Returns (user, created)."""
        row = self.db.get_user_with_hash(Config.DEMO_USERNAME)
        if row:
            return self.db.get_user(row["user_id"]), False
        user = self.db.create_user(Config.DEMO_USERNAME, "demo@documind.local",
                                   hash_password(initial_password("demo", Config.DEMO_USERNAME, Config.DEMO_PASSWORD)),
                                   role="user", user_id="usr_demo")
        return user, True

    def ensure_admin_user(self) -> Tuple[Dict, bool]:
        """Create the administrator account if missing. Returns (user, created)."""
        row = self.db.get_user_with_hash(Config.ADMIN_USERNAME)
        if row:
            return self.db.get_user(row["user_id"]), False
        user = self.db.create_user(Config.ADMIN_USERNAME, "admin@documind.local",
                                   hash_password(initial_password("administrator", Config.ADMIN_USERNAME,
                                                                 Config.ADMIN_PASSWORD)),
                                   role="admin", user_id="usr_admin")
        return user, True
