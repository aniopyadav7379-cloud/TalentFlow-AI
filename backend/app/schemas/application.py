from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.postgres.models import ApplicationStatus, InterviewStatus


class ApplicationCreate(BaseModel):
    job_id: str
    candidate_id: str
    resume_id: str | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    candidate_id: str
    resume_id: str | None
    status: ApplicationStatus
    match_score: float | None
    match_rationale: str | None
    ai_summary: str | None
    created_at: datetime
    updated_at: datetime


class ShortlistEntry(BaseModel):
    """One row of the recruiter-ready ranked shortlist."""
    application_id: str
    candidate_id: str
    candidate_name: str
    match_score: float = Field(..., ge=0, le=100)
    match_rationale: str
    top_skills: list[str] = Field(default_factory=list)
    passed_guardrails: bool
    bias_flags: list[str] = Field(default_factory=list)
    recommendation: str


class InterviewQuestion(BaseModel):
    id: str
    question: str
    category: str  # e.g. "technical", "behavioral", "system_design"


class InterviewCreate(BaseModel):
    application_id: str
    interviewer_name: str | None = None
    scheduled_at: datetime | None = None


class InterviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    status: InterviewStatus
    questions: list[dict]
    overall_score: float | None
    score_breakdown: dict
    ai_recommendation: str | None
    created_at: datetime


class InterviewResponseIn(BaseModel):
    question_id: str
    question: str
    answer: str


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    fairness_score: float | None
    bias_flags: list[str]
    grounding_score: float | None
    passed_guardrails: bool
    final_recommendation: str | None
    created_at: datetime
