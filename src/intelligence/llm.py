"""
LLM Client Module

Interfaces with LM Studio (or compatible OpenAI-style API).
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class LMStudioClient:
    """
    LLM client for LM Studio or OpenAI-compatible endpoints.

    Uses the OpenAI chat completions API format for compatibility.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        model: str = "llama-3.1-8b-instruct",
        timeout: float = 120.0,
    ):
        """
        Initialize LM Studio client.

        Args:
            base_url: LM Studio API URL (default localhost:1234)
            model: Model identifier (must match loaded model)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

        self._client = httpx.Client(
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
        self._async_client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Synchronous chat completion.

        Args:
            messages: List of {"role": "user"|"assistant", "content": str}
            temperature: Sampling temperature
            max_tokens: Maximum response tokens
            system_prompt: Optional system message

        Returns:
            Assistant response text
        """
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        response = self._client.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        data = response.json()

        return data["choices"][0]["message"]["content"]

    async def achat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Async chat completion."""
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        response = await self._async_client.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        data = response.json()

        return data["choices"][0]["message"]["content"]

    def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Simple completion (wrapped as chat)."""
        return self.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def health_check(self) -> bool:
        """Check if LM Studio is running and responsive."""
        try:
            response = self._client.get(f"{self.base_url}/models")
            return response.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """List available models from LM Studio."""
        try:
            response = self._client.get(f"{self.base_url}/models")
            response.raise_for_status()
            data = response.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logger.warning(f"Failed to list models: {e}")
            return []

    def close(self) -> None:
        """Close HTTP clients."""
        self._client.close()

    async def aclose(self) -> None:
        """Close async HTTP client."""
        await self._async_client.aclose()

    def __enter__(self) -> "LMStudioClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()


# Pre-defined prompts for Valorant coaching
COACHING_SYSTEM_PROMPT = """You are an expert Valorant coach analyzing team communications and tactics.
Your role is to:
1. Evaluate the quality of voice communications during rounds
2. Identify gaps between tactical situations and team responses
3. Provide actionable feedback for improvement

Be specific, constructive, and reference actual callouts from the transcript.
Focus on communication quality, timing, and tactical awareness."""

TRANSCRIPT_CLEANUP_PROMPT = """You are a Valorant transcript editor. Clean up and normalize the following voice chat transcript.
Fix any obvious transcription errors, standardize agent names and map callouts.
Do not change the meaning or add new content.
Return the cleaned transcript in the same format."""
