import pytest

from app.agents.base import AgentError
from app.agents.interview_agent import InterviewAgent
from app.services.llm_client import FakeLLMClient

VALID_QUESTIONS = {
    "questions": [
        {"id": "q1", "question": "Explain how you would design a rate limiter.", "category": "system_design"},
        {"id": "q2", "question": "Tell me about a time you disagreed with a teammate.", "category": "behavioral"},
    ]
}

VALID_SCORES = {
    "per_question": [
        {"question_id": "q1", "score": 8.0, "feedback": "Strong understanding of token bucket algorithm."},
        {"question_id": "q2", "score": 7.0, "feedback": "Good conflict resolution example."},
    ],
    "score_breakdown": {
        "technical": 80,
        "communication": 75,
        "problem_solving": 82,
        "confidence": 70,
        "leadership": 60,
    },
    "overall_score": 78,
    "summary": "Strong technical candidate with solid communication skills.",
}


def test_generate_questions_returns_validated_result():
    agent = InterviewAgent(FakeLLMClient.constant(VALID_QUESTIONS))
    result = agent.generate_questions(job_title="Backend Engineer", job_skills=["python", "system design"])
    assert len(result.questions) == 2
    assert result.questions[0].category == "system_design"


def test_generate_questions_rejects_empty_job_title():
    agent = InterviewAgent(FakeLLMClient.constant(VALID_QUESTIONS))
    with pytest.raises(AgentError):
        agent.generate_questions(job_title="   ", job_skills=[])


def test_generate_questions_raises_on_zero_questions():
    agent = InterviewAgent(FakeLLMClient.constant({"questions": []}))
    with pytest.raises(AgentError):
        agent.generate_questions(job_title="Backend Engineer", job_skills=["python"])


def test_generate_questions_raises_on_invalid_category():
    bad = {"questions": [{"id": "q1", "question": "A question here", "category": "not_a_real_category"}]}
    agent = InterviewAgent(FakeLLMClient.constant(bad))
    with pytest.raises(AgentError):
        agent.generate_questions(job_title="Backend Engineer", job_skills=[])


def test_score_responses_returns_validated_result():
    agent = InterviewAgent(FakeLLMClient.constant(VALID_SCORES))
    result = agent.score_responses(
        job_title="Backend Engineer",
        qa_pairs=[
            {"question_id": "q1", "question": "Design a rate limiter.", "answer": "I'd use a token bucket..."},
            {"question_id": "q2", "question": "Tell me about conflict.", "answer": "Once I disagreed with..."},
        ],
    )
    assert result.overall_score == 78
    assert result.score_breakdown.technical == 80
    assert len(result.per_question) == 2


def test_score_responses_rejects_empty_qa_pairs():
    agent = InterviewAgent(FakeLLMClient.constant(VALID_SCORES))
    with pytest.raises(AgentError):
        agent.score_responses(job_title="Backend Engineer", qa_pairs=[])


def test_score_responses_raises_on_out_of_range_score():
    bad = dict(VALID_SCORES, overall_score=150)  # exceeds 0-100 bound
    agent = InterviewAgent(FakeLLMClient.constant(bad))
    with pytest.raises(AgentError):
        agent.score_responses(job_title="Backend Engineer", qa_pairs=[{"question_id": "q1", "question": "q", "answer": "a"}])


def test_score_responses_prompt_includes_all_qa_pairs():
    captured = {}

    def responder(system, user):
        captured["user"] = user
        return VALID_SCORES

    agent = InterviewAgent(FakeLLMClient(responder=responder))
    agent.score_responses(
        job_title="Backend Engineer",
        qa_pairs=[
            {"question_id": "q1", "question": "Question one text", "answer": "Answer one text"},
            {"question_id": "q2", "question": "Question two text", "answer": "Answer two text"},
        ],
    )
    assert "Question one text" in captured["user"]
    assert "Answer two text" in captured["user"]
