import pytest

from app.agents.base import AgentError
from app.agents.evaluation_agent import EvaluationAgent
from app.schemas.agents import ResumeAnalysisResult
from app.schemas.evaluation import FairnessCheckResult, GroundingCheckResult
from app.services.enkrypt_client import EnkryptError, FakeEnkryptClient

ANALYSIS = ResumeAnalysisResult(
    summary="Solid backend engineer.",
    seniority_level="mid",
    strengths=["Strong Python skills"],
    weaknesses=["Limited leadership experience"],
    red_flags=[],
)


def test_evaluate_resume_analysis_passes_by_default(enkrypt_client):
    agent = EvaluationAgent(enkrypt_client)
    report = agent.evaluate_resume_analysis(ANALYSIS)
    assert report.passed_guardrails is True
    assert report.bias_flags == []


def test_evaluate_resume_analysis_surfaces_bias_flags():
    def fairness_responder(text, context):
        return FairnessCheckResult(fairness_score=0.3, bias_flags=["gendered_language"], passed=False)

    client = FakeEnkryptClient(fairness_responder=fairness_responder)
    agent = EvaluationAgent(client)
    report = agent.evaluate_resume_analysis(ANALYSIS)
    assert report.passed_guardrails is False
    assert "gendered_language" in report.bias_flags


def test_evaluate_resume_analysis_passes_readable_text_to_fairness_check():
    captured = {}

    def fairness_responder(text, context):
        captured["text"] = text
        return FairnessCheckResult(fairness_score=1.0, bias_flags=[], passed=True)

    client = FakeEnkryptClient(fairness_responder=fairness_responder)
    EvaluationAgent(client).evaluate_resume_analysis(ANALYSIS)
    assert "Strong Python skills" in captured["text"]
    assert "mid" in captured["text"]


def test_evaluate_recommendation_requires_both_checks_to_pass(enkrypt_client):
    agent = EvaluationAgent(enkrypt_client)
    report = agent.evaluate_recommendation(
        recommendation_rationale="Strong match based on 90% skill overlap and excellent interview scores.",
        evidence_text="Match score: 90. Interview overall score: 88.",
    )
    assert report.passed_guardrails is True
    assert report.grounding_score == 1.0


def test_evaluate_recommendation_fails_if_grounding_fails_even_when_fairness_passes():
    def grounding_responder(claim, source):
        return GroundingCheckResult(grounding_score=0.2, ungrounded_claims=["claims 10 years experience"], passed=False)

    client = FakeEnkryptClient(grounding_responder=grounding_responder)
    agent = EvaluationAgent(client)
    report = agent.evaluate_recommendation(
        recommendation_rationale="Candidate has 10 years of experience.",
        evidence_text="Match score: 90. No experience data available.",
    )
    assert report.passed_guardrails is False
    assert "claims 10 years experience" in report.raw_report["grounding"]["ungrounded_claims"]


def test_evaluate_resume_analysis_wraps_enkrypt_errors():
    def failing_responder(text, context):
        raise EnkryptError("service unavailable")

    client = FakeEnkryptClient(fairness_responder=failing_responder)
    agent = EvaluationAgent(client)
    with pytest.raises(AgentError):
        agent.evaluate_resume_analysis(ANALYSIS)
