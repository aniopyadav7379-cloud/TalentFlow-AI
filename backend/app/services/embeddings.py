"""
Embedding generation, abstracted behind `EmbeddingClient` so agents and
ingestion services never import `openai` directly.

`FakeEmbeddingClient` is deterministic (hash-based) — same text always
produces the same vector, different text produces a different vector — which
makes similarity-search tests meaningful without any network call or API key.
"""
from __future__ import annotations

import hashlib
import re
import struct
from abc import ABC, abstractmethod

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings


class EmbeddingError(Exception):
    """Raised when embedding generation fails after retries."""


class EmbeddingClient(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, same order."""

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class OpenAIEmbeddingClient(EmbeddingClient):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        key = api_key or settings.OPENAI_API_KEY
        if not key:
            raise EmbeddingError(
                "OPENAI_API_KEY is not set. Set it in .env, or use FakeEmbeddingClient for local dev/tests."
            )
        # Imported lazily so the openai package (and its network deps) is
        # only required when this client is actually instantiated.
        from openai import OpenAI

        self._client = OpenAI(api_key=key)
        self.model = model or settings.EMBEDDING_MODEL

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
    )
    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cleaned = [t if t.strip() else " " for t in texts]  # OpenAI rejects empty strings
        try:
            response = self._client.embeddings.create(model=self.model, input=cleaned)
        except Exception as exc:
            raise EmbeddingError(f"OpenAI embedding request failed: {exc}") from exc
        return [item.embedding for item in response.data]


class FakeEmbeddingClient(EmbeddingClient):
    """
    Deterministic, offline embedding stand-in for tests and local dev without
    an API key.

    Uses feature hashing (bag-of-words -> fixed-size vector via hashed token
    buckets), NOT a whole-string hash. This means texts sharing vocabulary
    produce vectors with genuinely higher cosine similarity — good enough to
    test ranking/search logic meaningfully offline. It is not a real semantic
    embedding (no synonym/context understanding) — never use in production.
    """

    def __init__(self, dim: int | None = None):
        self.dim = dim or get_settings().EMBEDDING_DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        tokens = self._tokenize(text)
        if not tokens:
            tokens = [""]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = sum(v * v for v in vector) ** 0.5
        if norm == 0:
            # Degenerate case (e.g. all collisions cancelled out): fall back
            # to a stable non-zero vector derived from the text hash so two
            # different empty-ish inputs still don't collide at the origin.
            return self._hash_to_unit_vector(text)
        return [v / norm for v in vector]

    def _hash_to_unit_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        needed_bytes = self.dim * 4
        repeated = (digest * (needed_bytes // len(digest) + 1))[:needed_bytes]
        raw_ints = struct.unpack(f"<{self.dim}i", repeated)
        max_int = 2**31 - 1
        vector = [x / max_int for x in raw_ints]
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norm for v in vector]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)?", text.lower())


def get_embedding_client() -> EmbeddingClient:
    """Factory: real OpenAI client if a key is configured, fake client otherwise (local dev without keys)."""
    settings = get_settings()
    if settings.OPENAI_API_KEY:
        return OpenAIEmbeddingClient()
    return FakeEmbeddingClient(dim=settings.EMBEDDING_DIM)
