"""OpenRouter API client for LLM-as-Judge grading."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

logger = structlog.get_logger()


class OpenRouterError(Exception):
    """Base exception for OpenRouter API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class OpenRouterRateLimitError(OpenRouterError):
    """Raised when rate limited by OpenRouter."""
    pass


class OpenRouterClient:
    """
    Async client for OpenRouter API.

    Provides methods for chat completions with retry logic
    and structured JSON output parsing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        """
        Initialize the OpenRouter client.

        Args:
            api_key: OpenRouter API key (defaults to settings)
            model: Model to use (defaults to settings)
            base_url: API base URL (defaults to settings)
            timeout_seconds: Request timeout (defaults to settings)
            max_retries: Max retry attempts (defaults to settings)
        """
        self.api_key = api_key or settings.openrouter_api_key
        self.model = model or settings.openrouter_model
        self.base_url = base_url or settings.openrouter_base_url
        self.timeout_seconds = timeout_seconds or settings.openrouter_timeout_seconds
        self.max_retries = max_retries or settings.openrouter_max_retries

        if not self.api_key:
            raise ValueError("OpenRouter API key is required")

        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "OpenRouterClient":
        """Enter async context."""
        await self._ensure_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context."""
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://trustmodel.ai",
                    "X-Title": "TrustModel Agent Eval",
                },
                timeout=httpx.Timeout(self.timeout_seconds),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Override model for this request
            temperature: Sampling temperature (0.0 for deterministic)
            max_tokens: Maximum tokens in response
            response_format: Optional response format (e.g., {"type": "json_object"})

        Returns:
            The API response as a dict

        Raises:
            OpenRouterError: If the request fails
            OpenRouterRateLimitError: If rate limited
        """
        client = await self._ensure_client()

        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            payload["response_format"] = response_format

        logger.debug(
            "Sending OpenRouter request",
            model=payload["model"],
            message_count=len(messages),
        )

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=60),
            retry=retry_if_exception_type((OpenRouterRateLimitError, httpx.TimeoutException)),
            reraise=True,
        ):
            with attempt:
                try:
                    response = await client.post(
                        "/chat/completions",
                        json=payload,
                    )

                    if response.status_code == 429:
                        raise OpenRouterRateLimitError(
                            "Rate limited by OpenRouter",
                            status_code=429,
                        )

                    if response.status_code >= 400:
                        error_body = response.json() if response.content else None
                        raise OpenRouterError(
                            f"OpenRouter API error: {response.status_code}",
                            status_code=response.status_code,
                            response_body=error_body,
                        )

                    result = response.json()

                    logger.debug(
                        "OpenRouter response received",
                        model=result.get("model"),
                        usage=result.get("usage"),
                    )

                    return result

                except httpx.TimeoutException:
                    logger.warning("OpenRouter request timed out, retrying...")
                    raise

        # Should not reach here due to reraise=True
        raise OpenRouterError("Max retries exceeded")

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """
        Send a chat completion request expecting JSON response.

        Args:
            messages: List of message dicts
            model: Override model
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Returns:
            Parsed JSON from the response content

        Raises:
            OpenRouterError: If request fails or response is not valid JSON
        """
        response = await self.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        try:
            content = response["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise OpenRouterError(
                f"Failed to parse JSON response: {e}",
                response_body=response,
            )

    async def get_text_response(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """
        Send a request and extract the text response.

        Args:
            messages: List of message dicts
            model: Override model
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Returns:
            The text content of the response
        """
        response = await self.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise OpenRouterError(
                f"Failed to extract text response: {e}",
                response_body=response,
            )


# Module-level client instance for convenience
_default_client: Optional[OpenRouterClient] = None


async def get_openrouter_client() -> OpenRouterClient:
    """Get or create the default OpenRouter client."""
    global _default_client
    if _default_client is None:
        _default_client = OpenRouterClient()
    return _default_client


async def close_openrouter_client() -> None:
    """Close the default OpenRouter client."""
    global _default_client
    if _default_client:
        await _default_client.close()
        _default_client = None
