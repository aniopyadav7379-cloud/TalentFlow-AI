from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.postgres.models import User
from app.db.postgres.session import get_db
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    skip: int = 0,
    limit: int = 100,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).offset(skip).limit(limit).all()