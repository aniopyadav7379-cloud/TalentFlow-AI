import pytest

from app.agents.base import AgentError
from app.agents.hr_recommendation_agent import HRRecommendationAgent
from app.schemas.agents import ScoreBreakdown
from app.services.llm_client import FakeLLMClient

STRONG_HIRE = {
    "decision": "strong_hire",
    "summary": "Excellent candidate, strongly recommend moving forward.",
    "rationale": "High match score and excellent interview performance across all dimensions.",
}

BREAKDOWN = ScoreBreakdown(technical=85, communication=80, problem_solving=88, confidence=75, leadership=70)


def test_synthesize_returns_validated_result_when_guardrails_pass():
    agent = HRRecommendationAgent(FakeLLMClient.constant(STRONG_HIRE))
    result = agent.synthesize(
        candidate_name="Asha Kumar",
        match_score=92.0,
        match_rationale="Strong skill overlap",
        interview_overall_score=85.0,
        interview_score_breakdown=BREAKDOWN,
        guardrails_passed=True,
        bias_flags=[],
    )
    assert result.decision == "strong_hire"


def test_synthesize_forces_hold_when_guardrails_fail_even_if_llm_says_hire():
    """
    Critical safety behavior: even if the LLM ignores the prompt instruction
    and recommends hire/strong_hire, the agent must override it to "hold"
    when guardrails_passed=False. This must not depend on prompt compliance.
    """
    llm_that_ignores_instructions = FakeLLMClient.constant(STRONG_HIRE)  # says strong_hire regardless
    agent = HRRecommendationAgent(llm_that_ignores_instructions)

    result = agent.synthesize(
        candidate_name="Asha Kumar",
        match_score=92.0,
        match_rationale="Strong skill overlap",
        interview_overall_score=85.0,
        interview_score_breakdown=BREAKDOWN,
        guardrails_passed=False,
        bias_flags=["potential_age_bias_in_language"],
    )

    assert result.decision == "hold"
    assert "potential_age_bias_in_language" in result.rationale


def test_synthesize_allows_no_hire_even_when_guardrails_fail():
    """A guardrail failure should force 'hold', but must not block a legitimate 'no_hire' decision."""
    no_hire = dict(STRONG_HIRE, decision="no_hire")
    agent = HRRecommendationAgent(FakeLLMClient.constant(no_hire))
    result = agent.synthesize(
        candidate_name="Asha Kumar",
        match_score=20.0,
        match_rationale="Low skill overlap",
        interview_overall_score=None,
        interview_score_breakdown=None,
        guardrails_passed=False,
        bias_flags=["some_flag"],
    )
    assert result.decision == "no_hire"


def test_synthesize_handles_no_interview_yet():
    agent = HRRecommendationAgent(FakeLLMClient.constant(STRONG_HIRE))
    result = agent.synthesize(
        candidate_name="Asha Kumar",
        match_score=88.0,
        match_rationale="Good fit",
        interview_overall_score=None,
        interview_score_breakdown=None,
        guardrails_passed=True,
        bias_flags=[],
    )
    assert result.decision == "strong_hire"


def test_synthesize_raises_on_malformed_llm_output():
    agent = HRRecommendationAgent(FakeLLMClient.constant({"decision": "not_a_real_decision"}))
    with pytest.raises(AgentError):
        agent.synthesize(
            candidate_name="Asha",
            match_score=50.0,
            match_rationale="ok",
            interview_overall_score=None,
            interview_score_breakdown=None,
            guardrails_passed=True,
            bias_flags=[],
        )
