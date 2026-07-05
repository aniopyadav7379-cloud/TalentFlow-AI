"""
Interview Evaluation Pipeline — the second orchestrator.

`ShortlistPipeline` (step 4) generates interview questions but obviously
can't score responses that don't exist yet — a human has to actually
conduct the interview first. This pipeline picks up from there: given
recorded question/answer pairs, it scores them, re-evaluates guardrails on
the updated recommendation, and re-synthesizes the HR recommendation with
real interview data instead of `None`.

Deliberately does NOT auto-advance `Application.status` to offered/rejected
— that's a consequential HR decision a human should make. It does set the
status to `INTERVIEWING` (a factual statement: the interview happened),
leaving the hire/reject call to a recruiter via a separate action.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.base import AgentError
from app.agents.evaluation_agent import EvaluationAgent
from app.agents.hr_recommendation_agent import HRRecommendationAgent
from app.agents.interview_agent import InterviewAgent
from app.db.postgres.models import (
    Application,
    ApplicationStatus,
    Candidate,
    Evaluation,
    Interview,
    InterviewResponse,
    InterviewStatus,
)
from app.schemas.agents import HRRecommendationResult, InterviewScoreResult
from app.services.enkrypt_client import EnkryptClient
from app.services.llm_client import LLMClient


class InterviewPipelineFatalError(Exception):
    """Raised when the pipeline can't proceed at all — unknown application, no interview record, etc."""


class InterviewEvaluationPipeline:
    def __init__(self, db: Session, llm_client: LLMClient, enkrypt_client: EnkryptClient):
        self.db = db
        self.interview_agent = InterviewAgent(llm_client)
        self.evaluation_agent = EvaluationAgent(enkrypt_client)
        self.hr_agent = HRRecommendationAgent(llm_client)

    def run(self, application_id: str, qa_pairs: list[dict]) -> dict:
        """
        `qa_pairs`: list of {"question_id": str, "question": str, "answer": str}.
        Returns {"application": Application, "interview": Interview, "recommendation": HRRecommendationResult}.
        """
        application = self.db.get(Application, application_id)
        if application is None:
            raise InterviewPipelineFatalError(f"Application {application_id} not found")

        interview = (
            self.db.query(Interview)
            .filter_by(application_id=application_id)
            .order_by(Interview.created_at.desc())
            .first()
        )
        if interview is None:
            raise InterviewPipelineFatalError(f"No interview record exists for application {application_id}")

        job_title = application.job.title
        try:
            score_result = self.interview_agent.score_responses(job_title=job_title, qa_pairs=qa_pairs)
        except AgentError as exc:
            raise InterviewPipelineFatalError(f"Interview scoring failed: {exc}") from exc

        self._persist_responses(interview, qa_pairs, score_result)
        recommendation = self._synthesize_and_evaluate(application, score_result)

        application.status = ApplicationStatus.INTERVIEWING
        application.ai_summary = recommendation.summary
        self.db.commit()

        return {"application": application, "interview": interview, "recommendation": recommendation}

    def _persist_responses(self, interview: Interview, qa_pairs: list[dict], score_result: InterviewScoreResult) -> None:
        scores_by_question_id = {s.question_id: s for s in score_result.per_question}
        for qa in qa_pairs:
            score_entry = scores_by_question_id.get(qa["question_id"])
            self.db.add(
                InterviewResponse(
                    interview_id=interview.id,
                    question=qa["question"],
                    answer=qa["answer"],
                    score=score_entry.score if score_entry else None,
                    feedback=score_entry.feedback if score_entry else None,
                )
            )
        interview.overall_score = score_result.overall_score
        interview.score_breakdown = score_result.score_breakdown.model_dump()
        interview.ai_recommendation = score_result.summary
        interview.status = InterviewStatus.COMPLETED
        self.db.flush()

    def _synthesize_and_evaluate(self, application: Application, score_result: InterviewScoreResult) -> HRRecommendationResult:
        existing_evaluation = self.db.query(Evaluation).filter_by(application_id=application.id).one_or_none()
        guardrails_passed_so_far = existing_evaluation.passed_guardrails if existing_evaluation else False
        bias_flags_so_far = existing_evaluation.bias_flags if existing_evaluation else ["no_prior_evaluation"]

        candidate = self.db.get(Candidate, application.candidate_id)
        candidate_name = candidate.full_name if candidate else "Unknown Candidate"

        try:
            recommendation = self.hr_agent.synthesize(
                candidate_name=candidate_name,
                match_score=application.match_score or 0.0,
                match_rationale=application.match_rationale or "",
                interview_overall_score=score_result.overall_score,
                interview_score_breakdown=score_result.score_breakdown,
                guardrails_passed=guardrails_passed_so_far,
                bias_flags=bias_flags_so_far,
            )
        except AgentError as exc:
            raise InterviewPipelineFatalError(f"HR recommendation synthesis failed: {exc}") from exc

        evidence_text = (
            f"Resume match score: {application.match_score}/100. "
            f"Interview overall score: {score_result.overall_score}/100. "
            f"Interview breakdown: {score_result.score_breakdown.model_dump()}."
        )
        try:
            post_hoc_check = self.evaluation_agent.evaluate_recommendation(
                recommendation_rationale=recommendation.rationale,
                evidence_text=evidence_text,
                candidate_context={"application_id": application.id},
            )
        except AgentError as exc:
            raise InterviewPipelineFatalError(f"Post-hoc recommendation guardrail check failed: {exc}") from exc

        final_guardrails_passed = guardrails_passed_so_far and post_hoc_check.passed_guardrails
        combined_bias_flags = sorted(set(bias_flags_so_far) | set(post_hoc_check.bias_flags))

        # Same hard-override principle as HRRecommendationAgent itself: never
        # trust prompt compliance alone. If the post-hoc check on the
        # rationale we just generated fails, force "hold" here in code.
        if not post_hoc_check.passed_guardrails and recommendation.decision in ("strong_hire", "hire"):
            recommendation = HRRecommendationResult(
                decision="hold",
                summary="Held for human review — the interview recommendation failed a post-hoc fairness/grounding check.",
                rationale=(
                    f"Guardrail flags: {', '.join(combined_bias_flags) or 'unspecified'}. "
                    f"Original rationale: {recommendation.rationale}"
                ),
            )

        self._upsert_evaluation(application.id, existing_evaluation, post_hoc_check, final_guardrails_passed, combined_bias_flags, recommendation)
        return recommendation

    def _upsert_evaluation(self, application_id, existing_evaluation, post_hoc_check, final_guardrails_passed, combined_bias_flags, recommendation) -> None:
        if existing_evaluation is None:
            existing_evaluation = Evaluation(application_id=application_id)
            self.db.add(existing_evaluation)

        existing_evaluation.fairness_score = post_hoc_check.fairness_score
        existing_evaluation.bias_flags = combined_bias_flags
        existing_evaluation.grounding_score = post_hoc_check.grounding_score
        existing_evaluation.passed_guardrails = final_guardrails_passed
        existing_evaluation.final_recommendation = recommendation.summary
        existing_evaluation.raw_report = {
            **(existing_evaluation.raw_report or {}),
            "post_interview_recommendation_check": post_hoc_check.raw_report,
        }
        self.db.flush()
