"""
Enkrypt AI guardrail client.

IMPORTANT — honesty about what's verified here: Enkrypt AI's exact REST
contract (endpoint paths, request/response shape) isn't something this
codebase has verified against live documentation. `EnkryptAIClient` below
follows the conventions described in the architecture handoff
(`fairness_check.py`, `bias_detection.py`, `grounding_check.py` as separate
concerns hitting a `Bias Detection API` and a grounding/hallucination
endpoint) and typical guardrail-API shapes, but **the endpoint paths and
payload keys are best-effort placeholders that must be confirmed against
Enkrypt's official API docs before this touches production traffic.**
`ENKRYPT_ENABLED=false` in settings lets you run the full pipeline with
`FakeEnkryptClient` while that verification happens.

Everything downstream (the `EvaluationAgent`, the orchestrator) depends only
on the `EnkryptClient` interface, so swapping in the confirmed contract later
is a one-file change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.schemas.evaluation import FairnessCheckResult, GroundingCheckResult


class EnkryptError(Exception):
    """Raised when a guardrail check fails to complete after retries."""


class EnkryptClient(ABC):
    @abstractmethod
    def check_fairness(self, text: str, context: dict | None = None) -> FairnessCheckResult:
        """Evaluate `text` (e.g. an AI-generated resume analysis) for bias/fairness concerns."""

    @abstractmethod
    def check_grounding(self, claim_text: str, source_text: str) -> GroundingCheckResult:
        """Verify that `claim_text` is actually supported by `source_text` (hallucination check)."""


class EnkryptAIClient(EnkryptClient):
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        settings = get_settings()
        key = api_key or settings.ENKRYPT_API_KEY
        base = base_url or (str(settings.ENKRYPT_BASE_URL) if settings.ENKRYPT_BASE_URL else None)
        if not key or not base:
            raise EnkryptError(
                "ENKRYPT_API_KEY and ENKRYPT_BASE_URL must both be set. "
                "Use FakeEnkryptClient for local dev/tests, or set ENKRYPT_ENABLED=false."
            )
        import httpx

        self._client = httpx.Client(
            base_url=base,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=30,
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
    )
    def check_fairness(self, text: str, context: dict | None = None) -> FairnessCheckResult:
        try:
            response = self._client.post(
                "/guardrails/fairness",
                json={"text": text, "context": context or {}},
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise EnkryptError(f"Enkrypt fairness check failed: {exc}") from exc

        return FairnessCheckResult(
            fairness_score=data.get("fairness_score", 0.0),
            bias_flags=data.get("bias_flags", []),
            passed=data.get("passed", False),
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
    )
    def check_grounding(self, claim_text: str, source_text: str) -> GroundingCheckResult:
        try:
            response = self._client.post(
                "/guardrails/grounding",
                json={"claim": claim_text, "source": source_text},
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise EnkryptError(f"Enkrypt grounding check failed: {exc}") from exc

        return GroundingCheckResult(
            grounding_score=data.get("grounding_score", 0.0),
            ungrounded_claims=data.get("ungrounded_claims", []),
            passed=data.get("passed", False),
        )


class FakeEnkryptClient(EnkryptClient):
    """
    Deterministic, offline guardrail client for tests/dev.

    Defaults to "everything passes" so pipeline-level tests aren't tangled
    up in guardrail specifics unless they explicitly want to be — pass
    `fairness_responder`/`grounding_responder` to simulate a flagged result.
    """

    def __init__(
        self,
        fairness_responder: Callable[[str, dict | None], FairnessCheckResult] | None = None,
        grounding_responder: Callable[[str, str], GroundingCheckResult] | None = None,
    ):
        self._fairness_responder = fairness_responder or (
            lambda text, context: FairnessCheckResult(fairness_score=1.0, bias_flags=[], passed=True)
        )
        self._grounding_responder = grounding_responder or (
            lambda claim, source: GroundingCheckResult(grounding_score=1.0, ungrounded_claims=[], passed=True)
        )
        self.fairness_calls: list[tuple[str, dict | None]] = []
        self.grounding_calls: list[tuple[str, str]] = []

    def check_fairness(self, text: str, context: dict | None = None) -> FairnessCheckResult:
        self.fairness_calls.append((text, context))
        return self._fairness_responder(text, context)

    def check_grounding(self, claim_text: str, source_text: str) -> GroundingCheckResult:
        self.grounding_calls.append((claim_text, source_text))
        return self._grounding_responder(claim_text, source_text)


def get_enkrypt_client() -> EnkryptClient:
    settings = get_settings()
    if settings.ENKRYPT_ENABLED and settings.ENKRYPT_API_KEY:
        return EnkryptAIClient()
    return FakeEnkryptClient()
