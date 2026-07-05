"""
FastAPI application entrypoint.

Run with: uvicorn app.main:app --reload
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.base import AgentError
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.services.embeddings import EmbeddingError
from app.services.enkrypt_client import EnkryptError
from app.services.llm_client import LLMError

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered recruitment platform: semantic candidate ranking, AI interviews, and bias-checked hiring recommendations.",
    version="0.4.0",
    debug=settings.DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Defense in depth: routes are expected to catch AgentError/PipelineFatalError
# and translate them into proper HTTPExceptions themselves. These handlers
# exist so an *uncaught* infra-level failure (LLM/embedding/guardrail
# provider down) still returns a clean 503, not a raw stack trace.
@app.exception_handler(LLMError)
@app.exception_handler(EmbeddingError)
@app.exception_handler(EnkryptError)
async def _provider_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": f"An upstream AI provider is unavailable: {exc}"},
    )


@app.exception_handler(AgentError)
async def _agent_error_handler(request: Request, exc: AgentError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": f"Agent '{exc.agent_name}' failed to produce a valid result: {exc}"},
    )


@app.get("/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
