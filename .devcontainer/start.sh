#!/usr/bin/env bash
# Starts DocuMind when the codespace is opened (runs in its own terminal; keep it open).
cd "$(dirname "$0")/.."
PY=.venv/bin/python
export PYTHONUNBUFFERED=1

# Already running? (e.g. the codespace was opened in a second browser tab)
if curl -s -o /dev/null http://localhost:8000/; then
  echo "DocuMind is already running on port 8000."
  exit 0
fi

# Allow the Codespaces URL in CORS (the UI is served from the same origin, this is just a safety net)
if [ -n "$CODESPACE_NAME" ]; then
  export ALLOWED_ORIGINS="https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev},http://localhost:8000"
fi

# First start only: create demo accounts/documents/chats. The LLM is switched off for seeding so it
# does not spend the Groq free-tier quota (about 250 questions are asked).
if [ ! -f data/app.db ]; then
  echo "Seeding demo data (first start only, takes 10-20 minutes)..."
  LLM_PROVIDER=none $PY scripts/seed_demo.py
fi

echo "Starting DocuMind on port 8000 - remember to set the port to Public in the Ports tab."
exec $PY -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
