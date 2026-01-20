"""
TrustModel Trace Proxy

Intercepts LLM API calls and captures traces in unified format.
Extensible architecture supports any LLM provider.

Supported providers out-of-the-box:
- Anthropic (Claude)
- OpenAI (GPT-4, etc.)

Usage:
    # Start proxy server
    python -m app.proxy.server --port 8080

    # Configure your SDK
    export ANTHROPIC_BASE_URL=http://localhost:8080/v1/anthropic
    export OPENAI_BASE_URL=http://localhost:8080/v1/openai
"""

from app.proxy.extractors.base import BaseExtractor, ExtractedTrace
from app.proxy.extractors.anthropic import AnthropicExtractor
from app.proxy.extractors.openai import OpenAIExtractor
from app.proxy.registry import ExtractorRegistry

__all__ = [
    "BaseExtractor",
    "ExtractedTrace",
    "AnthropicExtractor",
    "OpenAIExtractor",
    "ExtractorRegistry",
]
