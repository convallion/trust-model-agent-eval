"""Anthropic (Claude) trace extractor."""

from typing import Any, Dict, List, Optional

from trustmodel_mcp.extractors.base import BaseExtractor
from trustmodel_mcp.models import (
    Message,
    MessageType,
    ToolCall,
    UsageMetadata,
    ResponseMetadata,
)


class AnthropicExtractor(BaseExtractor):
    """Extractor for Anthropic Claude API."""

    provider_name = "anthropic"

    def extract_messages(
        self,
        request: Dict[str, Any],
        response: Dict[str, Any],
        latency_ms: float = 0,
    ) -> List[Message]:
        """Extract messages from Anthropic request/response."""
        messages: List[Message] = []
        model = self.extract_model(request, response)

        # Extract system message if present
        system = request.get("system")
        if system:
            messages.append(
                Message(
                    type=MessageType.SYSTEM,
                    content=self._extract_system_content(system),
                )
            )

        # Extract request messages (user turns and previous assistant turns)
        for msg in request.get("messages", []):
            extracted = self._extract_request_message(msg)
            messages.extend(extracted)

        # Extract response (new assistant turn)
        response_msg = self._extract_response_message(response, model, latency_ms)
        if response_msg:
            messages.append(response_msg)

        return messages

    def _extract_system_content(self, system: Any) -> str:
        """Extract system message content."""
        if isinstance(system, str):
            return system
        if isinstance(system, list):
            texts = []
            for block in system:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif isinstance(block, str):
                    texts.append(block)
            return "\n".join(texts)
        return str(system) if system else ""

    def _extract_request_message(self, msg: Dict[str, Any]) -> List[Message]:
        """Extract messages from a request message."""
        role = msg.get("role", "")
        content = msg.get("content", "")
        messages: List[Message] = []

        if role == "user":
            if isinstance(content, str):
                messages.append(Message(type=MessageType.HUMAN, content=content))
            elif isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_result":
                            # Tool result from previous turn
                            messages.append(
                                Message(
                                    type=MessageType.TOOL,
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
                        0, Message(type=MessageType.HUMAN, content="\n".join(text_parts))
                    )

        elif role == "assistant":
            # Previous assistant turn (context)
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

    def _extract_assistant_content(self, content: Any) -> Optional[Message]:
        """Extract assistant message content."""
        if isinstance(content, str):
            return Message(type=MessageType.AI, content=content)

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
                            ToolCall(
                                id=block.get("id", ""),
                                name=block.get("name", ""),
                                args=block.get("input", {}),
                            )
                        )

            return Message(
                type=MessageType.AI,
                content="\n".join(text_parts),
                tool_calls=tool_calls if tool_calls else None,
            )

        return None

    def _extract_response_message(
        self,
        response: Dict[str, Any],
        model: str,
        latency_ms: float,
    ) -> Optional[Message]:
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
                        ToolCall(
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                            args=block.get("input", {}),
                        )
                    )

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        return Message(
            type=MessageType.AI,
            content="\n".join(text_parts),
            tool_calls=tool_calls if tool_calls else None,
            usage_metadata=UsageMetadata(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            response_metadata=ResponseMetadata(
                model_name=model,
                finish_reason=response.get("stop_reason"),
                latency_ms=latency_ms,
                provider=self.provider_name,
            ),
        )
