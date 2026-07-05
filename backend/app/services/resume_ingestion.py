"""
Resume ingestion: the pipeline that turns an uploaded PDF into a queryable,
ranked candidate signal.

Flow: save file -> extract text -> extract structured info -> embed ->
upsert into Qdrant -> persist Resume row in Postgres.

This is intentionally a plain service class (not a Celery task) so it's
directly unit-testable; the async task wrapper in `app/tasks/` (added when
the API layer is built) will just call `ResumeIngestionService.ingest`.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.postgres.models import Resume
from app.db.qdrant.client import VectorStore
from app.services.embeddings import EmbeddingClient
from app.services.resume_parser import ParsedResume, ResumeParseError, parse_resume_pdf
from app.services.storage import StorageBackend


class ResumeIngestionError(Exception):
    """Raised when the ingestion pipeline cannot complete for a given resume."""


class ResumeIngestionService:
    def __init__(
        self,
        db: Session,
        vector_store: VectorStore,
        embedding_client: EmbeddingClient,
        storage: StorageBackend,
    ):
        self.db = db
        self.vector_store = vector_store
        self.embedding_client = embedding_client
        self.storage = storage

    def ingest(self, candidate_id: str, filename: str, file_bytes: bytes) -> Resume:
        """
        Save the file, parse it, embed it, and persist a fully-populated
        Resume row. On parse failure, still persists a Resume row with
        parse_status="failed" so the upload isn't silently lost — the
        recruiter sees it and can re-upload or the candidate matching agent
        can skip it gracefully instead of crashing the whole batch.
        """
        file_url = self.storage.save(candidate_id, filename, file_bytes)

        resume = Resume(candidate_id=candidate_id, file_url=file_url, parse_status="pending")
        self.db.add(resume)
        self.db.flush()  # assigns resume.id without committing

        try:
            parsed = parse_resume_pdf(file_bytes)
        except ResumeParseError as exc:
            resume.parse_status = "failed"
            resume.raw_text = f"PARSE_FAILED: {exc}"
            self.db.commit()
            return resume

        self._apply_parsed_fields(resume, parsed)

        embedding_text = self._build_embedding_text(parsed)
        vector = self.embedding_client.embed_one(embedding_text)

        point_id = self.vector_store.upsert_resume(
            resume_id=resume.id,
            candidate_id=candidate_id,
            vector=vector,
            payload={
                "skills": parsed.skills,
                "experience_years": parsed.experience_years,
                "file_url": file_url,
            },
        )
        resume.embedding_id = point_id
        resume.parse_status = "parsed"
        self.db.commit()
        return resume

    @staticmethod
    def _apply_parsed_fields(resume: Resume, parsed: ParsedResume) -> None:
        resume.raw_text = parsed.raw_text
        resume.parsed_skills = parsed.skills
        resume.parsed_experience_years = parsed.experience_years
        resume.parsed_education = parsed.education

    @staticmethod
    def _build_embedding_text(parsed: ParsedResume) -> str:
        """
        What actually gets embedded — skills and experience are surfaced
        explicitly (not just left buried in raw text) so semantic search
        weighs them, not just whichever prose happens to mention them most.
        """
        skills_line = f"Skills: {', '.join(parsed.skills)}" if parsed.skills else ""
        experience_line = f"Experience: {parsed.experience_years} years" if parsed.experience_years else ""
        return "\n".join(filter(None, [skills_line, experience_line, parsed.raw_text]))
