"""
Interview Agent.

Two responsibilities, kept in one agent since they share the same job/role
context: generating role-specific questions, and scoring the answers once
the interview happens. Both go through the LLM because both require
judgment (what's worth asking, whether an answer demonstrates competence)
that a rule-based system can't provide.
"""
from __future__ import annotations

import uuid

from pydantic import ValidationError

from app.agents.base import AgentError, BaseAgent
from app.schemas.agents import InterviewScoreResult, QuestionGenerationResult
from app.services.llm_client import LLMClient, LLMError

_QUESTION_SYSTEM_PROMPT = """You are an expert technical interviewer designing role-specific interview
questions. Questions must be answerable in a spoken interview (not requiring
a live coding environment) and must probe real competence, not trivia.

Respond with ONLY a JSON object matching this exact shape:
{
  "questions": [
    {"id": "<short unique id like q1>", "question": "<the question>", "category": "<one of: technical, behavioral, system_design, problem_solving, culture_fit>"}
  ]
}"""

_SCORING_SYSTEM_PROMPT = """You are an expert technical interviewer scoring a candidate's interview
responses. Score based STRICTLY on the content and quality of each answer —
never factor in the candidate's name, writing style quirks unrelated to
competence, or anything other than what the answer demonstrates.

Respond with ONLY a JSON object matching this exact shape:
{
  "per_question": [{"question_id": "<id>", "score": <0-10>, "feedback": "<brief, specific feedback>"}],
  "score_breakdown": {"technical": <0-100>, "communication": <0-100>, "problem_solving": <0-100>, "confidence": <0-100>, "leadership": <0-100>},
  "overall_score": <0-100>,
  "summary": "<2-3 sentence overall assessment>"
}"""


class InterviewAgent(BaseAgent):
    name = "interview_agent"

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def generate_questions(
        self,
        job_title: str,
        job_skills: list[str],
        candidate_skills: list[str] | None = None,
        num_questions: int = 5,
    ) -> QuestionGenerationResult:
        if not job_title.strip():
            raise AgentError(self.name, "Cannot generate questions without a job title")

        user_prompt = self._build_question_prompt(job_title, job_skills, candidate_skills, num_questions)
        try:
            raw = self.llm_client.complete_json(_QUESTION_SYSTEM_PROMPT, user_prompt)
        except LLMError as exc:
            raise AgentError(self.name, f"Question generation LLM call failed: {exc}") from exc

        try:
            result = QuestionGenerationResult.model_validate(raw)
        except ValidationError as exc:
            raise AgentError(self.name, f"LLM returned malformed questions: {exc}") from exc

        if not result.questions:
            raise AgentError(self.name, "LLM returned zero questions")
        return result

    def score_responses(
        self,
        job_title: str,
        qa_pairs: list[dict],
    ) -> InterviewScoreResult:
        """`qa_pairs`: list of {"question_id": str, "question": str, "answer": str}."""
        if not qa_pairs:
            raise AgentError(self.name, "Cannot score an interview with zero responses")

        user_prompt = self._build_scoring_prompt(job_title, qa_pairs)
        try:
            raw = self.llm_client.complete_json(_SCORING_SYSTEM_PROMPT, user_prompt)
        except LLMError as exc:
            raise AgentError(self.name, f"Response scoring LLM call failed: {exc}") from exc

        try:
            return InterviewScoreResult.model_validate(raw)
        except ValidationError as exc:
            raise AgentError(self.name, f"LLM returned malformed scores: {exc}") from exc

    @staticmethod
    def _build_question_prompt(
        job_title: str, job_skills: list[str], candidate_skills: list[str] | None, num_questions: int
    ) -> str:
        parts = [f"Role: {job_title}", f"Generate exactly {num_questions} questions."]
        if job_skills:
            parts.append(f"Required skills to probe: {', '.join(job_skills)}")
        if candidate_skills:
            parts.append(f"Candidate's claimed skills (verify depth on these): {', '.join(candidate_skills)}")
        return "\n".join(parts)

    @staticmethod
    def _build_scoring_prompt(job_title: str, qa_pairs: list[dict]) -> str:
        lines = [f"Role being interviewed for: {job_title}", ""]
        for qa in qa_pairs:
            qid = qa.get("question_id") or str(uuid.uuid4())[:8]
            lines.append(f"Question [{qid}]: {qa['question']}")
            lines.append(f"Answer: {qa['answer']}")
            lines.append("")
        return "\n".join(lines)
