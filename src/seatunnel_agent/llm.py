"""LLM provider abstraction layer.

Supports two protocols:
- anthropic: Claude (Anthropic native API)
- openai: Any OpenAI-compatible API (OpenAI, DeepSeek, Qwen, GLM, Moonshot, etc.)
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

from .config import Settings, env_float, env_int

DEFAULT_LLM_MAX_RETRIES = env_int("LLM_MAX_RETRIES", 3)
LLM_RETRY_BACKOFF_BASE = env_float("LLM_RETRY_BACKOFF_BASE", 2.0)

# Comma-separated substrings of model names that support extended thinking.
_THINKING_MODEL_KEYWORDS = tuple(
    k.strip()
    for k in os.getenv(
        "THINKING_MODEL_KEYWORDS", "claude-sonnet,claude-opus,claude-fable"
    ).split(",")
    if k.strip()
)


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    wants_tool_use: bool
    tool_calls: list[ToolCall]
    thinking_text: str
    reply_text: str
    raw_content: Any
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class _StreamedToolCall:
    id: str
    name: str
    arguments: str

    @property
    def function(self) -> _StreamedToolCall:
        return self


@dataclass
class _StreamedMessage:
    content: str | None
    tool_calls: list[_StreamedToolCall] | None


def _convert_tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic tool schema to OpenAI function calling format."""
    result = []
    for tool in tools:
        result.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        })
    return result


