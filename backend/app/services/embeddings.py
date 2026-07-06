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


class HuggingFaceEmbeddingClient(EmbeddingClient):
    """
    Free embedding client using the HuggingFace Inference API's
    feature-extraction pipeline. No local model download, no GPU/heavy
    dependencies (just an HTTP call), which keeps it light enough to run on
    free-tier hosting like Render.

    Default model: sentence-transformers/all-MiniLM-L6-v2 (384-dim).
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        key = api_key or settings.HUGGINGFACE_API_KEY
        if not key:
            raise EmbeddingError(
                "HUGGINGFACE_API_KEY is not set. Get a free token at "
                "https://huggingface.co/settings/tokens, or use FakeEmbeddingClient for local dev/tests."
            )
        self.model = model or settings.EMBEDDING_MODEL
        self._url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model}"
        self._headers = {"Authorization": f"Bearer {key}"}

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
    )
    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cleaned = [t if t.strip() else " " for t in texts]
        import httpx

        try:
            response = httpx.post(
                self._url,
                headers=self._headers,
                json={"inputs": cleaned, "options": {"wait_for_model": True}},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise EmbeddingError(f"HuggingFace embedding request failed: {exc}") from exc

        # feature-extraction returns one vector per input (already mean-pooled)
        # for sentence-transformers models, or a token-level matrix per input
        # for plain transformer models — handle both by mean-pooling here.
        vectors: list[list[float]] = []
        for item in data:
            if isinstance(item[0], list):
                dim = len(item[0])
                summed = [0.0] * dim
                for token_vec in item:
                    for i, v in enumerate(token_vec):
                        summed[i] += v
                vectors.append([v / len(item) for v in summed])
            else:
                vectors.append(item)
        return vectors


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
    """
    Factory: picks the embedding backend based on settings.EMBEDDING_PROVIDER.

    - "huggingface" (default): free HuggingFace Inference API. Falls back to
      the fake client if no HUGGINGFACE_API_KEY is set (e.g. local dev).
    - "openai": paid OpenAI embeddings. Falls back to fake if no key is set.
    - "fake": always the deterministic offline stand-in.
    """
    settings = get_settings()

    if settings.EMBEDDING_PROVIDER == "openai":
        if settings.OPENAI_API_KEY:
            return OpenAIEmbeddingClient()
        return FakeEmbeddingClient(dim=settings.EMBEDDING_DIM)

    if settings.EMBEDDING_PROVIDER == "huggingface":
        if settings.HUGGINGFACE_API_KEY:
            return HuggingFaceEmbeddingClient()
        return FakeEmbeddingClient(dim=settings.EMBEDDING_DIM)

    return FakeEmbeddingClient(dim=settings.EMBEDDING_DIM)