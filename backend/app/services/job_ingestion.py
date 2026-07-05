"""
Job ingestion: embeds a job description so it can be matched against
resumes (and, symmetrically, so `search_similar_interview_history` /
future "jobs similar to this one" features have a vector to compare against).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.postgres.models import Job
from app.db.qdrant.client import VectorStore
from app.services.embeddings import EmbeddingClient


class JobIngestionService:
    def __init__(self, db: Session, vector_store: VectorStore, embedding_client: EmbeddingClient):
        self.db = db
        self.vector_store = vector_store
        self.embedding_client = embedding_client

    def ingest(self, job: Job) -> Job:
        embedding_text = self._build_embedding_text(job)
        vector = self.embedding_client.embed_one(embedding_text)

        point_id = self.vector_store.upsert_job(
            job_id=job.id,
            vector=vector,
            payload={
                "title": job.title,
                "skills": job.skills,
                "status": job.status.value if hasattr(job.status, "value") else job.status,
                "location": job.location,
            },
        )
        job.embedding_id = point_id
        self.db.commit()
        return job

    @staticmethod
    def _build_embedding_text(job: Job) -> str:
        skills_line = f"Required skills: {', '.join(job.skills)}" if job.skills else ""
        parts = [job.title, skills_line, job.description, job.requirements or ""]
        return "\n".join(filter(None, parts))
