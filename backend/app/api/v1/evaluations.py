from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.postgres.models import Evaluation, User
from app.db.postgres.session import get_db
from app.schemas.application import EvaluationOut

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("", response_model=list[EvaluationOut])
def list_evaluations(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Evaluation]:
    return db.query(Evaluation).order_by(Evaluation.created_at.desc()).offset(skip).limit(limit).all()