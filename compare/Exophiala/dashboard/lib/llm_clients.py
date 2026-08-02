"""
LLM client abstraction — pick Anthropic, OpenAI, or any OpenAI-compatible endpoint.

Usage:
    from lib.llm_clients import make_llm_client
    llm = make_llm_client()
    text = llm.complete(system_prompt, user_prompt, max_tokens=500)

Environment variables (set the ONE you want to use):

  Anthropic:        ANTHROPIC_API_KEY  (+ optional ANTHROPIC_MODEL)
  OpenAI commercial: OPENAI_API_KEY   (+ optional OPENAI_BASE_URL, OPENAI_MODEL)
  OpenAI-compatible: CUSTOM_LLM_BASE_URL (+ CUSTOM_LLM_API_KEY, CUSTOM_LLM_MODEL)
                    — works with Groq, Together, Ollama, vLLM, LM Studio,
                      and custom endpoints like NRP.ai / your HPC cluster LLM service

"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import anthropic
    import httpx

# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class LLMClient(ABC):
    """Abstract base for all LLM backends."""

    @abstractmethod
    def complete(self, system: str, user: str, max_tokens: int) -> str:
        """
        Send a single-turn prompt and return the text content of the reply.

        Args:
            system:  System-prompt text (e.g. instructions for SQL generation).
            user:    User-message text (the actual question / query).
            max_tokens: Hard cap on output tokens.

        Returns:
            Raw text string from the model's reply. Callers are responsible
            for parsing the result (e.g. stripping code fences, validating SQL).
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

class AnthropicClient(LLMClient):
    """
    Anthropic Claude via the official ``anthropic`` Python SDK.

    Env vars:
        ANTHROPIC_API_KEY — required
        ANTHROPIC_MODEL   — defaults to "claude-sonnet-5"
    """

    def __init__(self) -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "anthropic package not installed. Run:\n"
                "  pip install anthropic"
            ) from exc
        import anthropic as _anthropic

        self._client: "anthropic.Anthropic" = _anthropic.Anthropic()
        self._model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")


# ---------------------------------------------------------------------------
# OpenAI / OpenAI-compatible
# ---------------------------------------------------------------------------

class OpenAIClient(LLMClient):
    """
    OpenAI API or any server that implements the ``/v1/chat/completions`` endpoint.

    Handles:
      - OpenAI commercial (api.openai.com)
      - Azure OpenAI (azure.com endpoint format)
      - Self-hosted: Groq, Together, Ollama, vLLM, LM Studio, NRP.ai LLM pods,
        or any other OpenAI-compatible inference server

    Env vars (checked in order, CUSTOM_xxx take priority for the "bring your own"
    endpoint case):

        OPENAI_API_KEY        — used when no custom base URL is set
        OPENAI_BASE_URL       — overrides the default OpenAI base URL
        OPENAI_MODEL          — model name (defaults to gpt-4o)
        CUSTOM_LLM_BASE_URL   — full base URL (e.g. http://llm-service:8000/v1)
        CUSTOM_LLM_API_KEY    — bearer token for the custom endpoint
        CUSTOM_LLM_MODEL      — model name for the custom endpoint

    The first non-empty ``*_BASE_URL`` determines which URL is called.
    ``OPENAI_API_KEY`` and ``CUSTOM_LLM_API_KEY`` are mutually exclusive in
    practice; whichever ``*_BASE_URL`` path is active uses its matching key.
    """

    _DEFAULT_BASE = "https://api.openai.com/v1"
    _DEFAULT_MODEL = "gpt-4o"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        # Resolve base URL: explicit arg > CUSTOM_LLM_BASE_URL > OPENAI_BASE_URL > default
        self._base_url = (
            base_url
            or os.getenv("CUSTOM_LLM_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or self._DEFAULT_BASE
        )

        # Resolve API key: explicit arg > matching env var for the chosen endpoint
        # If the base URL is the default OpenAI one, prefer OPENAI_API_KEY.
        # Otherwise (custom endpoint), prefer CUSTOM_LLM_API_KEY.
        if self._base_url != self._DEFAULT_BASE:
            self._api_key = (
                api_key
                or os.getenv("CUSTOM_LLM_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or ""
            )
        else:
            self._api_key = (
                api_key
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("CUSTOM_LLM_API_KEY")
                or ""
            )

        # Resolve model
        self._model = (
            model
            or os.getenv("CUSTOM_LLM_MODEL")
            or os.getenv("OPENAI_MODEL")
            or self._DEFAULT_MODEL
        )

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        try:
            import httpx  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "httpx package not installed. Run:\n"
                "  pip install httpx"
            ) from exc
        import httpx as _httpx

        url = f"{self._base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        with _httpx.Client(timeout=90.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data: dict = resp.json()

        return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDER_HINTS = {
    "ANTHROPIC_API_KEY": "Anthropic (Claude)",
    "OPENAI_API_KEY":    "OpenAI commercial",
    "CUSTOM_LLM_BASE_URL": "OpenAI-compatible endpoint",
}


def make_llm_client() -> LLMClient:
    """
    Instantiate the first configured LLM client, in priority order:

      1. Anthropic  — if ``ANTHROPIC_API_KEY`` is set
      2. OpenAI-compatible — if ``OPENAI_API_KEY`` or ``CUSTOM_LLM_BASE_URL`` is set
      3. Error — no credentials found

    Raises:
        EnvironmentError: when no credentials are configured.
    """
    if os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicClient()

    if os.getenv("OPENAI_API_KEY") or os.getenv("CUSTOM_LLM_BASE_URL"):
        return OpenAIClient()

    available = [k for k, v in _PROVIDER_HINTS.items() if os.getenv(k)]
    raise EnvironmentError(
        "No LLM credentials found. Set one of the following environment variables:\n"
        + "\n".join(f"  {k:30s} — {v}" for k, v in _PROVIDER_HINTS.items())
        + "\n\n"
          "Examples for each provider:\n"
          "  # Anthropic:\n"
          "  export ANTHROPIC_API_KEY='sk-ant-...'\n"
          "  export ANTHROPIC_MODEL='claude-sonnet-5'\n\n"
          "  # OpenAI commercial:\n"
          "  export OPENAI_API_KEY='sk-...'\n"
          "  export OPENAI_MODEL='gpt-4o'\n\n"
          "  # Custom / NRP.ai / vLLM / Groq / Ollama / LM Studio:\n"
          "  export CUSTOM_LLM_BASE_URL='http://your-llm-service:8000/v1'\n"
          "  export CUSTOM_LLM_API_KEY='<token or empty>'\n"
          "  export CUSTOM_LLM_MODEL='your-model-name'\n"
    )
