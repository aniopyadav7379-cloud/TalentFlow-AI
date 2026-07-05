import pytest

from app.agents.base import AgentError
from app.agents.candidate_matching_agent import CandidateMatchingAgent


def test_rank_candidates_orders_by_match_score(db_session, vector_store, embedding_client):
    # Strong match: shares all required skills.
    strong_vec = embedding_client.embed_one("Skills: python, fastapi, postgresql\nBackend engineer.")
    vector_store.upsert_resume("r-strong", "c-strong", strong_vec, {"skills": ["python", "fastapi", "postgresql"]})

    # Weak match: no overlapping skills.
    weak_vec = embedding_client.embed_one("Skills: photoshop, illustrator\nGraphic designer.")
    vector_store.upsert_resume("r-weak", "c-weak", weak_vec, {"skills": ["photoshop", "illustrator"]})

    agent = CandidateMatchingAgent(vector_store, embedding_client)
    results = agent.rank_candidates(
        job_title="Backend Engineer",
        job_description="Build APIs using Python and FastAPI.",
        job_skills=["python", "fastapi", "postgresql"],
        top_k=5,
    )

    assert results[0].resume_id == "r-strong"
    assert results[0].match_score > results[-1].match_score
    assert "python" in results[0].matched_skills


def test_rank_candidates_computes_missing_skills(db_session, vector_store, embedding_client):
    vec = embedding_client.embed_one("Skills: python\nBackend developer.")
    vector_store.upsert_resume("r1", "c1", vec, {"skills": ["python"]})

    agent = CandidateMatchingAgent(vector_store, embedding_client)
    results = agent.rank_candidates(
        job_title="Backend Engineer",
        job_description="Build APIs.",
        job_skills=["python", "kubernetes", "aws"],
        top_k=5,
    )

    assert "python" in results[0].matched_skills
    assert "kubernetes" in results[0].missing_skills
    assert "aws" in results[0].missing_skills


def test_rank_candidates_match_score_is_bounded(db_session, vector_store, embedding_client):
    vec = embedding_client.embed_one("Skills: python, fastapi\nBackend engineer.")
    vector_store.upsert_resume("r1", "c1", vec, {"skills": ["python", "fastapi"]})

    agent = CandidateMatchingAgent(vector_store, embedding_client)
    results = agent.rank_candidates(
        job_title="Backend Engineer", job_description="Build APIs.", job_skills=["python", "fastapi"], top_k=5
    )
    assert 0 <= results[0].match_score <= 100


def test_rank_candidates_raises_when_job_has_no_signal(vector_store, embedding_client):
    agent = CandidateMatchingAgent(vector_store, embedding_client)
    with pytest.raises(AgentError):
        agent.rank_candidates(job_title="Mystery Role", job_description="   ", job_skills=[], top_k=5)


def test_rank_candidates_respects_top_k(db_session, vector_store, embedding_client):
    for i in range(5):
        vec = embedding_client.embed_one(f"Skills: python\nCandidate {i} backend engineer.")
        vector_store.upsert_resume(f"r{i}", f"c{i}", vec, {"skills": ["python"]})

    agent = CandidateMatchingAgent(vector_store, embedding_client)
    results = agent.rank_candidates(
        job_title="Backend Engineer", job_description="Build APIs.", job_skills=["python"], top_k=2
    )
    assert len(results) == 2


def test_rank_candidates_no_resumes_returns_empty_list(vector_store, embedding_client):
    agent = CandidateMatchingAgent(vector_store, embedding_client)
    results = agent.rank_candidates(
        job_title="Backend Engineer", job_description="Build APIs.", job_skills=["python"], top_k=5
    )
    assert results == []
