"""HTTP client for TrustModel API."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional, TypeVar
from uuid import UUID

import httpx
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from trustmodel.core.config import TrustModelConfig, get_config
from trustmodel.core.exceptions import (
    APIError,
    AuthenticationError,
    RateLimitError,
    ServerError,
)
from trustmodel.core.logging import get_logger

T = TypeVar("T", bound=BaseModel)
logger = get_logger(__name__)


class TrustModelClient:
    """HTTP client for TrustModel API."""

    def __init__(self, config: Optional[TrustModelConfig] = None) -> None:
        self.config = config or get_config()
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.server_url,
                timeout=httpx.Timeout(self.config.request_timeout),
                headers=self._get_headers(),
            )
        return self._client

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "trustmodel-sdk/0.1.0",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "TrustModelClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _handle_error(self, response: httpx.Response) -> None:
        """Handle error responses."""
        status = response.status_code

        try:
            body = response.json()
        except Exception:
            body = {"detail": response.text}

        if status == 401:
            raise AuthenticationError(
                body.get("detail", "Authentication failed"),
                reason="invalid_credentials",
            )
        elif status == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                body.get("detail", "Rate limit exceeded"),
                retry_after=float(retry_after) if retry_after else None,
            )
        elif status >= 500:
            raise ServerError(
                body.get("detail", "Server error"),
                status_code=status,
            )
        else:
            raise APIError(
                body.get("detail", f"Request failed with status {status}"),
                status_code=status,
                response_body=body,
            )

    @retry(
        retry=retry_if_exception_type((ServerError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with retry logic."""
        logger.debug(
            "API request",
            method=method,
            path=path,
            params=params,
        )

        response = await self.client.request(
            method=method,
            url=path,
            params=params,
            json=json,
        )

        if response.status_code >= 400:
            self._handle_error(response)

        if response.status_code == 204:
            return {}

        return response.json()

    async def get(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make a GET request."""
        return await self._request("GET", path, params=params)

    async def post(
        self,
        path: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make a POST request."""
        return await self._request("POST", path, params=params, json=json)

    async def patch(
        self,
        path: str,
        json: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make a PATCH request."""
        return await self._request("PATCH", path, json=json)

    async def delete(self, path: str) -> dict[str, Any]:
        """Make a DELETE request."""
        return await self._request("DELETE", path)

    # Agent endpoints
    async def register_agent(self, data: dict[str, Any]) -> dict[str, Any]:
        """Register a new agent."""
        return await self.post("/v1/agents", json=data)

    async def get_agent(self, agent_id: UUID) -> dict[str, Any]:
        """Get agent details."""
        return await self.get(f"/v1/agents/{agent_id}")

    async def list_agents(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> dict[str, Any]:
        """List agents."""
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        return await self.get("/v1/agents", params=params)

    async def update_agent(
        self,
        agent_id: UUID,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update agent details."""
        return await self.patch(f"/v1/agents/{agent_id}", json=data)

    async def delete_agent(self, agent_id: UUID) -> None:
        """Delete an agent."""
        await self.delete(f"/v1/agents/{agent_id}")

    # Trace endpoints
    async def ingest_traces(self, data: dict[str, Any]) -> dict[str, Any]:
        """Ingest trace batch."""
        return await self.post("/v1/traces/batch", json=data)

    async def get_trace(
        self,
        trace_id: UUID,
        include_spans: bool = True,
    ) -> dict[str, Any]:
        """Get trace details."""
        return await self.get(
            f"/v1/traces/{trace_id}",
            params={"include_spans": include_spans},
        )

    async def list_traces(
        self,
        agent_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """List traces."""
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if agent_id:
            params["agent_id"] = str(agent_id)
        return await self.get("/v1/traces", params=params)

    # Evaluation endpoints
    async def start_evaluation(self, data: dict[str, Any]) -> dict[str, Any]:
        """Start an evaluation run."""
        return await self.post("/v1/evaluations", json=data)

    async def get_evaluation(self, evaluation_id: UUID) -> dict[str, Any]:
        """Get evaluation details."""
        return await self.get(f"/v1/evaluations/{evaluation_id}")

    async def list_evaluations(
        self,
        agent_id: Optional[UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """List evaluations."""
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if agent_id:
            params["agent_id"] = str(agent_id)
        if status:
            params["status"] = status
        return await self.get("/v1/evaluations", params=params)

    # Certificate endpoints
    async def issue_certificate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Issue a certificate."""
        return await self.post("/v1/certificates", json=data)

    async def get_certificate(self, certificate_id: UUID) -> dict[str, Any]:
        """Get certificate details."""
        return await self.get(f"/v1/certificates/{certificate_id}")

    async def verify_certificate(self, certificate_id: UUID) -> dict[str, Any]:
        """Verify a certificate."""
        return await self.get(f"/v1/certificates/{certificate_id}/verify")

    async def revoke_certificate(
        self,
        certificate_id: UUID,
        reason: str,
    ) -> dict[str, Any]:
        """Revoke a certificate."""
        return await self.post(
            f"/v1/certificates/{certificate_id}/revoke",
            json={"reason": reason},
        )

    # Session endpoints
    async def create_session(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a TACP session."""
        return await self.post("/v1/sessions", json=data)

    async def get_session(self, session_id: UUID) -> dict[str, Any]:
        """Get session details."""
        return await self.get(f"/v1/sessions/{session_id}")

    async def accept_session(self, session_id: UUID) -> dict[str, Any]:
        """Accept a session."""
        return await self.post(f"/v1/sessions/{session_id}/accept")

    async def end_session(self, session_id: UUID) -> None:
        """End a session."""
        await self.delete(f"/v1/sessions/{session_id}")

    # Registry endpoints
    async def search_registry(
        self,
        agent_name: Optional[str] = None,
        min_grade: Optional[str] = None,
        capabilities: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Search the trust registry."""
        params: dict[str, Any] = {}
        if agent_name:
            params["agent_name"] = agent_name
        if min_grade:
            params["min_grade"] = min_grade
        if capabilities:
            params["capabilities"] = capabilities
        return await self.get("/v1/registry/search", params=params)


@lru_cache()
def get_client() -> TrustModelClient:
    """Get cached API client."""
    return TrustModelClient()
