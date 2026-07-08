from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.postgres.models import Resume, User
from app.db.postgres.session import get_db
from app.schemas.candidate import ResumeOut

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("", response_model=list[ResumeOut])
def list_resumes(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Resume]:
    return db.query(Resume).order_by(Resume.created_at.desc()).offset(skip).limit(limit).all()