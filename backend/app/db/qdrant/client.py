"""
Qdrant client factory + typed helper functions.

Agents never touch qdrant_client directly — they go through the functions
here, which keeps payload shape and error handling in one place and makes
the vector store swappable/mockable in tests.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import get_settings
from app.db.qdrant.collections import ensure_collections


# Qdrant point IDs must be an unsigned int or a valid UUID string — arbitrary
# strings (e.g. a slug, or a non-UUID external ID) are rejected. We deterministically
# map any external ID to a UUID5 so callers can pass whatever ID scheme they use
# without needing to know this constraint, while the original ID is preserved
# in the payload for exact lookups.
_POINT_ID_NAMESPACE = uuid.UUID("6f6a6b1e-2f3a-4a3a-9b1a-3f6e2b1a7c5d")


def _coerce_point_id(external_id: str) -> str:
    try:
        return str(uuid.UUID(external_id))
    except (ValueError, AttributeError, TypeError):
        return str(uuid.uuid5(_POINT_ID_NAMESPACE, str(external_id)))


def get_qdrant_client(url: str | None = None, api_key: str | None = None, in_memory: bool = False) -> QdrantClient:
    """
    Build a Qdrant client.

    Three modes, so this app can run with zero external infra for local dev
    (same philosophy as the SQLite fallback for Postgres):
    - `in_memory=True`: fully in-process, nothing persisted — used by tests.
    - `QDRANT_URL=":memory:"`: same as above, selected via config.
    - `QDRANT_URL="local:<path>"`: embedded Qdrant persisted to a local
      directory — no server process required, survives restarts. Good
      default for solo/local development.
    - Any other `QDRANT_URL`: a real Qdrant server (production/staging).
    """
    if in_memory:
        return QdrantClient(location=":memory:")

    settings = get_settings()
    resolved_url = url or settings.QDRANT_URL

    if resolved_url == ":memory:":
        return QdrantClient(location=":memory:")
    if resolved_url.startswith("local:"):
        local_path = resolved_url.removeprefix("local:")
        return QdrantClient(path=local_path)

    return QdrantClient(
        url=resolved_url,
        api_key=api_key or settings.QDRANT_API_KEY,
        timeout=settings.QDRANT_TIMEOUT,
    )


@dataclass
class ScoredMatch:
    point_id: str
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


class VectorStore:
    """High-level operations used by the agent layer. One instance per request/job."""

    def __init__(self, client: QdrantClient | None = None, dim: int | None = None):
        self.client = client or get_qdrant_client()
        self.dim = dim or get_settings().EMBEDDING_DIM
        ensure_collections(self.client, self.dim)

    def upsert_resume(self, resume_id: str, candidate_id: str, vector: list[float], payload: dict[str, Any]) -> str:
        resume_id = resume_id or str(uuid.uuid4())
        point_id = _coerce_point_id(resume_id)
        self.client.upsert(
            collection_name="resumes",
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"resume_id": resume_id, "candidate_id": candidate_id, **payload},
                )
            ],
        )
        return point_id

    def upsert_job(self, job_id: str, vector: list[float], payload: dict[str, Any]) -> str:
        job_id = job_id or str(uuid.uuid4())
        point_id = _coerce_point_id(job_id)
        self.client.upsert(
            collection_name="jobs",
            points=[qmodels.PointStruct(id=point_id, vector=vector, payload={"job_id": job_id, **payload})],
        )
        return point_id

    def upsert_interview_history(self, record_id: str, job_id: str, candidate_id: str, vector: list[float], payload: dict[str, Any]) -> str:
        record_id = record_id or str(uuid.uuid4())
        point_id = _coerce_point_id(record_id)
        self.client.upsert(
            collection_name="interview_history",
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"record_id": record_id, "job_id": job_id, "candidate_id": candidate_id, **payload},
                )
            ],
        )
        return point_id

    def search_resumes_for_job(
        self, job_vector: list[float], top_k: int = 10, skill_filter: list[str] | None = None
    ) -> list[ScoredMatch]:
        query_filter = None
        if skill_filter:
            query_filter = qmodels.Filter(
                should=[qmodels.FieldCondition(key="skills", match=qmodels.MatchValue(value=s)) for s in skill_filter]
            )
        results = self.client.search(
            collection_name="resumes",
            query_vector=job_vector,
            query_filter=query_filter,
            limit=top_k,
        )
        return [ScoredMatch(point_id=str(r.id), score=r.score, payload=r.payload or {}) for r in results]

    def search_similar_interview_history(self, vector: list[float], job_id: str | None = None, top_k: int = 5) -> list[ScoredMatch]:
        query_filter = None
        if job_id:
            query_filter = qmodels.Filter(must=[qmodels.FieldCondition(key="job_id", match=qmodels.MatchValue(value=job_id))])
        results = self.client.search(
            collection_name="interview_history",
            query_vector=vector,
            query_filter=query_filter,
            limit=top_k,
        )
        return [ScoredMatch(point_id=str(r.id), score=r.score, payload=r.payload or {}) for r in results]
