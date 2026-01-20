"""Extractor registry for dynamic provider support."""

from typing import Dict, Optional, Type

from trustmodel_mcp.extractors.base import BaseExtractor
from trustmodel_mcp.extractors.anthropic import AnthropicExtractor
from trustmodel_mcp.extractors.openai import OpenAIExtractor


class ExtractorRegistry:
    """Registry for LLM provider extractors.

    Allows dynamic registration of new providers.

    Usage:
        registry = ExtractorRegistry()

        # Get extractor for a provider
        extractor = registry.get("anthropic")

        # Register a custom extractor
        registry.register(MyCustomExtractor)
    """

    def __init__(self):
        self._extractors: Dict[str, BaseExtractor] = {}

        # Register built-in extractors
        self.register(AnthropicExtractor())
        self.register(OpenAIExtractor())

    def register(self, extractor: BaseExtractor) -> None:
        """Register an extractor."""
        self._extractors[extractor.provider_name] = extractor

    def get(self, provider: str) -> Optional[BaseExtractor]:
        """Get extractor for a provider."""
        return self._extractors.get(provider.lower())

    def list_providers(self) -> list[str]:
        """List all registered providers."""
        return list(self._extractors.keys())

    def has_provider(self, provider: str) -> bool:
        """Check if a provider is registered."""
        return provider.lower() in self._extractors


# Global registry instance
_registry: Optional[ExtractorRegistry] = None


def get_registry() -> ExtractorRegistry:
    """Get the global extractor registry."""
    global _registry
    if _registry is None:
        _registry = ExtractorRegistry()
    return _registry
