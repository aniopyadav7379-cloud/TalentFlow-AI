from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_embedding_client, get_storage, get_vector_store
from app.db.postgres.models import Candidate, User
from app.db.postgres.session import get_db
from app.db.qdrant.client import VectorStore
from app.schemas.candidate import CandidateCreate, CandidateOut, ResumeOut
from app.services.embeddings import EmbeddingClient
from app.services.resume_ingestion import ResumeIngestionService
from app.services.storage import StorageBackend

router = APIRouter(prefix="/candidates", tags=["candidates"])

_MAX_RESUME_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def create_candidate(
    payload: CandidateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Candidate:
    existing = db.query(Candidate).filter_by(email=payload.email).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A candidate with this email already exists")

    candidate = Candidate(**payload.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.get("", response_model=list[CandidateOut])
def list_candidates(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Candidate]:
    return db.query(Candidate).order_by(Candidate.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate(candidate_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    db.delete(candidate)  # cascades to resumes + applications via the model's relationship config
    db.commit()


@router.post("/{candidate_id}/resume", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    candidate_id: str,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    storage: StorageBackend = Depends(get_storage),
):
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF resumes are accepted")

    content = await file.read()
    if len(content) > _MAX_RESUME_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Resume file exceeds 10MB limit")

    service = ResumeIngestionService(db, vector_store, embedding_client, storage)
    resume = service.ingest(candidate_id, file.filename or "resume.pdf", content)
    return resume