"""
Output contracts for every agent.

LLMs return JSON; these Pydantic models are the validation gate between "the
model said something" and "the pipeline trusts it." A malformed or
out-of-range LLM response raises `ValidationError` here, not three steps
later as a confusing bug in the orchestrator.
"""
from typing import Literal

from pydantic import BaseModel, Field


class ResumeAnalysisResult(BaseModel):
    summary: str = Field(..., min_length=10)
    seniority_level: Literal["junior", "mid", "senior", "lead", "principal"]
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


class CandidateMatch(BaseModel):
    resume_id: str
    candidate_id: str
    semantic_score: float = Field(..., ge=0, le=1)  # raw cosine similarity from Qdrant
    skill_overlap_score: float = Field(..., ge=0, le=1)  # fraction of job skills the resume has
    match_score: float = Field(..., ge=0, le=100)  # blended, recruiter-facing
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    rationale: str = ""


class InterviewQuestionOut(BaseModel):
    id: str
    question: str = Field(..., min_length=5)
    category: Literal["technical", "behavioral", "system_design", "problem_solving", "culture_fit"]


class QuestionGenerationResult(BaseModel):
    questions: list[InterviewQuestionOut]


class QuestionScore(BaseModel):
    question_id: str
    score: float = Field(..., ge=0, le=10)
    feedback: str


class ScoreBreakdown(BaseModel):
    technical: float = Field(..., ge=0, le=100)
    communication: float = Field(..., ge=0, le=100)
    problem_solving: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=100)
    leadership: float = Field(..., ge=0, le=100)


class InterviewScoreResult(BaseModel):
    per_question: list[QuestionScore]
    score_breakdown: ScoreBreakdown
    overall_score: float = Field(..., ge=0, le=100)
    summary: str


class HRRecommendationResult(BaseModel):
    decision: Literal["strong_hire", "hire", "hold", "no_hire"]
    summary: str = Field(..., min_length=10)
    rationale: str = Field(..., min_length=10)
