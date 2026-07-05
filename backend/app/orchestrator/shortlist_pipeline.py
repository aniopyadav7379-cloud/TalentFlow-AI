"""
Shortlist Pipeline — the orchestrator.

This is the piece the architecture handoff calls the "Mastra Orchestrator."
Mastra itself is a TypeScript-only framework, so this backend (Python/
FastAPI) uses LangGraph instead — the same state-machine approach the
handoff's own `agent_graph.py` naming already pointed at. The module
boundaries below (`_rank_candidates`, `_analyze_resumes`, etc.) map
1:1 onto the handoff's `matching_pipeline.py` / `resume_pipeline.py` /
`interview_pipeline.py` / `recommendation_pipeline.py` workflow files.

Pipeline stages, in order:
  1. rank_candidates          — CandidateMatchingAgent (Qdrant + skill overlap)
  2. analyze_resumes          — ResumeAnalysisAgent (per shortlisted candidate)
  3. evaluate_guardrails      — EvaluationAgent / Enkrypt fairness check
  4. generate_questions       — InterviewAgent (role-specific question bank)
  5. synthesize_recommendations — HRRecommendationAgent
  6. build_shortlist          — persists Application/Evaluation/Interview
                                 rows and returns the recruiter-facing list

Failure isolation: one candidate failing at any stage (bad LLM output, a
resume row that never finished parsing, etc.) is recorded in `state.errors`
and that candidate is dropped from later stages — it never halts the whole
batch. A fatal error (job not found) is the only thing allowed to raise.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.base import AgentError
from app.agents.candidate_matching_agent import CandidateMatchingAgent
from app.agents.evaluation_agent import EvaluationAgent
from app.agents.hr_recommendation_agent import HRRecommendationAgent
from app.agents.interview_agent import InterviewAgent
from app.agents.resume_analysis_agent import ResumeAnalysisAgent
from app.db.postgres.models import (
    Application,
    ApplicationStatus,
    Candidate,
    Evaluation,
    Interview,
    Job,
    Resume,
)
from app.db.qdrant.client import VectorStore
from app.schemas.agents import CandidateMatch, HRRecommendationResult, QuestionGenerationResult, ResumeAnalysisResult
from app.schemas.application import ShortlistEntry
from app.schemas.evaluation import EvaluationReport
from app.services.embeddings import EmbeddingClient
from app.services.enkrypt_client import EnkryptClient
from app.services.llm_client import LLMClient


class PipelineState(TypedDict, total=False):
    job_id: str
    top_k: int
    job: Job
    ranked_matches: list[CandidateMatch]
    resume_analyses: dict[str, ResumeAnalysisResult]
    guardrail_reports: dict[str, EvaluationReport]
    interview_questions: dict[str, QuestionGenerationResult]
    recommendations: dict[str, HRRecommendationResult]
    shortlist: list[ShortlistEntry]
    errors: list[dict]


class PipelineFatalError(Exception):
    """Raised for errors that must halt the whole pipeline (e.g. job not found) — never for a single candidate's failure."""


