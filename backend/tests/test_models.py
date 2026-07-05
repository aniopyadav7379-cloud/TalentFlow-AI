from app.db.postgres.models import (
    Application,
    ApplicationStatus,
    Candidate,
    Evaluation,
    Interview,
    InterviewResponse,
    Job,
    JobStatus,
    Resume,
    User,
    UserRole,
)


def _make_user(db_session):
    user = User(email="recruiter@talentflow.ai", hashed_password="x", full_name="Ravi Recruiter", role=UserRole.RECRUITER)
    db_session.add(user)
    db_session.commit()
    return user


def _make_job(db_session, user):
    job = Job(
        title="Backend Engineer",
        description="Build APIs.",
        skills=["python", "fastapi"],
        status=JobStatus.OPEN,
        created_by_id=user.id,
    )
    db_session.add(job)
    db_session.commit()
    return job


def _make_candidate(db_session):
    candidate = Candidate(full_name="Asha Kumar", email="asha@example.com")
    db_session.add(candidate)
    db_session.commit()
    return candidate


def test_create_user_and_job_relationship(db_session):
    user = _make_user(db_session)
    job = _make_job(db_session, user)

    assert job.created_by_id == user.id
    assert job.created_by.email == "recruiter@talentflow.ai"
    assert job in user.jobs


def test_job_defaults_to_draft_status(db_session):
    user = _make_user(db_session)
    job = Job(title="QA Engineer", description="Test things.", created_by_id=user.id)
    db_session.add(job)
    db_session.commit()
    assert job.status == JobStatus.DRAFT
    assert job.skills == []


def test_candidate_resume_relationship(db_session):
    candidate = _make_candidate(db_session)
    resume = Resume(candidate_id=candidate.id, file_url="s3://bucket/resume.pdf", parsed_skills=["python"])
    db_session.add(resume)
    db_session.commit()

    assert resume.parse_status == "pending"
    assert resume in candidate.resumes
    assert resume.candidate.full_name == "Asha Kumar"


def test_application_full_pipeline_chain(db_session):
    """An application should chain job -> candidate -> interview -> responses -> evaluation."""
    user = _make_user(db_session)
    job = _make_job(db_session, user)
    candidate = _make_candidate(db_session)

    application = Application(job_id=job.id, candidate_id=candidate.id, status=ApplicationStatus.SHORTLISTED, match_score=87.5)
    db_session.add(application)
    db_session.commit()

    interview = Interview(application_id=application.id, questions=[{"id": "q1", "question": "Explain REST"}])
    db_session.add(interview)
    db_session.commit()

    response = InterviewResponse(interview_id=interview.id, question="Explain REST", answer="...", score=8.0)
    db_session.add(response)

    evaluation = Evaluation(application_id=application.id, fairness_score=0.95, passed_guardrails=True)
    db_session.add(evaluation)
    db_session.commit()

    assert application.match_score == 87.5
    assert application.interviews[0].responses[0].score == 8.0
    assert application.evaluation.passed_guardrails is True
    assert application.job.title == "Backend Engineer"
    assert application.candidate.email == "asha@example.com"


def test_application_cascade_delete_removes_interviews(db_session):
    user = _make_user(db_session)
    job = _make_job(db_session, user)
    candidate = _make_candidate(db_session)
    application = Application(job_id=job.id, candidate_id=candidate.id)
    db_session.add(application)
    db_session.commit()

    interview = Interview(application_id=application.id)
    db_session.add(interview)
    db_session.commit()
    interview_id = interview.id

    db_session.delete(application)
    db_session.commit()

    assert db_session.get(Interview, interview_id) is None


def test_evaluation_is_unique_per_application(db_session):
    """Each application should have at most one Evaluation (one-to-one)."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    user = _make_user(db_session)
    job = _make_job(db_session, user)
    candidate = _make_candidate(db_session)
    application = Application(job_id=job.id, candidate_id=candidate.id)
    db_session.add(application)
    db_session.commit()

    db_session.add(Evaluation(application_id=application.id, passed_guardrails=True))
    db_session.commit()

    db_session.add(Evaluation(application_id=application.id, passed_guardrails=False))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
