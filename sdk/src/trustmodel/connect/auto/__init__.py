"""Auto-detection and patching for LLM libraries."""

from trustmodel.connect.auto.anthropic import patch_anthropic
from trustmodel.connect.auto.openai import patch_openai
from trustmodel.connect.auto.langchain import patch_langchain

__all__ = [
    "patch_anthropic",
    "patch_openai",
    "patch_langchain",
]
