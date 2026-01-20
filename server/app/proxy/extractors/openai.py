"""OpenAI (GPT) trace extractor.

Extracts traces from OpenAI Chat Completions API format.
Supports:
- Text messages
- Tool/function calling
- Multi-turn conversations
- Token usage tracking
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json

from app.proxy.extractors.base import (
    BaseExtractor,
    ExtractedMessage,
    ExtractedToolCall,
    ExtractedTrace,
)


class OpenAIExtractor(BaseExtractor):
    """Extractor for OpenAI Chat Completions API."""

    provider_name = "openai"
    base_url = "https://api.openai.com"
    handled_paths = ["/v1/chat/completions"]

    def extract(
        self,
        request_body: Dict[str, Any],
        response_body: Dict[str, Any],
        latency_ms: float = 0,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> ExtractedTrace:
        """Extract trace from OpenAI request/response."""
        messages: List[ExtractedMessage] = []
        now = datetime.now(timezone.utc)

        # Extract model
        model = response_body.get("model", request_body.get("model", "unknown"))

        # Extract request messages
        for msg in request_body.get("messages", []):
            extracted = self._extract_request_message(msg)
            if extracted:
                messages.append(extracted)

        # Extract response
        choices = response_body.get("choices", [])
        if choices:
            response_msg = self._extract_response_message(
                choices[0], response_body, model, latency_ms
            )
            if response_msg:
                messages.append(response_msg)

        # Calculate totals
        usage = response_body.get("usage", {})
        total_input = usage.get("prompt_tokens", 0)
        total_output = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", total_input + total_output)

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
            total_tokens=total_tokens,
            tool_call_count=tool_call_count,
            raw_request=request_body,
            raw_response=response_body,
            metadata={
                "response_id": response_body.get("id"),
                "system_fingerprint": response_body.get("system_fingerprint"),
            },
        )

    def _extract_request_message(
        self, msg: Dict[str, Any]
    ) -> Optional[ExtractedMessage]:
        """Extract a message from the request."""
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "system":
            return ExtractedMessage(
                type="system",
                content=self.extract_text_content(content),
            )

        elif role == "user":
            return ExtractedMessage(
                type="human",
                content=self.extract_text_content(content),
            )

        elif role == "assistant":
            # Previous assistant turn
            tool_calls = None
            raw_tool_calls = msg.get("tool_calls", [])
            if raw_tool_calls:
                tool_calls = []
                for tc in raw_tool_calls:
                    func = tc.get("function", {})
                    args = func.get("arguments", "{}")
                    try:
                        parsed_args = json.loads(args) if isinstance(args, str) else args
                    except json.JSONDecodeError:
                        parsed_args = {"raw": args}

                    tool_calls.append(
                        ExtractedToolCall(
                            id=tc.get("id", ""),
                            name=func.get("name", ""),
                            args=parsed_args,
                        )
                    )

            return ExtractedMessage(
                type="ai",
                content=self.extract_text_content(content) if content else "",
                tool_calls=tool_calls if tool_calls else None,
            )

        elif role == "tool":
            return ExtractedMessage(
                type="tool",
                content=self.extract_text_content(content),
                tool_call_id=msg.get("tool_call_id"),
                name=msg.get("name"),
            )

        elif role == "function":
            # Legacy function calling format
            return ExtractedMessage(
                type="tool",
                content=self.extract_text_content(content),
                name=msg.get("name"),
            )

        return None

    def _extract_response_message(
        self,
        choice: Dict[str, Any],
        response: Dict[str, Any],
        model: str,
        latency_ms: float,
    ) -> Optional[ExtractedMessage]:
        """Extract the assistant response message."""
        msg = choice.get("message", {})
        usage = response.get("usage", {})

        content = msg.get("content", "")

        # Extract tool calls
        tool_calls = None
        raw_tool_calls = msg.get("tool_calls", [])
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                func = tc.get("function", {})
                args = func.get("arguments", "{}")
                try:
                    parsed_args = json.loads(args) if isinstance(args, str) else args
                except json.JSONDecodeError:
                    parsed_args = {"raw": args}

                tool_calls.append(
                    ExtractedToolCall(
                        id=tc.get("id", ""),
                        name=func.get("name", ""),
                        args=parsed_args,
                    )
                )

        # Handle legacy function calling
        function_call = msg.get("function_call")
        if function_call and not tool_calls:
            args = function_call.get("arguments", "{}")
            try:
                parsed_args = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                parsed_args = {"raw": args}

            tool_calls = [
                ExtractedToolCall(
                    id="func_call",
                    name=function_call.get("name", ""),
                    args=parsed_args,
                )
            ]

        return ExtractedMessage(
            type="ai",
            content=self.extract_text_content(content) if content else "",
            tool_calls=tool_calls if tool_calls else None,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            model_name=model,
            finish_reason=choice.get("finish_reason"),
            latency_ms=latency_ms,
        )
