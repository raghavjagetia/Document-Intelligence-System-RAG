#!/usr/bin/env bash
# DocuMind one-command start (macOS / Linux / Git Bash)
set -e
cd "$(dirname "$0")"
PY=.venv/bin/python; [ -f .venv/Scripts/python.exe ] && PY=.venv/Scripts/python.exe
if [ ! -d .venv ]; then
  python3 -m venv .venv
  PY=.venv/bin/python; [ -f .venv/Scripts/python.exe ] && PY=.venv/Scripts/python.exe
  $PY -m pip install --upgrade pip
  $PY -m pip install torch --index-url https://download.pytorch.org/whl/cpu
  $PY -m pip install -r requirements.txt
  $PY -m spacy download en_core_web_sm
fi
[ -f frontend/dist/index.html ] || (cd frontend && npm install && npm run build)
[ -f data/app.db ] || $PY scripts/seed_demo.py
echo "DocuMind running at http://localhost:8000  (first-run passwords: data/initial_credentials.txt)"
exec $PY -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
