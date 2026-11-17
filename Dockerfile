# ---------- Stage 1: build the React frontend ----------
FROM node:20-alpine AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Python API + models ----------
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/app/.cache/huggingface
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements.txt \
 && python -m spacy download en_core_web_sm
# Pre-download the embedding and reranker models into the image
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"
COPY backend/ backend/
COPY scripts/ scripts/
COPY evaluation/ evaluation/
COPY data/sample_documents/ data/sample_documents/
COPY --from=frontend /web/dist frontend/dist
EXPOSE 8000
CMD ["sh", "-c", "python scripts/seed_demo.py && python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000"]
