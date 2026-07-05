from fastapi import APIRouter

from app.api.v1 import applications, auth, candidates, interviews, jobs, mastra_bridge

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(jobs.router)
api_router.include_router(candidates.router)
api_router.include_router(applications.router)
api_router.include_router(interviews.router)
# Mastra orchestration bridge — granular per-agent endpoints, additive only.
# See app/api/v1/mastra_bridge.py's module docstring for why this exists
# alongside (not instead of) the existing routes above.
api_router.include_router(mastra_bridge.router)
