"""
Mastra bridge endpoints.

Why this file exists: the existing `/jobs/{id}/shortlist` endpoint already
runs the full pipeline (rank -> analyze -> guardrail -> generate questions ->
recommend -> persist) server-side in one call via `ShortlistPipeline`
(app/orchestrator/shortlist_pipeline.py) — that endpoint is untouched by
this file and remains the fast, deterministic path the existing frontend
uses.

Mastra's agent, by contrast, needs each capability exposed as an
independently callable tool so *it* can decide the call sequence, inspect
intermediate results, and pause for human approval between steps. This
router exposes exactly that: one thin endpoint per agent capability. Every
endpoint below constructs the same, already-tested agent classes from
`app/agents/` using the same dependency providers as the rest of the API
(`app/api/deps.py`) — nothing here reimplements agent logic; it only adds a
URL in front of logic that already exists and is already tested.

Note on ordering (Enkrypt before vs. after Recommendation): the reference
hackathon architecture diagram shows Enkrypt after Recommendation. This
router deliberately requires `guardrails_passed`/`bias_flags` as *input* to
`/recommendation` (matching `HRRecommendationAgent.synthesize`'s existing,
tested contract — see app/agents/hr_recommendation_agent.py), because the
guardrail result has to be able to force a "hold" decision, not just review
one after the fact. The Mastra workflow (mastra/src/workflows/hiringWorkflow.ts)
therefore calls the enkrypt tool BEFORE the recommendation tool for that
gating check, and MAY optionally call it again afterward on the
recommendation's own rationale for defense-in-depth — see that file's
comments for the full reasoning.
"""
from fastapi import APIRouter, Depends

from app.agents.candidate_matching_agent import CandidateMatchingAgent
from app.agents.hr_recommendation_agent import HRRecommendationAgent
from app.agents.interview_agent import InterviewAgent
from app.api.deps import (
    get_current_user,
    get_embedding_client,
    get_enkrypt_client,
    get_llm_client,
    get_vector_store,
)
from app.db.postgres.models import User
from app.db.qdrant.client import VectorStore
from app.schemas.agents import CandidateMatch, HRRecommendationResult, InterviewScoreResult, QuestionGenerationResult
from app.schemas.evaluation import EvaluationReport
from app.schemas.mastra_bridge import (
    CandidateRankRequest,
    CandidateSearchMatch,
    CandidateSearchRequest,
    CandidateSearchResponse,
    EnkryptCheckRequest,
    InterviewEvaluateRequest,
    InterviewGenerateRequest,
    RecommendationRequest,
)
from app.services.embeddings import EmbeddingClient
from app.services.enkrypt_client import EnkryptClient
from app.services.llm_client import LLMClient

router = APIRouter(tags=["mastra-bridge"])


@router.post("/candidate/search", response_model=CandidateSearchResponse)
def candidate_search(
    payload: CandidateSearchRequest,
    current_user: User = Depends(get_current_user),
    vector_store: VectorStore = Depends(get_vector_store),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
) -> CandidateSearchResponse:
    """Pure semantic search — no skill-overlap blending, no persistence. Used by Mastra's candidateSearchTool."""
    job_text = "\n".join(filter(None, [payload.job_title, payload.job_description]))
    job_vector = embedding_client.embed_one(job_text)
    raw_matches = vector_store.search_resumes_for_job(job_vector=job_vector, top_k=payload.top_k)

    return CandidateSearchResponse(
        matches=[
            CandidateSearchMatch(
                resume_id=m.payload.get("resume_id", m.point_id),
                candidate_id=m.payload.get("candidate_id", ""),
                score=m.score,
                skills=m.payload.get("skills", []),
            )
            for m in raw_matches
        ]
    )


@router.post("/candidate/rank", response_model=list[CandidateMatch])
def candidate_rank(
    payload: CandidateRankRequest,
    current_user: User = Depends(get_current_user),
    vector_store: VectorStore = Depends(get_vector_store),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
) -> list[CandidateMatch]:
    """Semantic + skill-overlap blended ranking. Used by Mastra's rankingTool. Deterministic — no LLM call."""
    agent = CandidateMatchingAgent(vector_store, embedding_client)
    return agent.rank_candidates(
        job_title=payload.job_title,
        job_description=payload.job_description,
        job_skills=payload.job_skills,
        top_k=payload.top_k,
    )


@router.post("/interview/generate", response_model=QuestionGenerationResult)
def interview_generate(
    payload: InterviewGenerateRequest,
    current_user: User = Depends(get_current_user),
    llm_client: LLMClient = Depends(get_llm_client),
) -> QuestionGenerationResult:
    """Used by Mastra's interviewTool (generate action). No persistence — a pure question-generation call."""
    agent = InterviewAgent(llm_client)
    return agent.generate_questions(
        job_title=payload.job_title,
        job_skills=payload.job_skills,
        candidate_skills=payload.candidate_skills,
        num_questions=payload.num_questions,
    )


@router.post("/interview/evaluate", response_model=InterviewScoreResult)
def interview_evaluate(
    payload: InterviewEvaluateRequest,
    current_user: User = Depends(get_current_user),
    llm_client: LLMClient = Depends(get_llm_client),
) -> InterviewScoreResult:
    """Used by Mastra's interviewTool (evaluate action). No persistence — pure scoring call."""
    agent = InterviewAgent(llm_client)
    return agent.score_responses(job_title=payload.job_title, qa_pairs=payload.qa_pairs)


@router.post("/recommendation", response_model=HRRecommendationResult)
def recommendation(
    payload: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    llm_client: LLMClient = Depends(get_llm_client),
) -> HRRecommendationResult:
    """
    Used by Mastra's recommendationTool. `guardrails_passed`/`bias_flags` must
    come from a prior enkrypt/check call — see the module docstring above on
    why this endpoint requires that as input rather than checking it after.
    """
    agent = HRRecommendationAgent(llm_client)
    return agent.synthesize(
        candidate_name=payload.candidate_name,
        match_score=payload.match_score,
        match_rationale=payload.match_rationale,
        interview_overall_score=payload.interview_overall_score,
        interview_score_breakdown=payload.interview_score_breakdown,
        guardrails_passed=payload.guardrails_passed,
        bias_flags=payload.bias_flags,
    )


@router.post("/enkrypt/check", response_model=EvaluationReport)
def enkrypt_check(
    payload: EnkryptCheckRequest,
    current_user: User = Depends(get_current_user),
    enkrypt_client: EnkryptClient = Depends(get_enkrypt_client),
) -> EvaluationReport:
    """
    Used by Mastra's enkryptTool. Fairness-checks `text`; additionally runs a
    grounding check if `source_text` is given. Generic by design (works on a
    resume analysis, a ranking rationale, or a recommendation rationale)
    rather than assuming one specific upstream shape.
    """
    fairness = enkrypt_client.check_fairness(payload.text, context=payload.context)

    grounding_score = 1.0
    ungrounded_claims: list[str] = []
    passed = fairness.passed
    raw_report = {"fairness": fairness.model_dump()}

    if payload.source_text:
        grounding = enkrypt_client.check_grounding(payload.text, payload.source_text)
        grounding_score = grounding.grounding_score
        ungrounded_claims = grounding.ungrounded_claims
        passed = passed and grounding.passed
        raw_report["grounding"] = grounding.model_dump()

    return EvaluationReport(
        fairness_score=fairness.fairness_score,
        bias_flags=fairness.bias_flags + ungrounded_claims,
        grounding_score=grounding_score,
        passed_guardrails=passed,
        raw_report=raw_report,
    )
