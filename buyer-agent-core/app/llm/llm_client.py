from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.config.settings import LLMProvider, Settings

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    """One turn in the conversation handed to the LLM."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str


@dataclass
class LLMResponse:
    """Raw model output. The Planner - not this module - turns this into a
    structured Decision."""

    content: str
    raw: dict[str, Any] = field(default_factory=dict)


class LLMUnavailableError(Exception):
    """The configured LLM provider could not be reached or returned an error."""


class LLMTimeoutError(LLMUnavailableError):
    """The configured LLM provider did not respond in time."""


class LLMClient(ABC):
    """Provider-independent contract for asking a model to decide the next
    action. Implementations only talk to their specific provider - no
    agent-loop or planning logic belongs here."""

    @abstractmethod
    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        raise NotImplementedError


class EchoLLMClient(LLMClient):
    """Deterministic, network-free client used when no LLM key is configured.
    Lets the service start and be exercised (registry, gateway, wiring)
    without a real provider. Not suitable for real reasoning."""

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        last_user = next((m for m in reversed(messages) if m.role == "user"), None)
        content = (
            '{"action": "FINAL_RESPONSE", "response": '
            '"No LLM provider is configured (set GEMINI_API_KEY or LLM_API_KEY), '
            f'so I could not reason about: {(last_user.content if last_user else "")!r}."}}'
        )
        return LLMResponse(content=content, raw={"provider": "echo"})


class GeminiLLMClient(LLMClient):
    """Minimal Gemini generateContent client built on httpx."""

    def __init__(self, settings: Settings, client: Optional[httpx.Client] = None):
        self._api_key = settings.gemini_api_key
        self._base_url = settings.gemini_base_url
        self._max_tokens = settings.llm_max_output_tokens
        # Short client-level timeout: this call sits on the agent's own
        # think step, and a slow LLM call should fail fast, not stall the
        # whole /buyer/chat request.
        self._client = client or httpx.Client(timeout=15.0)

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        system = "\n".join(m.content for m in messages if m.role == "system")
        turns = [m for m in messages if m.role != "system"]
        contents = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
            for m in turns
        ]
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": self._max_tokens, "temperature": 0.2},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        try:
            response = self._client.post(
                self._base_url,
                params={"key": self._api_key},
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Timed out waiting for Gemini") from exc
        except httpx.RequestError as exc:
            raise LLMUnavailableError(f"Could not reach Gemini: {exc}") from exc

        if response.status_code >= 400:
            raise LLMUnavailableError(f"Gemini returned {response.status_code}: {response.text[:200]}")

        body = response.json()
        try:
            content = body["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError("Malformed response from Gemini") from exc

        content = _strip_code_fences(content)
        return LLMResponse(content=content, raw=body)


class OpenAIChatLLMClient(LLMClient):
    """Minimal OpenAI-compatible Chat Completions client (works with Groq,
    OpenAI, or any OpenAI-shaped endpoint)."""

    def __init__(self, settings: Settings, client: Optional[httpx.Client] = None):
        self._model = settings.llm_model
        self._api_key = settings.llm_api_key
        self._max_tokens = settings.llm_max_output_tokens
        self._client = client or httpx.Client(base_url=settings.llm_base_url, timeout=120.0)

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        openai_messages = []
        for m in messages:
            role = m.role
            content = m.content
            if role == "tool":
                role = "user"
                content = f"[Tool result]\n{content}"
            elif role == "model":
                role = "assistant"
            openai_messages.append({"role": role, "content": content})

        payload = {
            "model": self._model,
            "messages": openai_messages,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            response = self._client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Timed out waiting for the LLM provider") from exc
        except httpx.RequestError as exc:
            raise LLMUnavailableError(f"Could not reach the LLM provider: {exc}") from exc

        if response.status_code >= 400:
            raise LLMUnavailableError(f"LLM provider returned {response.status_code}: {response.text[:200]}")

        body = response.json()
        try:
            content = body["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError("Malformed response from LLM provider") from exc

        return LLMResponse(content=_strip_code_fences(content), raw=body)


def _strip_code_fences(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return content


def create_llm_client(settings: Settings) -> LLMClient:
    """Factory: pick an LLMClient implementation from configuration."""
    if settings.llm_provider == LLMProvider.GEMINI:
        if not settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY not set - using EchoLLMClient (dev only)")
            return EchoLLMClient()
        return GeminiLLMClient(settings)

    if settings.llm_provider == LLMProvider.OPENAI:
        if not settings.llm_api_key:
            logger.warning("LLM_API_KEY not set - using EchoLLMClient (dev only)")
            return EchoLLMClient()
        return OpenAIChatLLMClient(settings)

    logger.warning("LLM_PROVIDER=local or unset - using EchoLLMClient (dev only)")
    return EchoLLMClient()
