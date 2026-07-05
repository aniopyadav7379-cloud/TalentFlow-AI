"""
HR Recommendation Agent.

Synthesizes everything upstream (resume match score, interview scores, and
— critically — guardrail status) into one final recommendation. This is
deliberately the LAST agent in the pipeline, after Enkrypt's evaluation
layer has already run: `guardrails_passed=False` forces the decision toward
"hold" regardless of how strong the scores look, because a fairness/bias
flag means the upstream signal itself may not be trustworthy.
"""
from __future__ import annotations

from pydantic import ValidationError

from app.agents.base import AgentError, BaseAgent
from app.schemas.agents import HRRecommendationResult, ScoreBreakdown
from app.services.llm_client import LLMClient, LLMError

_SYSTEM_PROMPT = """You are a senior HR partner making a final hiring recommendation by
synthesizing a candidate's resume match score and interview performance.

Base your decision only on the evidence given. If guardrails_passed is
false, you MUST recommend "hold" regardless of how strong the scores look —
explain in your rationale that a fairness/bias check flagged a concern that
needs human review before proceeding.

Respond with ONLY a JSON object matching this exact shape:
{
  "decision": "<one of: strong_hire, hire, hold, no_hire>",
  "summary": "<1-2 sentence recommendation for the recruiter>",
  "rationale": "<specific reasoning citing the match score and interview evidence>"
}"""


class HRRecommendationAgent(BaseAgent):
    name = "hr_recommendation_agent"

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def synthesize(
        self,
        candidate_name: str,
        match_score: float,
        match_rationale: str,
        interview_overall_score: float | None,
        interview_score_breakdown: ScoreBreakdown | None,
        guardrails_passed: bool,
        bias_flags: list[str],
    ) -> HRRecommendationResult:
        user_prompt = self._build_prompt(
            candidate_name,
            match_score,
            match_rationale,
            interview_overall_score,
            interview_score_breakdown,
            guardrails_passed,
            bias_flags,
        )
        try:
            raw = self.llm_client.complete_json(_SYSTEM_PROMPT, user_prompt)
        except LLMError as exc:
            raise AgentError(self.name, f"LLM call failed: {exc}") from exc

        try:
            result = HRRecommendationResult.model_validate(raw)
        except ValidationError as exc:
            raise AgentError(self.name, f"LLM returned malformed recommendation: {exc}") from exc

        # Defense in depth: never trust the LLM alone to honor the guardrail
        # instruction. If guardrails failed, the decision is forced to "hold"
        # here even if the model didn't comply with the prompt.
        if not guardrails_passed and result.decision in ("strong_hire", "hire"):
            result = HRRecommendationResult(
                decision="hold",
                summary="Held for human review — a fairness/bias guardrail flagged this application.",
                rationale=(
                    f"Guardrail check failed (flags: {', '.join(bias_flags) or 'unspecified'}). "
                    f"Original model rationale: {result.rationale}"
                ),
            )
        return result

    @staticmethod
    def _build_prompt(
        candidate_name: str,
        match_score: float,
        match_rationale: str,
        interview_overall_score: float | None,
        interview_score_breakdown: ScoreBreakdown | None,
        guardrails_passed: bool,
        bias_flags: list[str],
    ) -> str:
        parts = [
            f"Candidate: {candidate_name}",
            f"Resume match score: {match_score}/100 — {match_rationale}",
        ]
        if interview_overall_score is not None:
            parts.append(f"Interview overall score: {interview_overall_score}/100")
        if interview_score_breakdown is not None:
            parts.append(f"Interview breakdown: {interview_score_breakdown.model_dump()}")
        else:
            parts.append("Interview: not yet conducted")
        parts.append(f"guardrails_passed: {guardrails_passed}")
        if bias_flags:
            parts.append(f"Bias/fairness flags raised: {', '.join(bias_flags)}")
        return "\n".join(parts)
