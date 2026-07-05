"""
Evaluation Agent — the "Enkrypt AI Layer" from the architecture handoff.

Runs two independent checks on the AI-generated content that will influence
a hiring decision:

1. Fairness/bias check on the Resume Analysis Agent's output (strengths,
   weaknesses, red flags) — this is exactly the kind of free-text judgment
   an LLM can subtly bias on.
2. Grounding check: does the HR recommendation's rationale actually follow
   from the evidence (match score, interview scores) it cites, or is the
   LLM asserting things the evidence doesn't support?

`passed_guardrails` is the single boolean the HR Recommendation Agent's
override logic depends on — see `hr_recommendation_agent.py`.
"""
from __future__ import annotations

from app.agents.base import AgentError, BaseAgent
from app.schemas.agents import ResumeAnalysisResult
from app.schemas.evaluation import EvaluationReport
from app.services.enkrypt_client import EnkryptClient, EnkryptError


class EvaluationAgent(BaseAgent):
    name = "evaluation_agent"

    def __init__(self, enkrypt_client: EnkryptClient):
        self.enkrypt_client = enkrypt_client

    def evaluate_resume_analysis(
        self,
        resume_analysis: ResumeAnalysisResult,
        candidate_context: dict | None = None,
    ) -> EvaluationReport:
        """Fairness-check a resume analysis. No grounding check here — there's no separate rationale to verify yet."""
        analysis_text = self._analysis_to_text(resume_analysis)
        try:
            fairness = self.enkrypt_client.check_fairness(analysis_text, context=candidate_context)
        except EnkryptError as exc:
            raise AgentError(self.name, f"Fairness check failed: {exc}") from exc

        return EvaluationReport(
            fairness_score=fairness.fairness_score,
            bias_flags=fairness.bias_flags,
            grounding_score=1.0,  # not evaluated in this call
            passed_guardrails=fairness.passed,
            raw_report={"fairness": fairness.model_dump()},
        )

    def evaluate_recommendation(
        self,
        recommendation_rationale: str,
        evidence_text: str,
        candidate_context: dict | None = None,
    ) -> EvaluationReport:
        """
        Full check on the HR recommendation: fairness of the rationale text,
        AND whether the rationale is actually grounded in the evidence
        (match score, interview scores) rather than the model inventing
        justification.
        """
        try:
            fairness = self.enkrypt_client.check_fairness(recommendation_rationale, context=candidate_context)
            grounding = self.enkrypt_client.check_grounding(recommendation_rationale, evidence_text)
        except EnkryptError as exc:
            raise AgentError(self.name, f"Guardrail check failed: {exc}") from exc

        passed = fairness.passed and grounding.passed
        return EvaluationReport(
            fairness_score=fairness.fairness_score,
            bias_flags=fairness.bias_flags,
            grounding_score=grounding.grounding_score,
            passed_guardrails=passed,
            raw_report={
                "fairness": fairness.model_dump(),
                "grounding": grounding.model_dump(),
            },
        )

    @staticmethod
    def _analysis_to_text(analysis: ResumeAnalysisResult) -> str:
        return (
            f"Summary: {analysis.summary}\n"
            f"Seniority: {analysis.seniority_level}\n"
            f"Strengths: {', '.join(analysis.strengths)}\n"
            f"Weaknesses: {', '.join(analysis.weaknesses)}\n"
            f"Red flags: {', '.join(analysis.red_flags)}"
        )
