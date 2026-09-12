"""LLM provider abstraction layer.

Supports two protocols:
- anthropic: Claude (Anthropic native API)
- openai: Any OpenAI-compatible API (OpenAI, DeepSeek, Qwen, GLM, Moonshot, etc.)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from .config import Settings
from .tools import TOOL_DEFINITIONS


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


def _convert_tools_to_openai() -> list[dict[str, Any]]:
    """Convert Anthropic tool schema to OpenAI function calling format."""
    result = []
    for tool in TOOL_DEFINITIONS:
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

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = settings.llm_provider

        if self.provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(api_key=settings.api_key)
        elif self.provider == "openai":
            import openai
            kwargs: dict[str, Any] = {"api_key": settings.api_key}
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
                return self._call_anthropic_stream(system_prompt, messages, on_text_delta)
            return self._call_anthropic(system_prompt, messages)
        else:
            if on_text_delta:
                return self._call_openai_stream(system_prompt, messages, on_text_delta)
            return self._call_openai(system_prompt, messages)

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
    # Anthropic
    # ------------------------------------------------------------------

    def _call_anthropic(self, system_prompt: str, messages: list) -> LLMResponse:
        response = self._client.messages.create(
            model=self.settings.model_name,
            max_tokens=self.settings.max_tokens,
            system=system_prompt,
            tools=TOOL_DEFINITIONS,
            messages=messages,
            thinking={"type": "adaptive"},
        )

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

        return LLMResponse(
            wants_tool_use=(response.stop_reason == "tool_use"),
            tool_calls=tool_calls,
            thinking_text=thinking,
            reply_text=text,
            raw_content=response.content,
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

        with self._client.messages.stream(
            model=self.settings.model_name,
            max_tokens=self.settings.max_tokens,
            system=system_prompt,
            tools=TOOL_DEFINITIONS,
            messages=messages,
            thinking={"type": "adaptive"},
        ) as stream:
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

            raw_content = stream.get_final_message().content

        full_text = "".join(text_parts)
        return LLMResponse(
            wants_tool_use=len(tool_calls) > 0,
            tool_calls=tool_calls,
            thinking_text=thinking,
            reply_text=full_text,
            raw_content=raw_content,
        )

    # ------------------------------------------------------------------
    # OpenAI-compatible (OpenAI, DeepSeek, Qwen, GLM, Moonshot, ...)
    # ------------------------------------------------------------------

    def _call_openai(self, system_prompt: str, messages: list) -> LLMResponse:
        import openai

        oai_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            oai_messages.extend(self._convert_message(msg))

        try:
            response = self._client.chat.completions.create(
                model=self.settings.model_name,
                max_tokens=self.settings.max_tokens,
                messages=oai_messages,
                tools=_convert_tools_to_openai(),
            )
        except openai.APITimeoutError:
            raise RuntimeError("API request timed out. Check your network or try again.")
        except openai.APIConnectionError:
            raise RuntimeError("Cannot connect to API. Check LLM_BASE_URL and your network.")

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

        raw = choice.message

        return LLMResponse(
            wants_tool_use=len(tool_calls) > 0,
            tool_calls=tool_calls,
            thinking_text="",
            reply_text=text,
            raw_content=raw,
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

        try:
            stream = self._client.chat.completions.create(
                model=self.settings.model_name,
                max_tokens=self.settings.max_tokens,
                messages=oai_messages,
                tools=_convert_tools_to_openai(),
                stream=True,
            )
        except openai.APITimeoutError:
            raise RuntimeError("API request timed out. Check your network or try again.")
        except openai.APIConnectionError:
            raise RuntimeError("Cannot connect to API. Check LLM_BASE_URL and your network.")

        text_parts: list[str] = []
        tc_builders: dict[int, dict[str, Any]] = {}

        for chunk in stream:
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
