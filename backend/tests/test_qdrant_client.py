from app.db.qdrant.collections import ALL_COLLECTIONS


def _vec(seed: float, dim: int = 64) -> list[float]:
    """Deterministic small vector for tests, distinct per seed."""
    return [seed + i * 0.01 for i in range(dim)]


def test_collections_created_on_init(vector_store):
    collections = {c.name for c in vector_store.client.get_collections().collections}
    for name in ALL_COLLECTIONS:
        assert name in collections


def test_upsert_and_search_resume(vector_store):
    vector_store.upsert_resume(
        resume_id="r1",
        candidate_id="c1",
        vector=_vec(0.9),
        payload={"skills": ["python", "fastapi"], "name": "Asha"},
    )
    vector_store.upsert_resume(
        resume_id="r2",
        candidate_id="c2",
        vector=_vec(0.1),
        payload={"skills": ["marketing"], "name": "Ravi"},
    )

    results = vector_store.search_resumes_for_job(job_vector=_vec(0.9), top_k=2)
    assert len(results) == 2
    # The closer vector (r1, seeded identically) should rank first.
    assert results[0].payload["resume_id"] == "r1"
    assert results[0].payload["name"] == "Asha"


def test_upsert_resume_point_id_is_deterministic_uuid(vector_store):
    point_id = vector_store.upsert_resume("r1", "c1", _vec(0.9), {})
    # Same external id must always coerce to the same Qdrant point id, so
    # re-upserting "r1" updates the existing point instead of duplicating it.
    assert point_id == vector_store.upsert_resume("r1", "c1", _vec(0.5), {})


def test_search_resumes_with_skill_filter(vector_store):
    vector_store.upsert_resume("r1", "c1", _vec(0.9), {"skills": ["python"]})
    vector_store.upsert_resume("r2", "c2", _vec(0.85), {"skills": ["java"]})

    results = vector_store.search_resumes_for_job(job_vector=_vec(0.9), top_k=5, skill_filter=["java"])
    assert len(results) == 1
    assert results[0].payload["resume_id"] == "r2"


def test_upsert_and_search_interview_history(vector_store):
    vector_store.upsert_interview_history(
        record_id="ih1", job_id="job1", candidate_id="c1", vector=_vec(0.5), payload={"summary": "Strong technical answer"}
    )
    results = vector_store.search_similar_interview_history(vector=_vec(0.5), job_id="job1")
    assert len(results) == 1
    assert results[0].payload["summary"] == "Strong technical answer"


def test_search_interview_history_filters_by_job(vector_store):
    vector_store.upsert_interview_history("ih1", "job1", "c1", _vec(0.5), {})
    vector_store.upsert_interview_history("ih2", "job2", "c2", _vec(0.5), {})

    results = vector_store.search_similar_interview_history(vector=_vec(0.5), job_id="job2")
    assert len(results) == 1
    assert results[0].payload["record_id"] == "ih2"


def test_get_qdrant_client_memory_url_string_selects_in_memory_mode(monkeypatch):
    """QDRANT_URL=':memory:' must behave identically to the in_memory=True flag."""
    from app.core.config import get_settings
    from app.db.qdrant.client import get_qdrant_client

    get_settings.cache_clear()
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    try:
        client = get_qdrant_client()
        client.get_collections()  # would raise a connection error if this weren't truly in-memory
    finally:
        get_settings.cache_clear()


def test_get_qdrant_client_local_path_uses_embedded_mode(tmp_path):
    """QDRANT_URL='local:<path>' must run embedded, no server process required — this is the
    zero-infra default a fresh clone relies on."""
    from app.db.qdrant.client import get_qdrant_client

    local_path = str(tmp_path / "qdrant_data")
    client = get_qdrant_client(url=f"local:{local_path}")
    client.get_collections()  # would raise a connection error if this tried to hit a real server
    import os

    assert os.path.isdir(local_path)


def test_get_qdrant_client_real_url_still_uses_remote_mode():
    """A normal http(s) URL must still build a remote client (not silently redirected to embedded mode)."""
    from app.db.qdrant.client import get_qdrant_client

    client = get_qdrant_client(url="http://localhost:6333")
    # We don't assert connectivity here (no server running in CI) — only
    # that the client was built in remote mode, not embedded/in-memory.
    assert client._client.__class__.__name__ != "QdrantLocal"
