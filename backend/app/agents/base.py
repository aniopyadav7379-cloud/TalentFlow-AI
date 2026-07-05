"""
Shared base for every agent.

Agents are plain classes, not a framework abstraction — each one wraps a
narrow, testable unit of work (analyze one resume, rank candidates for one
job, etc.) and raises `AgentError` on failure rather than returning a
half-populated result. The orchestrator (step 4) decides what to do when an
agent fails (retry, skip, halt the pipeline) — agents themselves don't
swallow errors silently.
"""
from abc import ABC


class AgentError(Exception):
    """Raised when an agent cannot produce a valid result — bad LLM output, no candidates found, etc."""

    def __init__(self, agent_name: str, message: str):
        self.agent_name = agent_name
        super().__init__(f"[{agent_name}] {message}")


class BaseAgent(ABC):
    name: str = "base_agent"
