#!/usr/bin/env bash
# One-time setup for GitHub Codespaces (safe to re-run).
set -e
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
  python -m venv .venv
fi
PY=.venv/bin/python
$PY -m pip install --upgrade pip
$PY -m pip install torch --index-url https://download.pytorch.org/whl/cpu
$PY -m pip install -r requirements.txt
$PY -m spacy download en_core_web_sm

# Download the embedding + reranker models now so the first start is faster
$PY -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

(cd frontend && npm ci && npm run build)
echo "DocuMind setup complete."
