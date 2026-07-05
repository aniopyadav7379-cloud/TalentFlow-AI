from app.db.postgres.models import Candidate
from app.services.resume_ingestion import ResumeIngestionService
from tests.pdf_helpers import make_pdf_bytes

GOOD_RESUME_TEXT = """Ravi Sharma
ravi.sharma@example.com

4 years of experience in backend engineering.

Skills
Python, FastAPI, PostgreSQL, Docker
"""


def _make_candidate(db_session) -> Candidate:
    candidate = Candidate(full_name="Ravi Sharma", email="ravi.sharma@example.com")
    db_session.add(candidate)
    db_session.commit()
    return candidate


def test_ingest_successful_resume(db_session, vector_store, embedding_client, local_storage):
    candidate = _make_candidate(db_session)
    service = ResumeIngestionService(db_session, vector_store, embedding_client, local_storage)

    resume = service.ingest(candidate.id, "ravi_resume.pdf", make_pdf_bytes(GOOD_RESUME_TEXT))

    assert resume.parse_status == "parsed"
    assert "python" in resume.parsed_skills
    assert resume.parsed_experience_years == 4.0
    assert resume.embedding_id is not None
    assert resume.file_url.startswith("local://")
    assert local_storage.exists(resume.file_url)


def test_ingested_resume_is_searchable_in_qdrant(db_session, vector_store, embedding_client, local_storage):
    candidate = _make_candidate(db_session)
    service = ResumeIngestionService(db_session, vector_store, embedding_client, local_storage)
    resume = service.ingest(candidate.id, "ravi_resume.pdf", make_pdf_bytes(GOOD_RESUME_TEXT))

    # Search using the exact same text the resume was embedded from (fake
    # client is deterministic) — should retrieve this resume back.
    query_vector = embedding_client.embed_one(
        f"Skills: {', '.join(resume.parsed_skills)}\nExperience: {resume.parsed_experience_years} years\n{resume.raw_text}"
    )
    results = vector_store.search_resumes_for_job(job_vector=query_vector, top_k=1)
    assert len(results) == 1
    assert results[0].payload["resume_id"] == resume.id


def test_ingest_unparseable_resume_marks_failed_not_lost(db_session, vector_store, embedding_client, local_storage):
    candidate = _make_candidate(db_session)
    service = ResumeIngestionService(db_session, vector_store, embedding_client, local_storage)

    resume = service.ingest(candidate.id, "broken.pdf", b"not a real pdf")

    assert resume.parse_status == "failed"
    assert resume.embedding_id is None
    assert resume.id is not None  # still persisted, not silently dropped
    assert "PARSE_FAILED" in resume.raw_text


def test_ingest_persists_resume_row_queryable_after_commit(db_session, vector_store, embedding_client, local_storage):
    candidate = _make_candidate(db_session)
    service = ResumeIngestionService(db_session, vector_store, embedding_client, local_storage)
    resume = service.ingest(candidate.id, "ravi_resume.pdf", make_pdf_bytes(GOOD_RESUME_TEXT))

    from app.db.postgres.models import Resume

    reloaded = db_session.get(Resume, resume.id)
    assert reloaded is not None
    assert reloaded.parse_status == "parsed"
    assert reloaded.candidate_id == candidate.id
