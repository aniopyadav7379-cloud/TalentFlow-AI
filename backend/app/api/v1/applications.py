from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_embedding_client,
    get_enkrypt_client,
    get_llm_client,
    get_vector_store,
)
from app.db.postgres.models import Application, Job, User
from app.db.postgres.session import get_db
from app.db.qdrant.client import VectorStore
from app.orchestrator.shortlist_pipeline import PipelineFatalError, ShortlistPipeline
from app.schemas.application import ApplicationOut, ShortlistEntry
from app.services.embeddings import EmbeddingClient
from app.services.enkrypt_client import EnkryptClient
from app.services.llm_client import LLMClient

router = APIRouter(tags=["applications"])


class RunShortlistRequest(BaseModel):
    top_k: int = Field(default=10, ge=1, le=100)


@router.post("/jobs/{job_id}/shortlist", response_model=list[ShortlistEntry])
def run_shortlist(
    job_id: str,
    payload: RunShortlistRequest = RunShortlistRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    llm_client: LLMClient = Depends(get_llm_client),
    enkrypt_client: EnkryptClient = Depends(get_enkrypt_client),
) -> list[ShortlistEntry]:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    pipeline = ShortlistPipeline(db, vector_store, embedding_client, llm_client, enkrypt_client)
    try:
        final_state = pipeline.run(job_id, top_k=payload.top_k)
    except PipelineFatalError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return final_state["shortlist"]


@router.get("/applications", response_model=list[ApplicationOut])
def list_all_applications(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Application]:
    return db.query(Application).order_by(Application.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/jobs/{job_id}/applications", response_model=list[ApplicationOut])
def list_applications_for_job(
    job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Application]:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return (
        db.query(Application)
        .filter_by(job_id=job_id)
        .order_by(Application.match_score.desc().nullslast())
        .all()
    )


@router.get("/applications/{application_id}", response_model=ApplicationOut)
def get_application(
    application_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application