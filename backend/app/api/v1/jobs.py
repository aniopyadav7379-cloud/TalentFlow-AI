from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_embedding_client, get_vector_store
from app.db.postgres.models import Job, User
from app.db.postgres.session import get_db
from app.db.qdrant.client import VectorStore
from app.schemas.job import JobCreate, JobOut, JobUpdate
from app.services.embeddings import EmbeddingClient
from app.services.job_ingestion import JobIngestionService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
) -> Job:
    job = Job(**payload.model_dump(), created_by_id=current_user.id)
    db.add(job)
    db.commit()
    db.refresh(job)

    # Embed immediately so the job is searchable/matchable right away —
    # candidate matching depends on this having run.
    JobIngestionService(db, vector_store, embedding_client).ingest(job)
    db.refresh(job)
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Job]:
    return db.query(Job).order_by(Job.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=JobOut)
def update_job(
    job_id: str,
    payload: JobUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    updates = payload.model_dump(exclude_unset=True)
    re_embed_fields = {"title", "description", "requirements", "skills"}
    needs_re_embed = bool(re_embed_fields & updates.keys())

    for field, value in updates.items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)

    if needs_re_embed:
        JobIngestionService(db, vector_store, embedding_client).ingest(job)
        db.refresh(job)
    return job
