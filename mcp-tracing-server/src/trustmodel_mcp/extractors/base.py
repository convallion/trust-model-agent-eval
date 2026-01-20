"""Base extractor interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from trustmodel_mcp.models import Message


class BaseExtractor(ABC):
    """Base class for LLM provider extractors.

    Each extractor knows how to parse request/response from a specific
    LLM provider into the unified Message format.
    """

    provider_name: str = "base"

    @abstractmethod
    def extract_messages(
        self,
        request: Dict[str, Any],
        response: Dict[str, Any],
        latency_ms: float = 0,
    ) -> List[Message]:
        """Extract messages from request/response pair.

        Args:
            request: The API request body
            response: The API response body
            latency_ms: Request latency in milliseconds

        Returns:
            List of Message objects in unified format
        """
        pass

    def extract_model(self, request: Dict[str, Any], response: Dict[str, Any]) -> str:
        """Extract model name from request/response."""
        return response.get("model", request.get("model", "unknown"))

    @staticmethod
    def extract_text_content(content: Any) -> str:
        """Helper to extract text from various content formats."""
        if content is None:
            return ""
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
        return str(content)
