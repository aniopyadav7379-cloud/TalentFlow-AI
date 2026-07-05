"""
Candidate Matching Agent.

Deliberately NOT LLM-based: ranking is deterministic and reproducible —
given the same resumes and job, it always returns the same order. This
matters for fairness (no run-to-run variance in who gets shortlisted) and
for cost/speed (Qdrant search is near-instant vs. an LLM call per candidate).

Score = blend of semantic similarity (does the resume *read* like a fit) and
explicit skill overlap (does it literally have the required skills) — pure
semantic similarity alone can be gamed by resumes that use similar language
without having the actual skills, so we anchor it against explicit overlap.
"""
from __future__ import annotations

from app.agents.base import AgentError, BaseAgent
from app.db.qdrant.client import VectorStore
from app.schemas.agents import CandidateMatch
from app.services.embeddings import EmbeddingClient

# Semantic similarity captures "reads like a fit" (context, phrasing, adjacent
# skills); skill overlap is the literal, harder-to-game signal. Weighting
# overlap higher keeps the ranking grounded in explicit requirements.
_SEMANTIC_WEIGHT = 0.4
_SKILL_OVERLAP_WEIGHT = 0.6


class CandidateMatchingAgent(BaseAgent):
    name = "candidate_matching_agent"

    def __init__(self, vector_store: VectorStore, embedding_client: EmbeddingClient):
        self.vector_store = vector_store
        self.embedding_client = embedding_client

    def rank_candidates(
        self,
        job_title: str,
        job_description: str,
        job_skills: list[str],
        top_k: int = 10,
    ) -> list[CandidateMatch]:
        if not job_skills and not job_description.strip():
            raise AgentError(self.name, "Job has no description or skills to match against")

        job_text = self._build_job_text(job_title, job_description, job_skills)
        job_vector = self.embedding_client.embed_one(job_text)

        raw_matches = self.vector_store.search_resumes_for_job(job_vector=job_vector, top_k=top_k)

        results = []
        for match in raw_matches:
            resume_skills = set(s.lower() for s in match.payload.get("skills", []))
            required_skills = set(s.lower() for s in job_skills)

            matched = sorted(resume_skills & required_skills)
            missing = sorted(required_skills - resume_skills)
            overlap_score = len(matched) / len(required_skills) if required_skills else 0.0

            # Qdrant cosine "score" for COSINE distance config is already
            # similarity in [-1, 1] (1 = identical direction); clamp defensively.
            semantic_score = max(0.0, min(1.0, match.score))

            blended = (_SEMANTIC_WEIGHT * semantic_score + _SKILL_OVERLAP_WEIGHT * overlap_score) * 100

            results.append(
                CandidateMatch(
                    resume_id=match.payload.get("resume_id", match.point_id),
                    candidate_id=match.payload.get("candidate_id", ""),
                    semantic_score=semantic_score,
                    skill_overlap_score=overlap_score,
                    match_score=round(blended, 1),
                    matched_skills=matched,
                    missing_skills=missing,
                    rationale=self._build_rationale(matched, missing, semantic_score),
                )
            )

        results.sort(key=lambda r: r.match_score, reverse=True)
        return results

    @staticmethod
    def _build_job_text(title: str, description: str, skills: list[str]) -> str:
        skills_line = f"Required skills: {', '.join(skills)}" if skills else ""
        return "\n".join(filter(None, [title, skills_line, description]))

    @staticmethod
    def _build_rationale(matched: list[str], missing: list[str], semantic_score: float) -> str:
        parts = []
        if matched:
            parts.append(f"Matches {len(matched)} required skill(s): {', '.join(matched)}")
        if missing:
            parts.append(f"missing {len(missing)}: {', '.join(missing)}")
        parts.append(f"semantic similarity {semantic_score:.2f}")
        return "; ".join(parts)
