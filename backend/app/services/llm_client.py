"""
LLM completion client, abstracted the same way embeddings.py is: agents never
import `openai` directly, they depend on `LLMClient`.

Every agent call goes through `complete_json`, which enforces that the model
returns valid, schema-shaped JSON — malformed output is a retried/raised
error, never silently coerced into something the agent misinterprets.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Callable

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings


class LLMError(Exception):
    """Raised when an LLM call fails, or returns output that isn't valid JSON, after retries."""


class LLMClient(ABC):
    @abstractmethod
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Return a parsed JSON dict. Raises LLMError if the model doesn't return valid JSON."""


class OpenAILLMClient(LLMClient):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        key = api_key or settings.OPENAI_API_KEY
        if not key:
            raise LLMError(
                "OPENAI_API_KEY is not set. Set it in .env, or use FakeLLMClient for local dev/tests."
            )
        from openai import OpenAI

        self._client = OpenAI(api_key=key)
        self.model = model or settings.LLM_MODEL

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
    )
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            )
            content = response.choices[0].message.content
        except Exception as exc:
            raise LLMError(f"OpenAI chat completion failed: {exc}") from exc

        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise LLMError(f"Model did not return valid JSON: {exc}. Raw content: {content!r}") from exc


class FakeLLMClient(LLMClient):
    """
    Deterministic, offline LLM stand-in for tests.

    Two modes:
    - `responder(system, user) -> dict`: full control, computed per-call
    - `queue=[dict, dict, ...]`: pop a canned response per call, in order

    Exactly one of `responder` or `queue` should be provided.
    """

    def __init__(
        self,
        responder: Callable[[str, str], dict] | None = None,
        queue: list[dict] | None = None,
    ):
        if (responder is None) == (queue is None):
            raise ValueError("Provide exactly one of `responder` or `queue`")
        self._responder = responder
        self._queue = list(queue) if queue is not None else None
        self.call_log: list[tuple[str, str]] = []

    @classmethod
    def constant(cls, response: dict) -> "FakeLLMClient":
        return cls(responder=lambda system, user: response)

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        self.call_log.append((system_prompt, user_prompt))
        if self._responder is not None:
            return self._responder(system_prompt, user_prompt)
        if not self._queue:
            raise LLMError("FakeLLMClient queue exhausted — more calls were made than canned responses provided")
        return self._queue.pop(0)


def get_llm_client() -> LLMClient:
    """Factory: real OpenAI client if a key is configured, otherwise raises — agents must be given a FakeLLMClient explicitly in tests/dev without keys."""
    settings = get_settings()
    if settings.OPENAI_API_KEY:
        return OpenAILLMClient()
    raise LLMError(
        "No OPENAI_API_KEY configured and no explicit LLMClient was provided. "
        "Pass a FakeLLMClient explicitly for local development without an API key."
    )
