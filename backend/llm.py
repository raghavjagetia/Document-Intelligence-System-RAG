"""
LLM Client
Provider-agnostic text generation with streaming. Supported providers:
- groq       (OpenAI-compatible API, free tier, Llama models)
- gemini     (Google Generative Language API)
- anthropic  (Claude Messages API)
When no provider is configured/reachable, `available` is False and the RAG
pipeline falls back to neural extractive answering (see rag_pipeline.py).
"""
import json
import logging
import time
from typing import Dict, Iterator, Optional

import requests

from .config import Config

logger = logging.getLogger(__name__)


# Some models (e.g. gpt-oss) emit narrow no-break spaces and 【1】-style brackets; normalise them so
# answers display cleanly and "[1]" citations are recognised.
_TEXT_FIX = str.maketrans({"\u3010": "[", "\u3011": "]", "\u202f": " ", "\u00a0": " ", "\u2009": " ",
                           "\u2011": "-"})


def _clean(text: str) -> str:
    return text.translate(_TEXT_FIX)


def _sse_data(response) -> Iterator[str]:
    """Payloads of 'data:' lines from a server-sent-events response, decoded as UTF-8.
    (requests' decode_unicode guesses Latin-1 when the server omits a charset, which garbles
    every non-ASCII character, so whole lines are decoded explicitly instead.)"""
    for raw in response.iter_lines():
        if raw:
            line = raw.decode("utf-8", errors="replace")
            if line.startswith("data:"):
                yield line[5:].strip()


class LLMPaused(RuntimeError):
    """The provider rate-limited us for a long time; callers fall back to offline answers"""


class LLMClient:
    # provider -> time.monotonic() until which it asked us not to call it (shared by all clients)
    _paused_until: Dict[str, float] = {}

    def __init__(self, provider: Optional[str] = None, retries: Optional[int] = None, max_wait: Optional[float] = None):
        self.provider = self._resolve_provider(provider or Config.LLM_PROVIDER)
        # how often to wait and retry when the provider rate-limits a request (HTTP 429) before giving up,
        # and the longest single wait worth doing (interactive use keeps this short)
        self.retries = Config.LLM_RATE_LIMIT_RETRIES if retries is None else retries
        self.max_wait = Config.LLM_RETRY_MAX_WAIT if max_wait is None else max_wait
        self.model = {
            "groq": Config.GROQ_MODEL,
            "gemini": Config.GEMINI_MODEL,
            "anthropic": Config.ANTHROPIC_MODEL,
        }.get(self.provider, "none")

    # ---------- provider selection ----------
    def _resolve_provider(self, requested: str) -> str:
        if requested != "auto":
            return requested
        if Config.GROQ_API_KEY:
            return "groq"
        if Config.GEMINI_API_KEY:
            return "gemini"
        if Config.ANTHROPIC_API_KEY:
            return "anthropic"
        return "none"

    @property
    def available(self) -> bool:
        return self.provider in ("groq", "gemini", "anthropic")

    @property
    def label(self) -> str:
        return f"{self.provider}/{self.model}" if self.available else "none"

    # ---------- public API ----------
    def generate(self, prompt: str, system: str = "", max_tokens: Optional[int] = None) -> str:
        return "".join(self.stream(prompt, system, max_tokens))

    def stream(self, prompt: str, system: str = "", max_tokens: Optional[int] = None) -> Iterator[str]:
        if not self.available:
            raise RuntimeError("No LLM provider is configured")
        max_tokens = max_tokens or Config.LLM_MAX_TOKENS
        handler = {
            "groq": self._stream_groq,
            "gemini": self._stream_gemini,
            "anthropic": self._stream_anthropic,
        }[self.provider]
        remaining = self.paused_seconds
        if remaining > 0:
            # the provider told us to back off: answer offline right away instead of waiting
            raise LLMPaused(f"{self.provider} rate limit - resumes in {remaining:.0f} s")
        for attempt in range(self.retries + 1):
            started = False
            try:
                for piece in handler(prompt, system, max_tokens):
                    started = True
                    yield piece
                return
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status != 429 or started:
                    raise
                raw = e.response.headers.get("retry-after", "") if e.response is not None else ""
                wait = float(raw) if raw.replace(".", "", 1).isdigit() else 5.0
                # a short wait is worth it; a long one (e.g. the daily free-tier allowance is used up) is not:
                # pause this provider for that long and let callers fall back to offline answers at once
                if wait > self.max_wait or attempt == self.retries:
                    LLMClient._paused_until[self.provider] = time.monotonic() + wait
                    raise
                time.sleep(wait)

    @property
    def paused_seconds(self) -> float:
        """Seconds until the provider accepts requests again after a long rate-limit (0 if not paused)"""
        return max(0.0, LLMClient._paused_until.get(self.provider, 0.0) - time.monotonic())

    # ---------- providers ----------
    def _stream_groq(self, prompt: str, system: str, max_tokens: int) -> Iterator[str]:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        with requests.post(
            f"{Config.GROQ_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"},
            json={"model": self.model, "messages": messages, "temperature": Config.LLM_TEMPERATURE,
                  "max_tokens": max_tokens, "stream": True},
            stream=True, timeout=Config.LLM_TIMEOUT,
        ) as r:
            r.raise_for_status()
            for data in _sse_data(r):
                if data == "[DONE]":
                    break
                delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
                if delta:
                    yield _clean(delta)

    def _stream_gemini(self, prompt: str, system: str, max_tokens: int) -> Iterator[str]:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": Config.LLM_TEMPERATURE, "maxOutputTokens": max_tokens},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
               f":streamGenerateContent?alt=sse&key={Config.GEMINI_API_KEY}")
        with requests.post(url, json=body, stream=True, timeout=Config.LLM_TIMEOUT) as r:
            r.raise_for_status()
            for data in _sse_data(r):
                payload = json.loads(data)
                for cand in payload.get("candidates", []):
                    for part in cand.get("content", {}).get("parts", []):
                        if part.get("text"):
                            yield _clean(part["text"])

    def _stream_anthropic(self, prompt: str, system: str, max_tokens: int) -> Iterator[str]:
        body = {"model": self.model, "max_tokens": max_tokens, "temperature": Config.LLM_TEMPERATURE,
                "messages": [{"role": "user", "content": prompt}], "stream": True}
        if system:
            body["system"] = system
        with requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": Config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json=body, stream=True, timeout=Config.LLM_TIMEOUT,
        ) as r:
            r.raise_for_status()
            for data in _sse_data(r):
                event = json.loads(data)
                if event.get("type") == "content_block_delta":
                    text = event.get("delta", {}).get("text")
                    if text:
                        yield _clean(text)