class LLMClient:
    """Unified interface over Anthropic and OpenAI-compatible APIs."""

    def __init__(
        self,
        settings: Settings,
        tools: list[dict[str, Any]] | None = None,
    ) -> None:
        self.settings = settings
        self.provider = settings.llm_provider
        self.tools = tools if tools is not None else []

        if self.provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=settings.api_key,
                timeout=settings.llm_timeout,
            )
        elif self.provider == "openai":
            import openai
            kwargs: dict[str, Any] = {
                "api_key": settings.api_key,
                "timeout": settings.llm_timeout,
            }
            if settings.llm_base_url:
                kwargs["base_url"] = settings.llm_base_url
            self._client = openai.OpenAI(**kwargs)
        else:
            raise ValueError(
                f"Unknown LLM_PROVIDER: '{self.provider}'. "
                "Supported: 'anthropic', 'openai'"
            )

    def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        on_text_delta: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        if self.provider == "anthropic":
            if on_text_delta:
                fn = self._call_anthropic_stream
                return self._call_with_retry(fn, system_prompt, messages, on_text_delta)
            return self._call_with_retry(self._call_anthropic, system_prompt, messages)
        else:
            if on_text_delta:
                fn = self._call_openai_stream
                return self._call_with_retry(fn, system_prompt, messages, on_text_delta)
            return self._call_with_retry(self._call_openai, system_prompt, messages)

    def build_tool_result_message(
        self, tool_results: list[dict[str, Any]]
    ) -> dict[str, Any] | list[dict[str, Any]]:
        if self.provider == "anthropic":
            return {"role": "user", "content": tool_results}
        else:
            msgs: list[dict[str, Any]] = []
            for tr in tool_results:
                msgs.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_use_id"],
                    "content": tr["content"],
                })
            return msgs

    def append_assistant(self, raw_content: Any) -> dict[str, Any]:
        if self.provider == "anthropic":
            return {"role": "assistant", "content": raw_content}
        else:
            msg: dict[str, Any] = {
                "role": "assistant",
                "content": raw_content.content or "",
            }
            if raw_content.tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in raw_content.tool_calls
                ]
            return msg

    # ------------------------------------------------------------------
    # Retry helper
    # ------------------------------------------------------------------

    def _call_with_retry(
        self,
        fn: Callable[..., LLMResponse],
        *args: Any,
        max_retries: int = DEFAULT_LLM_MAX_RETRIES,
        **kwargs: Any,
    ) -> LLMResponse:
        for attempt in range(max_retries):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                status = (
                    getattr(exc, "status_code", None)
                    or getattr(getattr(exc, "response", None), "status_code", None)
                    or getattr(exc, "http_status", None)
                )
                if isinstance(status, str):
                    status = None
                exc_str = str(exc).lower()
                retryable = (
                    status in (429, 500, 502, 503, 529)
                    or "rate" in exc_str
                    or "timeout" in exc_str
                    or "timed out" in exc_str
                )
                if not retryable or attempt == max_retries - 1:
                    raise
                wait = LLM_RETRY_BACKOFF_BASE ** attempt
                logger.warning("Retryable error (attempt %d/%d), waiting %ds: %s",
                               attempt + 1, max_retries, wait, exc)
                time.sleep(wait)
        raise RuntimeError("Unreachable")

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------

    @staticmethod
    def _supports_thinking(model_name: str) -> bool:
        return any(k in model_name for k in _THINKING_MODEL_KEYWORDS)

    def _call_anthropic(self, system_prompt: str, messages: list) -> LLMResponse:
        kwargs: dict[str, Any] = dict(
            model=self.settings.model_name,
            max_tokens=self.settings.max_tokens,
            system=system_prompt,
            tools=self.tools,
            messages=messages,
        )
        if self._supports_thinking(self.settings.model_name):
            kwargs["thinking"] = {"type": "adaptive"}
        if self.settings.temperature > 0:
            kwargs["temperature"] = self.settings.temperature
        response = self._client.messages.create(**kwargs)

        thinking = ""
        text = ""
        tool_calls = []

        for block in response.content:
            if not hasattr(block, "type"):
                continue
            if block.type == "thinking" and getattr(block, "thinking", ""):
                thinking = block.thinking
            elif block.type == "text" and block.text:
                text = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id, name=block.name, input=block.input,
                ))

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
            }

        return LLMResponse(
            wants_tool_use=(response.stop_reason == "tool_use"),
            tool_calls=tool_calls,
            thinking_text=thinking,
            reply_text=text,
            raw_content=response.content,
            usage=usage,
        )

    def _call_anthropic_stream(
        self,
        system_prompt: str,
        messages: list,
        on_text_delta: Callable[[str], None],
    ) -> LLMResponse:
        thinking = ""
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        raw_content: list[Any] = []

        current_tool_id = ""
        current_tool_name = ""
        current_tool_json = ""

        stream_kwargs: dict[str, Any] = dict(
            model=self.settings.model_name,
            max_tokens=self.settings.max_tokens,
            system=system_prompt,
            tools=self.tools,
            messages=messages,
        )
        if self._supports_thinking(self.settings.model_name):
            stream_kwargs["thinking"] = {"type": "adaptive"}
        if self.settings.temperature > 0:
            stream_kwargs["temperature"] = self.settings.temperature
        with self._client.messages.stream(**stream_kwargs) as stream:
            for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        current_tool_id = block.id
                        current_tool_name = block.name
                        current_tool_json = ""
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "thinking_delta":
                        thinking += delta.thinking
                    elif delta.type == "text_delta":
                        text_parts.append(delta.text)
                        on_text_delta(delta.text)
                    elif delta.type == "input_json_delta":
                        current_tool_json += delta.partial_json
                elif event.type == "content_block_stop":
                    if current_tool_name:
                        try:
                            args = json.loads(current_tool_json) if current_tool_json else {}
                        except json.JSONDecodeError:
                            args = {}
                        tool_calls.append(ToolCall(
                            id=current_tool_id,
                            name=current_tool_name,
                            input=args,
                        ))
                        current_tool_name = ""

            final_msg = stream.get_final_message()
            raw_content = final_msg.content
            usage = {}
            if hasattr(final_msg, "usage") and final_msg.usage:
                usage = {
                    "input_tokens": getattr(final_msg.usage, "input_tokens", 0),
                    "output_tokens": getattr(final_msg.usage, "output_tokens", 0),
                }

        full_text = "".join(text_parts)
        wants_tool = getattr(final_msg, "stop_reason", None) == "tool_use"
        return LLMResponse(
            wants_tool_use=wants_tool,
            tool_calls=tool_calls,
            thinking_text=thinking,
            reply_text=full_text,
            raw_content=raw_content,
            usage=usage,
        )

    # ------------------------------------------------------------------
    # OpenAI-compatible (OpenAI, DeepSeek, Qwen, GLM, Moonshot, ...)
    # ------------------------------------------------------------------

    def _call_openai(self, system_prompt: str, messages: list) -> LLMResponse:
        import openai

        oai_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            oai_messages.extend(self._convert_message(msg))

        oai_kwargs: dict[str, Any] = dict(
            model=self.settings.model_name,
            max_tokens=self.settings.max_tokens,
            messages=oai_messages,
            tools=_convert_tools_to_openai(self.tools),
        )
        if self.settings.temperature > 0:
            oai_kwargs["temperature"] = self.settings.temperature
        base = self.settings.llm_base_url or "https://api.openai.com"
        try:
            response = self._client.chat.completions.create(**oai_kwargs)
        except openai.APITimeoutError:
            raise RuntimeError(
                f"API request timed out ({self.settings.llm_timeout}s). "
                f"Endpoint: {base} — check network or increase LLM_TIMEOUT."
            )
        except openai.APIConnectionError:
            raise RuntimeError(
                f"Cannot connect to API at {base}. "
                "Check LLM_BASE_URL and your network."
            )

        if not response.choices:
            raise RuntimeError("API returned empty response (no choices).")

        choice = response.choices[0]
        text = choice.message.content or ""
        tool_calls = []

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(
                    id=tc.id, name=tc.function.name, input=args,
                ))

        thinking = getattr(choice.message, "reasoning_content", "") or ""

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "input_tokens": getattr(response.usage, "prompt_tokens", 0),
                "output_tokens": getattr(response.usage, "completion_tokens", 0),
            }

        raw = choice.message

        return LLMResponse(
            wants_tool_use=len(tool_calls) > 0,
            tool_calls=tool_calls,
            thinking_text=thinking,
            reply_text=text,
            raw_content=raw,
            usage=usage,
        )

    def _call_openai_stream(
        self,
        system_prompt: str,
        messages: list,
        on_text_delta: Callable[[str], None],
    ) -> LLMResponse:
        import openai

        oai_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            oai_messages.extend(self._convert_message(msg))

        stream_oai_kwargs: dict[str, Any] = dict(
            model=self.settings.model_name,
            max_tokens=self.settings.max_tokens,
            messages=oai_messages,
            tools=_convert_tools_to_openai(self.tools),
            stream=True,
        )
        if self.settings.temperature > 0:
            stream_oai_kwargs["temperature"] = self.settings.temperature
        if not self.settings.llm_base_url:
            stream_oai_kwargs["stream_options"] = {"include_usage": True}
        base = self.settings.llm_base_url or "https://api.openai.com"
        try:
            stream = self._client.chat.completions.create(**stream_oai_kwargs)
        except openai.APITimeoutError:
            raise RuntimeError(
                f"API request timed out ({self.settings.llm_timeout}s). "
                f"Endpoint: {base} — check network or increase LLM_TIMEOUT."
            )
        except openai.APIConnectionError:
            raise RuntimeError(
                f"Cannot connect to API at {base}. "
                "Check LLM_BASE_URL and your network."
            )

        text_parts: list[str] = []
        tc_builders: dict[int, dict[str, Any]] = {}
        usage: dict[str, int] = {}

        for chunk in stream:
            if hasattr(chunk, "usage") and chunk.usage:
                usage = {
                    "input_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                    "output_tokens": getattr(chunk.usage, "completion_tokens", 0),
                }
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                text_parts.append(delta.content)
                on_text_delta(delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tc_builders:
                        tc_builders[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tc_builders[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc_builders[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc_builders[idx]["arguments"] += tc_delta.function.arguments

        tool_calls: list[ToolCall] = []
        for _idx in sorted(tc_builders):
            b = tc_builders[_idx]
            try:
                args = json.loads(b["arguments"])
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=b["id"], name=b["name"], input=args))

        full_text = "".join(text_parts)

        raw = _StreamedMessage(content=full_text, tool_calls=[
            _StreamedToolCall(id=b["id"], name=b["name"], arguments=b["arguments"])
            for b in (tc_builders[i] for i in sorted(tc_builders))
        ] if tc_builders else None)

        return LLMResponse(
            wants_tool_use=len(tool_calls) > 0,
            tool_calls=tool_calls,
            thinking_text="",
            reply_text=full_text,
            raw_content=raw,
            usage=usage,
        )

    def _convert_message(self, msg: dict[str, Any]) -> list[dict[str, Any]]:
        role = msg.get("role", "user")
        content = msg.get("content")

        # Assistant messages with tool_calls — already a proper dict from append_assistant
        if role == "assistant" and "tool_calls" in msg:
            return [msg]

        # Assistant messages with plain text
        if role == "assistant":
            return [{"role": "assistant", "content": content or ""}]

        # Tool result messages (from build_tool_result_message)
        if role == "tool":
            return [msg]

        # User messages
        return [{"role": role, "content": content if isinstance(content, str) else str(content)}]
