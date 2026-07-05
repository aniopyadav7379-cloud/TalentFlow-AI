"""
Resume Analysis Agent.

The rule-based parser (`resume_parser.py`) already extracts skills,
experience years, and education deterministically. This agent adds the
judgment a rule-based system can't: seniority inference, strengths,
weaknesses, and red flags — the qualitative read a recruiter would give it.

This is the one place in the pipeline where "the LLM might be wrong" matters
most for fairness, since strengths/weaknesses/red_flags directly shape a
shortlist — that's exactly why its output goes through Enkrypt AI's bias
check (step 4) before ever reaching a recruiter.
"""
from __future__ import annotations

from pydantic import ValidationError

from app.agents.base import AgentError, BaseAgent
from app.schemas.agents import ResumeAnalysisResult
from app.services.llm_client import LLMClient, LLMError

_SYSTEM_PROMPT = """You are an expert technical recruiter analyzing a resume.
Base your analysis STRICTLY on the resume text provided — never assume facts
not present in it, and never factor in the candidate's name, gender, age, or
any other attribute unrelated to their qualifications.

Respond with ONLY a JSON object matching this exact shape:
{
  "summary": "<2-3 sentence neutral summary of the candidate's background>",
  "seniority_level": "<one of: junior, mid, senior, lead, principal>",
  "strengths": ["<specific, evidence-based strength>", ...],
  "weaknesses": ["<specific, evidence-based gap>", ...],
  "red_flags": ["<only genuine concerns like unexplained gaps, not minor nitpicks>"]
}"""


class ResumeAnalysisAgent(BaseAgent):
    name = "resume_analysis_agent"

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def analyze(
        self,
        resume_text: str,
        parsed_skills: list[str],
        experience_years: float | None,
        job_context: str | None = None,
    ) -> ResumeAnalysisResult:
        if not resume_text or not resume_text.strip():
            raise AgentError(self.name, "Cannot analyze an empty resume")

        user_prompt = self._build_user_prompt(resume_text, parsed_skills, experience_years, job_context)

        try:
            raw = self.llm_client.complete_json(_SYSTEM_PROMPT, user_prompt)
        except LLMError as exc:
            raise AgentError(self.name, f"LLM call failed: {exc}") from exc

        try:
            return ResumeAnalysisResult.model_validate(raw)
        except ValidationError as exc:
            raise AgentError(self.name, f"LLM returned output that failed schema validation: {exc}") from exc

    @staticmethod
    def _build_user_prompt(
        resume_text: str, parsed_skills: list[str], experience_years: float | None, job_context: str | None
    ) -> str:
        parts = [
            f"Extracted skills (rule-based, may be incomplete): {', '.join(parsed_skills) or 'none detected'}",
            f"Extracted experience: {experience_years} years" if experience_years else "Experience: not detected",
        ]
        if job_context:
            parts.append(f"Evaluate relevance to this role context: {job_context}")
        parts.append(f"\nResume text:\n{resume_text}")
        return "\n".join(parts)
