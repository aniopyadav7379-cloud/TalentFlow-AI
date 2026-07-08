import mimetypes

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_storage
from app.db.postgres.models import Resume, User
from app.db.postgres.session import get_db
from app.schemas.candidate import ResumeOut
from app.services.storage import StorageBackend

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("", response_model=list[ResumeOut])
def list_resumes(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Resume]:
    return db.query(Resume).order_by(Resume.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{resume_id}/file")
def get_resume_file(
    resume_id: str,
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> Response:
    """
    Streams the actual resume bytes. `Resume.file_url` is an internal storage
    identifier (e.g. "local://candidate_id/uuid_name.pdf"), not something a
    browser can open directly — this endpoint is what resolves it, so the
    frontend should always link here rather than to `file_url` itself.

    Deliberately unauthenticated: this is opened via a plain <a href> / new
    browser tab, which can't attach the app's Bearer token. Safe enough for
    a hackathon MVP since `resume_id` is an unguessable UUID (same trust
    model as a signed CDN link) — revisit if this becomes a real product.
    """
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    if not storage.exists(resume.file_url):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume file is missing from storage")

    content = storage.read(resume.file_url)
    filename = resume.file_url.rsplit("/", 1)[-1]
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )