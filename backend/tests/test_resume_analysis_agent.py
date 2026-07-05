import pytest

from app.agents.base import AgentError
from app.agents.resume_analysis_agent import ResumeAnalysisAgent
from app.services.llm_client import FakeLLMClient

VALID_ANALYSIS = {
    "summary": "Backend engineer with strong Python and distributed systems experience.",
    "seniority_level": "mid",
    "strengths": ["Deep FastAPI experience", "Solid distributed systems background"],
    "weaknesses": ["No leadership experience mentioned"],
    "red_flags": [],
}


def test_analyze_returns_validated_result():
    llm = FakeLLMClient.constant(VALID_ANALYSIS)
    agent = ResumeAnalysisAgent(llm)

    result = agent.analyze(
        resume_text="Experienced backend engineer skilled in Python and FastAPI.",
        parsed_skills=["python", "fastapi"],
        experience_years=4.0,
    )

    assert result.seniority_level == "mid"
    assert "Deep FastAPI experience" in result.strengths
    assert result.red_flags == []


def test_analyze_rejects_empty_resume_text():
    agent = ResumeAnalysisAgent(FakeLLMClient.constant(VALID_ANALYSIS))
    with pytest.raises(AgentError):
        agent.analyze(resume_text="   ", parsed_skills=[], experience_years=None)


def test_analyze_raises_on_malformed_llm_output():
    llm = FakeLLMClient.constant({"summary": "too short"})  # missing required fields
    agent = ResumeAnalysisAgent(llm)
    with pytest.raises(AgentError):
        agent.analyze(resume_text="Some resume text here.", parsed_skills=[], experience_years=None)


def test_analyze_raises_on_invalid_seniority_enum():
    bad = dict(VALID_ANALYSIS, seniority_level="超すごい")  # not one of the allowed literals
    agent = ResumeAnalysisAgent(FakeLLMClient.constant(bad))
    with pytest.raises(AgentError):
        agent.analyze(resume_text="Some resume text.", parsed_skills=[], experience_years=None)


def test_analyze_prompt_includes_job_context_when_given():
    captured = {}

    def responder(system, user):
        captured["user"] = user
        return VALID_ANALYSIS

    agent = ResumeAnalysisAgent(FakeLLMClient(responder=responder))
    agent.analyze(
        resume_text="Resume text.",
        parsed_skills=["python"],
        experience_years=3.0,
        job_context="Senior Backend Engineer role requiring distributed systems expertise",
    )
    assert "Senior Backend Engineer" in captured["user"]
