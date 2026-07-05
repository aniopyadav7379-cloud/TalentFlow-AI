"""
Qdrant collection schema for TalentFlow AI.

Three collections:
- resumes:            one point per parsed resume, used for candidate<->job matching
- jobs:                one point per job description, used symmetrically for
                        "find jobs similar to this candidate" style queries
- interview_history:   one point per completed interview transcript/summary,
                        used by the HR recommendation agent as long-term memory
                        (e.g. "how have similar answers scored before")
"""
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

RESUMES = "resumes"
JOBS = "jobs"
INTERVIEW_HISTORY = "interview_history"

ALL_COLLECTIONS = (RESUMES, JOBS, INTERVIEW_HISTORY)


@dataclass(frozen=True)
class HNSWProfile:
    """HNSW tuning: higher m/ef_construct = better recall, slower indexing."""
    m: int = 16
    ef_construct: int = 128
    full_scan_threshold: int = 10_000


DEFAULT_HNSW = HNSWProfile()


def _vector_params(dim: int, hnsw: HNSWProfile) -> qmodels.VectorParams:
    return qmodels.VectorParams(
        size=dim,
        distance=qmodels.Distance.COSINE,
        hnsw_config=qmodels.HnswConfigDiff(
            m=hnsw.m,
            ef_construct=hnsw.ef_construct,
            full_scan_threshold=hnsw.full_scan_threshold,
        ),
    )


def ensure_collections(client: QdrantClient, dim: int, hnsw: HNSWProfile = DEFAULT_HNSW) -> None:
    """Idempotently create all required collections if they don't already exist."""
    existing = {c.name for c in client.get_collections().collections}
    for name in ALL_COLLECTIONS:
        if name in existing:
            continue
        client.create_collection(
            collection_name=name,
            vectors_config=_vector_params(dim, hnsw),
        )
        # Payload indexes so filtered search (e.g. by job_id, skill) is fast.
        if name == RESUMES:
            client.create_payload_index(name, field_name="candidate_id", field_schema=qmodels.PayloadSchemaType.KEYWORD)
            client.create_payload_index(name, field_name="skills", field_schema=qmodels.PayloadSchemaType.KEYWORD)
        elif name == JOBS:
            client.create_payload_index(name, field_name="job_id", field_schema=qmodels.PayloadSchemaType.KEYWORD)
            client.create_payload_index(name, field_name="status", field_schema=qmodels.PayloadSchemaType.KEYWORD)
        elif name == INTERVIEW_HISTORY:
            client.create_payload_index(name, field_name="job_id", field_schema=qmodels.PayloadSchemaType.KEYWORD)
            client.create_payload_index(name, field_name="candidate_id", field_schema=qmodels.PayloadSchemaType.KEYWORD)


def reset_collections(client: QdrantClient, dim: int, hnsw: HNSWProfile = DEFAULT_HNSW) -> None:
    """Drop and recreate all collections. Destructive — used in tests/dev only."""
    for name in ALL_COLLECTIONS:
        client.delete_collection(name)
    ensure_collections(client, dim, hnsw)
