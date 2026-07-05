from app.db.postgres.models import Job, JobStatus, User, UserRole
from app.services.job_ingestion import JobIngestionService


def _make_user(db_session) -> User:
    user = User(email="recruiter@talentflow.ai", hashed_password="x", full_name="Recruiter", role=UserRole.RECRUITER)
    db_session.add(user)
    db_session.commit()
    return user


def test_ingest_job_sets_embedding_id(db_session, vector_store, embedding_client):
    user = _make_user(db_session)
    job = Job(
        title="Backend Engineer",
        description="Build and scale REST APIs using Python and FastAPI.",
        skills=["python", "fastapi", "postgresql"],
        status=JobStatus.OPEN,
        created_by_id=user.id,
    )
    db_session.add(job)
    db_session.commit()

    service = JobIngestionService(db_session, vector_store, embedding_client)
    ingested = service.ingest(job)

    assert ingested.embedding_id is not None


def test_ingested_job_is_searchable_and_finds_matching_resume(db_session, vector_store, embedding_client):
    """
    This is the core semantic-matching contract: a job embedding and a resume
    embedding built from overlapping skill text should be nearest neighbors.
    """
    user = _make_user(db_session)
    job = Job(
        title="Backend Engineer",
        description="Build and scale REST APIs using Python and FastAPI.",
        skills=["python", "fastapi", "postgresql"],
        status=JobStatus.OPEN,
        created_by_id=user.id,
    )
    db_session.add(job)
    db_session.commit()
    JobIngestionService(db_session, vector_store, embedding_client).ingest(job)

    job_vector = embedding_client.embed_one(
        "Backend Engineer\nRequired skills: python, fastapi, postgresql\n"
        "Build and scale REST APIs using Python and FastAPI."
    )

    # A resume embedded with near-identical skill text should be a close match.
    matching_vector = embedding_client.embed_one("Skills: python, fastapi, postgresql\nBackend engineer resume text")
    vector_store.upsert_resume("resume-1", "candidate-1", matching_vector, {"skills": ["python", "fastapi"]})

    # An unrelated resume should not be the top match.
    unrelated_vector = embedding_client.embed_one("Skills: photoshop, illustrator\nGraphic designer resume text")
    vector_store.upsert_resume("resume-2", "candidate-2", unrelated_vector, {"skills": ["photoshop"]})

    results = vector_store.search_resumes_for_job(job_vector=job_vector, top_k=2)
    assert results[0].payload["resume_id"] == "resume-1"
