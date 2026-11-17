"""
Test configuration. Points the app at a throw-away data directory and uses the
lightweight model fallbacks (hashing embedder + lexical reranker) so the suite
runs in seconds and is deterministic. Real-model quality is measured by the
benchmark in backend/evaluation.py instead.
Run:  python -m pytest -q
"""
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="documind_test_")
os.environ["DATA_DIR"] = _TMP
os.environ.setdefault("ENABLE_NEURAL_MODELS", "false")
os.environ["LLM_PROVIDER"] = "none"
os.environ["FRONTEND_DIST"] = str(Path(_TMP) / "no_frontend")
# fixed passwords for the automatically created accounts (the app itself has no built-in passwords)
os.environ["DEMO_PASSWORD"] = "Demo-Test-Pass-1"
os.environ["ADMIN_PASSWORD"] = "Admin-Test-Pass-1"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from backend.app import app
    with TestClient(app) as c:
        yield c


def _register(client, name):
    r = client.post("/api/auth/register", json={"username": name, "email": f"{name}@test.io", "password": "secret123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def alice(client):
    return _register(client, "alice")


@pytest.fixture(scope="session")
def bob(client):
    return _register(client, "bob")
