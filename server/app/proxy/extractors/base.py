"""Base extractor interface for LLM providers.

This module defines the extensible architecture for adding new LLM providers.
To add a new provider:

1. Create a new file: extractors/your_provider.py
2. Inherit from BaseExtractor
3. Implement extract() method
4. Register in ExtractorRegistry

Example:
    class MyProviderExtractor(BaseExtractor):
        provider_name = "my_provider"
        base_url = "https://api.myprovider.com"

        def extract(self, request_body, response_body, latency_ms):
            # Parse request/response into unified format
            return ExtractedTrace(...)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ExtractedToolCall:
    """A tool call extracted from LLM response."""

    id: str
    name: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedMessage:
    """A message in unified format.

    Compatible with LangSmith trace format:
    - type: "human", "ai", "tool", "system"
    - content: The message text
    - tool_calls: List of tool calls (for AI messages)
    - tool_call_id: For tool response messages
    """

    type: str  # "human", "ai", "tool", "system"
    content: str = ""
    name: Optional[str] = None
    tool_calls: Optional[List[ExtractedToolCall]] = None
    tool_call_id: Optional[str] = None

    # Usage metadata (for AI messages)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Response metadata
    model_name: Optional[str] = None
    finish_reason: Optional[str] = None
    latency_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format matching LangSmith."""
        result: Dict[str, Any] = {
            "type": self.type,
            "content": self.content,
        }

        if self.name:
            result["name"] = self.name

        if self.tool_calls:
            result["tool_calls"] = [
                {"id": tc.id, "name": tc.name, "args": tc.args}
                for tc in self.tool_calls
            ]

        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id

        if self.total_tokens > 0:
            result["usage_metadata"] = {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens,
            }

        if self.model_name or self.finish_reason:
            result["response_metadata"] = {}
            if self.model_name:
                result["response_metadata"]["model_name"] = self.model_name
            if self.finish_reason:
                result["response_metadata"]["finish_reason"] = self.finish_reason

        return result


@dataclass
class ExtractedTrace:
    """A complete trace extracted from request/response pair."""

    provider: str
    messages: List[ExtractedMessage]
    model: str
    thread_id: Optional[str] = None

    # Timing
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    latency_ms: float = 0

    # Aggregated stats
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    tool_call_count: int = 0

    # Raw data for debugging
    raw_request: Optional[Dict[str, Any]] = None
    raw_response: Optional[Dict[str, Any]] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for API."""
        return {
            "provider": self.provider,
            "model": self.model,
            "thread_id": self.thread_id,
            "messages": [m.to_dict() for m in self.messages],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "latency_ms": self.latency_ms,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "tool_call_count": self.tool_call_count,
            "metadata": self.metadata,
        }


class BaseExtractor(ABC):
    """Base class for LLM provider extractors.

    Subclasses must implement:
    - provider_name: Unique identifier for the provider
    - base_url: The provider's API base URL
    - extract(): Parse request/response into unified format
    """

    provider_name: str = "base"
    base_url: str = ""

    # Paths that this extractor handles
    # e.g., ["/v1/messages", "/v1/chat/completions"]
    handled_paths: List[str] = []

    @abstractmethod
    def extract(
        self,
        request_body: Dict[str, Any],
        response_body: Dict[str, Any],
        latency_ms: float = 0,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> ExtractedTrace:
        """Extract trace data from request/response pair.

        Args:
            request_body: The parsed JSON request body
            response_body: The parsed JSON response body
            latency_ms: Request latency in milliseconds
            request_headers: Optional request headers

        Returns:
            ExtractedTrace with unified message format
        """
        pass

    def can_handle(self, path: str) -> bool:
        """Check if this extractor can handle the given path."""
        return any(path.startswith(p) for p in self.handled_paths)

    def extract_text_content(self, content: Any) -> str:
        """Helper to extract text from various content formats."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict):
                    if item.get("type") == "text":
                        texts.append(item.get("text", ""))
            return "\n".join(texts)
        return str(content) if content else ""
