from pydantic import BaseModel, Field


class FairnessCheckResult(BaseModel):
    """Bias/fairness evaluation of a piece of AI-generated text (e.g. a resume analysis)."""
    fairness_score: float = Field(..., ge=0, le=1)
    bias_flags: list[str] = Field(default_factory=list)
    passed: bool


class GroundingCheckResult(BaseModel):
    """Hallucination check: does a claim actually follow from its cited source text?"""
    grounding_score: float = Field(..., ge=0, le=1)
    ungrounded_claims: list[str] = Field(default_factory=list)
    passed: bool


class EvaluationReport(BaseModel):
    """Combined guardrail verdict, persisted as the `Evaluation` row for an application."""
    fairness_score: float = Field(..., ge=0, le=1)
    bias_flags: list[str] = Field(default_factory=list)
    grounding_score: float = Field(..., ge=0, le=1)
    passed_guardrails: bool
    raw_report: dict = Field(default_factory=dict)
