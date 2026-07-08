from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_enkrypt_client, get_llm_client
from app.db.postgres.models import Application, Interview, User
from app.db.postgres.session import get_db
from app.orchestrator.interview_evaluation_pipeline import InterviewEvaluationPipeline, InterviewPipelineFatalError
from app.schemas.application import InterviewOut
from app.services.enkrypt_client import EnkryptClient
from app.services.llm_client import LLMClient

router = APIRouter(prefix="/applications/{application_id}/interview", tags=["interviews"])

# Separate top-level router (no application_id in the path) purely for the
# "list every interview" dashboard view. Registered alongside `router` in
# app/api/v1/router.py.
list_router = APIRouter(prefix="/interviews", tags=["interviews"])


@list_router.get("", response_model=list[InterviewOut])
def list_all_interviews(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Interview]:
    return db.query(Interview).order_by(Interview.created_at.desc()).offset(skip).limit(limit).all()


class SubmitResponsesRequest(BaseModel):
    responses: list[dict] = Field(
        ..., description='Each item: {"question_id": str, "question": str, "answer": str}', min_length=1
    )


@router.get("", response_model=InterviewOut)
def get_interview(
    application_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Interview:
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    interview = (
        db.query(Interview).filter_by(application_id=application_id).order_by(Interview.created_at.desc()).first()
    )
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No interview has been generated for this application yet")
    return interview


@router.post("/responses", response_model=InterviewOut)
def submit_responses(
    application_id: str,
    payload: SubmitResponsesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
    enkrypt_client: EnkryptClient = Depends(get_enkrypt_client),
) -> Interview:
    for item in payload.responses:
        missing = {"question_id", "question", "answer"} - item.keys()
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Each response must include question_id, question, and answer. Missing: {missing}",
            )

    pipeline = InterviewEvaluationPipeline(db, llm_client, enkrypt_client)
    try:
        result = pipeline.run(application_id, payload.responses)
    except InterviewPipelineFatalError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return result["interview"]