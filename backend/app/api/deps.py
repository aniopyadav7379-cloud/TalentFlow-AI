"""
FastAPI dependency providers.

Every route depends on these, never on a concrete client class directly —
this is what makes `app.dependency_overrides` in tests work cleanly (swap
in Fake* clients for the whole app with a few lines, see tests/conftest.py).
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_access_token
from app.db.postgres.models import User
from app.db.postgres.session import get_db
from app.db.qdrant.client import VectorStore
from app.services.embeddings import EmbeddingClient
from app.services.embeddings import get_embedding_client as _get_embedding_client
from app.services.enkrypt_client import EnkryptClient
from app.services.enkrypt_client import get_enkrypt_client as _get_enkrypt_client
from app.services.llm_client import LLMClient
from app.services.llm_client import get_llm_client as _get_llm_client
from app.services.storage import StorageBackend
from app.services.storage import get_storage_backend as _get_storage_backend

_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def _cached_vector_store() -> VectorStore:
    # Built once per process: avoids re-running ensure_collections() on
    # every single request.
    return VectorStore()


def get_vector_store() -> VectorStore:
    return _cached_vector_store()


def get_embedding_client() -> EmbeddingClient:
    return _get_embedding_client()


def get_llm_client() -> LLMClient:
    return _get_llm_client()


def get_enkrypt_client() -> EnkryptClient:
    return _get_enkrypt_client()


def get_storage() -> StorageBackend:
    return _get_storage_backend()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        user_id = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user