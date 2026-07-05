"""
Request schemas for the Mastra bridge endpoints (app/api/v1/mastra_bridge.py).

These expose the individual AI agents as granular, independently-callable
REST endpoints — the shape Mastra's tool-calling agent needs (one tool per
capability), as opposed to the existing `/jobs/{id}/shortlist` endpoint
which runs the entire orchestrated pipeline server-side in one call.

Response shapes reuse the existing agent schemas (`app.schemas.agents`,
`app.schemas.evaluation`) directly — no new response contracts invented,
so there is exactly one definition of what a "candidate match" or
"recommendation" looks like anywhere in this codebase.
"""
from pydantic import BaseModel, Field

from app.schemas.agents import ScoreBreakdown


class CandidateSearchRequest(BaseModel):
    job_title: str
    job_description: str = ""
    job_skills: list[str] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=100)


class CandidateSearchMatch(BaseModel):
    resume_id: str
    candidate_id: str
    score: float
    skills: list[str] = Field(default_factory=list)


class CandidateSearchResponse(BaseModel):
    matches: list[CandidateSearchMatch]


class CandidateRankRequest(BaseModel):
    job_title: str
    job_description: str = ""
    job_skills: list[str] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=100)


class InterviewGenerateRequest(BaseModel):
    job_title: str
    job_skills: list[str] = Field(default_factory=list)
    candidate_skills: list[str] | None = None
    num_questions: int = Field(default=5, ge=1, le=15)


class InterviewEvaluateRequest(BaseModel):
    job_title: str
    qa_pairs: list[dict] = Field(
        ..., min_length=1, description='Each item: {"question_id", "question", "answer"}'
    )


class RecommendationRequest(BaseModel):
    candidate_name: str
    match_score: float = Field(..., ge=0, le=100)
    match_rationale: str = ""
    interview_overall_score: float | None = None
    interview_score_breakdown: ScoreBreakdown | None = None
    guardrails_passed: bool
    bias_flags: list[str] = Field(default_factory=list)


class EnkryptCheckRequest(BaseModel):
    text: str = Field(..., min_length=1, description="AI-generated text to fairness-check")
    source_text: str | None = Field(
        default=None, description="If provided, also runs a grounding/hallucination check of `text` against this evidence"
    )
    context: dict | None = None
