"""OpenAI (GPT) trace extractor."""

import json
from typing import Any, Dict, List, Optional

from trustmodel_mcp.extractors.base import BaseExtractor
from trustmodel_mcp.models import (
    Message,
    MessageType,
    ToolCall,
    UsageMetadata,
    ResponseMetadata,
)


class OpenAIExtractor(BaseExtractor):
    """Extractor for OpenAI Chat Completions API."""

    provider_name = "openai"

    def extract_messages(
        self,
        request: Dict[str, Any],
        response: Dict[str, Any],
        latency_ms: float = 0,
    ) -> List[Message]:
        """Extract messages from OpenAI request/response."""
        messages: List[Message] = []
        model = self.extract_model(request, response)

        # Extract request messages
        for msg in request.get("messages", []):
            extracted = self._extract_request_message(msg)
            if extracted:
                messages.append(extracted)

        # Extract response
        choices = response.get("choices", [])
        if choices:
            response_msg = self._extract_response_message(
                choices[0], response, model, latency_ms
            )
            if response_msg:
                messages.append(response_msg)

        return messages

    def _extract_request_message(self, msg: Dict[str, Any]) -> Optional[Message]:
        """Extract a message from the request."""
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "system":
            return Message(
                type=MessageType.SYSTEM,
                content=self.extract_text_content(content),
            )

        elif role == "user":
            return Message(
                type=MessageType.HUMAN,
                content=self.extract_text_content(content),
            )

        elif role == "assistant":
            # Previous assistant turn
            tool_calls = self._extract_tool_calls(msg.get("tool_calls", []))

            return Message(
                type=MessageType.AI,
                content=self.extract_text_content(content) if content else "",
                tool_calls=tool_calls if tool_calls else None,
            )

        elif role == "tool":
            return Message(
                type=MessageType.TOOL,
                content=self.extract_text_content(content),
                tool_call_id=msg.get("tool_call_id"),
                name=msg.get("name"),
            )

        elif role == "function":
            # Legacy function calling format
            return Message(
                type=MessageType.TOOL,
                content=self.extract_text_content(content),
                name=msg.get("name"),
            )

        return None

    def _extract_tool_calls(self, raw_tool_calls: List[Dict[str, Any]]) -> List[ToolCall]:
        """Extract tool calls from OpenAI format."""
        tool_calls = []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            args = func.get("arguments", "{}")

            try:
                parsed_args = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                parsed_args = {"raw": args}

            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=func.get("name", ""),
                    args=parsed_args,
                )
            )
        return tool_calls

    def _extract_response_message(
        self,
        choice: Dict[str, Any],
        response: Dict[str, Any],
        model: str,
        latency_ms: float,
    ) -> Optional[Message]:
        """Extract the assistant response message."""
        msg = choice.get("message", {})
        usage = response.get("usage", {})

        content = msg.get("content", "")

        # Extract tool calls
        tool_calls = self._extract_tool_calls(msg.get("tool_calls", []))

        # Handle legacy function calling
        function_call = msg.get("function_call")
        if function_call and not tool_calls:
            args = function_call.get("arguments", "{}")
            try:
                parsed_args = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                parsed_args = {"raw": args}

            tool_calls = [
                ToolCall(
                    id="func_call",
                    name=function_call.get("name", ""),
                    args=parsed_args,
                )
            ]

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        return Message(
            type=MessageType.AI,
            content=self.extract_text_content(content) if content else "",
            tool_calls=tool_calls if tool_calls else None,
            usage_metadata=UsageMetadata(
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            response_metadata=ResponseMetadata(
                model_name=model,
                finish_reason=choice.get("finish_reason"),
                latency_ms=latency_ms,
                provider=self.provider_name,
            ),
        )