class ShortlistPipeline:
    def __init__(
        self,
        db: Session,
        vector_store: VectorStore,
        embedding_client: EmbeddingClient,
        llm_client: LLMClient,
        enkrypt_client: EnkryptClient,
        default_top_k: int = 10,
    ):
        self.db = db
        self.default_top_k = default_top_k
        self.matching_agent = CandidateMatchingAgent(vector_store, embedding_client)
        self.resume_agent = ResumeAnalysisAgent(llm_client)
        self.evaluation_agent = EvaluationAgent(enkrypt_client)
        self.interview_agent = InterviewAgent(llm_client)
        self.hr_agent = HRRecommendationAgent(llm_client)
        self._graph = self._build_graph()

    def run(self, job_id: str, top_k: int | None = None) -> PipelineState:
        initial_state: PipelineState = {
            "job_id": job_id,
            "top_k": top_k or self.default_top_k,
            "errors": [],
        }
        return self._graph.invoke(initial_state)

    # ------------------------------------------------------------------ #
    # Graph construction
    # ------------------------------------------------------------------ #

    def _build_graph(self):
        graph = StateGraph(PipelineState)
        graph.add_node("rank_candidates", self._rank_candidates)
        graph.add_node("analyze_resumes", self._analyze_resumes)
        graph.add_node("evaluate_guardrails", self._evaluate_guardrails)
        graph.add_node("generate_questions", self._generate_questions)
        graph.add_node("synthesize_recommendations", self._synthesize_recommendations)
        graph.add_node("build_shortlist", self._build_shortlist)

        graph.set_entry_point("rank_candidates")
        graph.add_edge("rank_candidates", "analyze_resumes")
        graph.add_edge("analyze_resumes", "evaluate_guardrails")
        graph.add_edge("evaluate_guardrails", "generate_questions")
        graph.add_edge("generate_questions", "synthesize_recommendations")
        graph.add_edge("synthesize_recommendations", "build_shortlist")
        graph.add_edge("build_shortlist", END)
        return graph.compile()

    # ------------------------------------------------------------------ #
    # Stage 1: rank_candidates  (matching_pipeline.py equivalent)
    # ------------------------------------------------------------------ #

    def _rank_candidates(self, state: PipelineState) -> dict:
        job = self.db.get(Job, state["job_id"])
        if job is None:
            raise PipelineFatalError(f"Job {state['job_id']} not found")

        matches = self.matching_agent.rank_candidates(
            job_title=job.title,
            job_description=job.description,
            job_skills=job.skills,
            top_k=state.get("top_k", self.default_top_k),
        )
        return {"job": job, "ranked_matches": matches}

    # ------------------------------------------------------------------ #
    # Stage 2: analyze_resumes  (resume_pipeline.py equivalent)
    # ------------------------------------------------------------------ #

    def _analyze_resumes(self, state: PipelineState) -> dict:
        analyses: dict[str, ResumeAnalysisResult] = {}
        errors = list(state.get("errors", []))
        job = state["job"]

        for match in state["ranked_matches"]:
            resume = self.db.get(Resume, match.resume_id)
            if resume is None or resume.parse_status != "parsed":
                errors.append(
                    {"resume_id": match.resume_id, "stage": "analyze_resumes", "error": "resume missing or not successfully parsed"}
                )
                continue
            try:
                analyses[match.resume_id] = self.resume_agent.analyze(
                    resume_text=resume.raw_text,
                    parsed_skills=resume.parsed_skills,
                    experience_years=resume.parsed_experience_years,
                    job_context=job.title,
                )
            except AgentError as exc:
                errors.append({"resume_id": match.resume_id, "stage": "analyze_resumes", "error": str(exc)})

        return {"resume_analyses": analyses, "errors": errors}

    # ------------------------------------------------------------------ #
    # Stage 3: evaluate_guardrails  (Enkrypt AI layer)
    # ------------------------------------------------------------------ #

    def _evaluate_guardrails(self, state: PipelineState) -> dict:
        reports: dict[str, EvaluationReport] = {}
        errors = list(state.get("errors", []))

        for resume_id, analysis in state["resume_analyses"].items():
            try:
                reports[resume_id] = self.evaluation_agent.evaluate_resume_analysis(
                    analysis, candidate_context={"resume_id": resume_id, "job_id": state["job_id"]}
                )
            except AgentError as exc:
                errors.append({"resume_id": resume_id, "stage": "evaluate_guardrails", "error": str(exc)})

        return {"guardrail_reports": reports, "errors": errors}

    # ------------------------------------------------------------------ #
    # Stage 4: generate_questions  (interview_pipeline.py equivalent)
    # ------------------------------------------------------------------ #

    def _generate_questions(self, state: PipelineState) -> dict:
        questions: dict[str, QuestionGenerationResult] = {}
        errors = list(state.get("errors", []))
        job = state["job"]
        matches_by_resume = {m.resume_id: m for m in state["ranked_matches"]}

        # Only generate questions for candidates who made it through analysis
        # — no point building an interview kit for a candidate we couldn't
        # even analyze.
        for resume_id in state["resume_analyses"]:
            match = matches_by_resume.get(resume_id)
            try:
                questions[resume_id] = self.interview_agent.generate_questions(
                    job_title=job.title,
                    job_skills=job.skills,
                    candidate_skills=match.matched_skills if match else None,
                )
            except AgentError as exc:
                errors.append({"resume_id": resume_id, "stage": "generate_questions", "error": str(exc)})

        return {"interview_questions": questions, "errors": errors}

    # ------------------------------------------------------------------ #
    # Stage 5: synthesize_recommendations  (recommendation_pipeline.py equivalent)
    # ------------------------------------------------------------------ #

    def _synthesize_recommendations(self, state: PipelineState) -> dict:
        recommendations: dict[str, HRRecommendationResult] = {}
        errors = list(state.get("errors", []))
        matches_by_resume = {m.resume_id: m for m in state["ranked_matches"]}

        for resume_id, analysis in state["resume_analyses"].items():
            match = matches_by_resume[resume_id]
            report = state["guardrail_reports"].get(resume_id)
            # No guardrail report at all (the check itself failed) is treated
            # as NOT passed — fail closed, never fail open on a safety check.
            guardrails_passed = report.passed_guardrails if report else False
            bias_flags = report.bias_flags if report else ["guardrail_check_unavailable"]

            candidate = self.db.get(Candidate, match.candidate_id)
            candidate_name = candidate.full_name if candidate else "Unknown Candidate"

            try:
                recommendations[resume_id] = self.hr_agent.synthesize(
                    candidate_name=candidate_name,
                    match_score=match.match_score,
                    match_rationale=match.rationale,
                    interview_overall_score=None,
                    interview_score_breakdown=None,
                    guardrails_passed=guardrails_passed,
                    bias_flags=bias_flags,
                )
            except AgentError as exc:
                errors.append({"resume_id": resume_id, "stage": "synthesize_recommendations", "error": str(exc)})

        return {"recommendations": recommendations, "errors": errors}

    # ------------------------------------------------------------------ #
    # Stage 6: build_shortlist  — persists Application/Evaluation/Interview
    # ------------------------------------------------------------------ #

    def _build_shortlist(self, state: PipelineState) -> dict:
        shortlist: list[ShortlistEntry] = []
        matches_by_resume = {m.resume_id: m for m in state["ranked_matches"]}
        job = state["job"]

        for resume_id, recommendation in state["recommendations"].items():
            match = matches_by_resume[resume_id]
            report = state["guardrail_reports"].get(resume_id)
            candidate = self.db.get(Candidate, match.candidate_id)

            application = self._get_or_create_application(job.id, match.candidate_id, resume_id, match, recommendation)
            self._upsert_evaluation(application.id, report)

            question_bank = state.get("interview_questions", {}).get(resume_id)
            if question_bank is not None:
                self._create_interview(application.id, question_bank)

            self.db.commit()

            shortlist.append(
                ShortlistEntry(
                    application_id=application.id,
                    candidate_id=match.candidate_id,
                    candidate_name=candidate.full_name if candidate else "Unknown Candidate",
                    match_score=match.match_score,
                    match_rationale=match.rationale,
                    top_skills=match.matched_skills,
                    # Same fallback as _synthesize_recommendations: no report at
                    # all (the check itself errored) must read the same way
                    # here as it did when it drove the recommendation — never
                    # silently reset to "no flags" just because this stage
                    # re-reads the dict independently.
                    passed_guardrails=report.passed_guardrails if report else False,
                    bias_flags=report.bias_flags if report else ["guardrail_check_unavailable"],
                    recommendation=recommendation.summary,
                )
            )

        shortlist.sort(key=lambda entry: entry.match_score, reverse=True)
        return {"shortlist": shortlist}

    # ------------------------------------------------------------------ #
    # Persistence helpers — idempotent so re-running the pipeline for the
    # same job doesn't create duplicate Application/Evaluation rows.
    # ------------------------------------------------------------------ #

    def _get_or_create_application(
        self,
        job_id: str,
        candidate_id: str,
        resume_id: str,
        match: CandidateMatch,
        recommendation: HRRecommendationResult,
    ) -> Application:
        application = (
            self.db.query(Application)
            .filter_by(job_id=job_id, candidate_id=candidate_id)
            .one_or_none()
        )
        if application is None:
            application = Application(job_id=job_id, candidate_id=candidate_id)
            self.db.add(application)

        application.resume_id = resume_id
        application.status = ApplicationStatus.SHORTLISTED
        application.match_score = match.match_score
        application.match_rationale = match.rationale
        application.ai_summary = recommendation.summary
        self.db.flush()
        return application

    def _upsert_evaluation(self, application_id: str, report: EvaluationReport | None) -> None:
        if report is None:
            return
        evaluation = self.db.query(Evaluation).filter_by(application_id=application_id).one_or_none()
        if evaluation is None:
            evaluation = Evaluation(application_id=application_id)
            self.db.add(evaluation)

        evaluation.fairness_score = report.fairness_score
        evaluation.bias_flags = report.bias_flags
        evaluation.grounding_score = report.grounding_score
        evaluation.passed_guardrails = report.passed_guardrails
        evaluation.raw_report = report.raw_report
        self.db.flush()

    def _create_interview(self, application_id: str, question_bank: QuestionGenerationResult) -> Interview:
        interview = Interview(
            application_id=application_id,
            questions=[q.model_dump() for q in question_bank.questions],
        )
        self.db.add(interview)
        self.db.flush()
        return interview
