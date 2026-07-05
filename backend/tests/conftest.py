import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.postgres.models import Base
from app.db.postgres.session import get_engine
from app.db.qdrant.client import VectorStore, get_qdrant_client
from app.services.embeddings import FakeEmbeddingClient
from app.services.enkrypt_client import FakeEnkryptClient
from app.services.llm_client import LLMClient
from app.services.storage import LocalStorage


@pytest.fixture()
def test_settings() -> Settings:
    """Isolated settings for tests — never touches real infra or .env secrets."""
    return Settings(
        ENVIRONMENT="test",
        DATABASE_URL="sqlite:///:memory:",
        JWT_SECRET_KEY="test-secret",
        OPENAI_API_KEY=None,
        ENKRYPT_API_KEY=None,
        ENKRYPT_ENABLED=False,
        EMBEDDING_DIM=64,  # small enough for fast tests, large enough for feature hashing to be meaningful
    )


@pytest.fixture()
def db_session(test_settings: Settings) -> Session:
    """Fresh in-memory SQLite DB, schema created, per test."""
    engine = get_engine(test_settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    Session_ = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = Session_()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def vector_store(test_settings: Settings) -> VectorStore:
    """Fully in-process Qdrant — no server, no network, resets every test."""
    client = get_qdrant_client(in_memory=True)
    return VectorStore(client=client, dim=test_settings.EMBEDDING_DIM)


@pytest.fixture()
def embedding_client(test_settings: Settings) -> FakeEmbeddingClient:
    """Deterministic, offline embedding client — no API key or network needed."""
    return FakeEmbeddingClient(dim=test_settings.EMBEDDING_DIM)


@pytest.fixture()
def enkrypt_client() -> FakeEnkryptClient:
    """Deterministic guardrail client, defaults to 'everything passes' unless a test overrides it."""
    return FakeEnkryptClient()


@pytest.fixture()
def local_storage() -> LocalStorage:
    """Isolated temp-dir storage backend, cleaned up automatically after the test."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield LocalStorage(base_dir=tmp_dir)


class MutableLLMClient(LLMClient):
    """
    A FakeLLMClient whose responder can be reassigned after construction.

    The `client` fixture below wires ONE instance of this into the FastAPI
    app's dependency overrides for the whole test. Individual API tests then
    just set `llm_client.responder = my_router_fn` before making a request —
    no need to rebuild the app wiring per test.
    """

    def __init__(self):
        self.responder = lambda system, user: {}
        self.call_log: list[tuple[str, str]] = []

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        self.call_log.append((system_prompt, user_prompt))
        return self.responder(system_prompt, user_prompt)


@pytest.fixture()
def llm_client() -> MutableLLMClient:
    return MutableLLMClient()


@pytest.fixture()
def client(db_session, vector_store, embedding_client, llm_client, enkrypt_client, local_storage):
    """
    A fully wired FastAPI TestClient: real routes, real auth flow, real
    request/response validation — every external dependency (DB, Qdrant,
    embeddings, LLM, Enkrypt, file storage) swapped for the deterministic
    fakes already defined above.
    """
    from app.api import deps
    from app.db.postgres.session import get_db as real_get_db
    from app.main import app as fastapi_app

    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[real_get_db] = override_get_db
    fastapi_app.dependency_overrides[deps.get_vector_store] = lambda: vector_store
    fastapi_app.dependency_overrides[deps.get_embedding_client] = lambda: embedding_client
    fastapi_app.dependency_overrides[deps.get_llm_client] = lambda: llm_client
    fastapi_app.dependency_overrides[deps.get_enkrypt_client] = lambda: enkrypt_client
    fastapi_app.dependency_overrides[deps.get_storage] = lambda: local_storage

    with TestClient(fastapi_app) as test_client:
        yield test_client

    fastapi_app.dependency_overrides.clear()
