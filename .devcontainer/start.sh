#!/usr/bin/env bash
# Starts DocuMind in the background on every codespace start. Log: /tmp/documind.log
cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOG=/tmp/documind.log

# Already running? (e.g. the start command ran twice)
if curl -s -o /dev/null http://localhost:8000/; then
  echo "DocuMind is already running on port 8000."
  exit 0
fi

# Allow the Codespaces URL in CORS (the UI is served from the same origin, this is just a safety net)
if [ -n "$CODESPACE_NAME" ]; then
  export ALLOWED_ORIGINS="https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev},http://localhost:8000"
fi

setsid nohup bash -c "
  # First start only: create demo accounts/documents/chats. LLM is switched off for seeding so it
  # does not spend the Groq free-tier quota (about 250 questions are asked).
  if [ ! -f data/app.db ]; then
    echo 'Seeding demo data (first start, takes several minutes)...'
    LLM_PROVIDER=none $PY scripts/seed_demo.py
  fi
  exec $PY -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
" > "$LOG" 2>&1 < /dev/null &

# Try to make the port public automatically (may need doing by hand in the Ports tab)
if [ -n "$CODESPACE_NAME" ] && command -v gh >/dev/null; then
  gh codespace ports visibility 8000:public -c "$CODESPACE_NAME" >/dev/null 2>&1 || true
fi

echo "DocuMind is starting in the background. Follow progress with:  tail -f $LOG"
