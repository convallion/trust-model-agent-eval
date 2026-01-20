"""Anthropic (Claude) trace extractor.

Extracts traces from Anthropic Messages API format.
Supports:
- Text messages
- Tool use (function calling)
- Multi-turn conversations
- Token usage tracking
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.proxy.extractors.base import (
    BaseExtractor,
    ExtractedMessage,
    ExtractedToolCall,
    ExtractedTrace,
)


class AnthropicExtractor(BaseExtractor):
    """Extractor for Anthropic Claude API."""

    provider_name = "anthropic"
    base_url = "https://api.anthropic.com"
    handled_paths = ["/v1/messages"]

    def extract(
        self,
        request_body: Dict[str, Any],
        response_body: Dict[str, Any],
        latency_ms: float = 0,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> ExtractedTrace:
        """Extract trace from Anthropic request/response."""
        messages: List[ExtractedMessage] = []
        now = datetime.now(timezone.utc)

        # Extract model
        model = response_body.get("model", request_body.get("model", "unknown"))

        # Extract system message if present
        system = request_body.get("system")
        if system:
            messages.append(
                ExtractedMessage(
                    type="system",
                    content=self._extract_system_content(system),
                )
            )

        # Extract request messages (user turns)
        for msg in request_body.get("messages", []):
            extracted = self._extract_request_message(msg)
            if extracted:
                messages.extend(extracted)

        # Extract response (assistant turn)
        response_msg = self._extract_response_message(response_body, model, latency_ms)
        if response_msg:
            messages.append(response_msg)

        # Calculate totals
        usage = response_body.get("usage", {})
        total_input = usage.get("input_tokens", 0)
        total_output = usage.get("output_tokens", 0)

        # Count tool calls
        tool_call_count = 0
        for msg in messages:
            if msg.tool_calls:
                tool_call_count += len(msg.tool_calls)

        return ExtractedTrace(
            provider=self.provider_name,
            model=model,
            messages=messages,
            started_at=now,
            ended_at=now,
            latency_ms=latency_ms,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
            tool_call_count=tool_call_count,
            raw_request=request_body,
            raw_response=response_body,
            metadata={
                "stop_reason": response_body.get("stop_reason"),
                "stop_sequence": response_body.get("stop_sequence"),
            },
        )

    def _extract_system_content(self, system: Any) -> str:
        """Extract system message content."""
        if isinstance(system, str):
            return system
        if isinstance(system, list):
            # System can be list of content blocks
            texts = []
            for block in system:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif isinstance(block, str):
                    texts.append(block)
            return "\n".join(texts)
        return str(system) if system else ""

    def _extract_request_message(
        self, msg: Dict[str, Any]
    ) -> List[ExtractedMessage]:
        """Extract messages from a request message."""
        role = msg.get("role", "")
        content = msg.get("content", "")
        messages: List[ExtractedMessage] = []

        if role == "user":
            # User message - can contain text and tool results
            if isinstance(content, str):
                messages.append(
                    ExtractedMessage(type="human", content=content)
                )
            elif isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_result":
                            # Tool result from previous turn
                            messages.append(
                                ExtractedMessage(
                                    type="tool",
                                    content=self._extract_tool_result_content(
                                        block.get("content", "")
                                    ),
                                    tool_call_id=block.get("tool_use_id"),
                                    name=block.get("name"),
                                )
                            )
                    elif isinstance(block, str):
                        text_parts.append(block)

                if text_parts:
                    messages.insert(
                        0, ExtractedMessage(type="human", content="\n".join(text_parts))
                    )

        elif role == "assistant":
            # Assistant message from previous turn (for context)
            extracted = self._extract_assistant_content(content)
            if extracted:
                messages.append(extracted)

        return messages

    def _extract_tool_result_content(self, content: Any) -> str:
        """Extract content from tool result."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
            return "\n".join(texts)
        return str(content) if content else ""

    def _extract_assistant_content(
        self, content: Any
    ) -> Optional[ExtractedMessage]:
        """Extract assistant message content."""
        if isinstance(content, str):
            return ExtractedMessage(type="ai", content=content)

        if isinstance(content, list):
            text_parts = []
            tool_calls = []

            for block in content:
                if isinstance(block, dict):
                    block_type = block.get("type", "")
                    if block_type == "text":
                        text_parts.append(block.get("text", ""))
                    elif block_type == "tool_use":
                        tool_calls.append(
                            ExtractedToolCall(
                                id=block.get("id", ""),
                                name=block.get("name", ""),
                                args=block.get("input", {}),
                            )
                        )

            return ExtractedMessage(
                type="ai",
                content="\n".join(text_parts),
                tool_calls=tool_calls if tool_calls else None,
            )

        return None

    def _extract_response_message(
        self,
        response: Dict[str, Any],
        model: str,
        latency_ms: float,
    ) -> Optional[ExtractedMessage]:
        """Extract the assistant response message."""
        content_blocks = response.get("content", [])
        usage = response.get("usage", {})

        text_parts = []
        tool_calls = []

        for block in content_blocks:
            if isinstance(block, dict):
                block_type = block.get("type", "")
                if block_type == "text":
                    text_parts.append(block.get("text", ""))
                elif block_type == "tool_use":
                    tool_calls.append(
                        ExtractedToolCall(
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                            args=block.get("input", {}),
                        )
                    )

        return ExtractedMessage(
            type="ai",
            content="\n".join(text_parts),
            tool_calls=tool_calls if tool_calls else None,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            model_name=model,
            finish_reason=response.get("stop_reason"),
            latency_ms=latency_ms,
        )
