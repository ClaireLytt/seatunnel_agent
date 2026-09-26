from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from seatunnel_agent.config import Settings
from seatunnel_agent.llm import LLMClient, LLMResponse, ToolCall, _convert_tools_to_openai
from seatunnel_agent.tools import TOOL_DEFINITIONS


ANTHROPIC_SETTINGS = Settings(
    api_key="sk-test",
    seatunnel_home="/tmp/seatunnel",
    llm_provider="anthropic",
)

OPENAI_SETTINGS = Settings(
    api_key="sk-test",
    seatunnel_home="/tmp/seatunnel",
    llm_provider="openai",
    llm_base_url="https://api.example.com/v1",
)


class TestToolCallDataclass:
    def test_fields(self):
        tc = ToolCall(id="t1", name="read_config", input={"path": "/tmp"})
        assert tc.id == "t1"
        assert tc.name == "read_config"
        assert tc.input == {"path": "/tmp"}


class TestLLMResponse:
    def test_no_tool_use(self):
        r = LLMResponse(
            wants_tool_use=False, tool_calls=[], thinking_text="",
            reply_text="hello", raw_content="hello",
        )
        assert not r.wants_tool_use
        assert r.reply_text == "hello"

    def test_with_tool_use(self):
        tc = ToolCall(id="t1", name="validate_config", input={})
        r = LLMResponse(
            wants_tool_use=True, tool_calls=[tc], thinking_text="thinking",
            reply_text="", raw_content=None,
        )
        assert r.wants_tool_use
        assert len(r.tool_calls) == 1
        assert r.thinking_text == "thinking"


class TestConvertToolsToOpenAI:
    def test_format(self):
        tools = _convert_tools_to_openai(TOOL_DEFINITIONS)
        assert isinstance(tools, list)
        assert len(tools) > 0
        for t in tools:
            assert t["type"] == "function"
            assert "name" in t["function"]
            assert "description" in t["function"]
            assert "parameters" in t["function"]


class TestLLMClientInit:
    def test_invalid_provider(self):
        bad_settings = Settings(api_key="k", llm_provider="bad_provider")
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            LLMClient(bad_settings)

    @patch("seatunnel_agent.llm.anthropic", create=True)
    def test_anthropic_init(self, mock_mod):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)
        assert client.provider == "anthropic"

    @patch("seatunnel_agent.llm.openai", create=True)
    def test_openai_init(self, mock_mod):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            client = LLMClient(OPENAI_SETTINGS)
        assert client.provider == "openai"


class TestBuildToolResultMessage:
    def test_anthropic_format(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)
        tool_results = [
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"},
        ]
        msg = client.build_tool_result_message(tool_results)
        assert msg["role"] == "user"
        assert msg["content"] == tool_results

    def test_openai_format(self):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            client = LLMClient(OPENAI_SETTINGS)
        tool_results = [
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"},
            {"type": "tool_result", "tool_use_id": "t2", "content": "done"},
        ]
        msgs = client.build_tool_result_message(tool_results)
        assert isinstance(msgs, list)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "tool"
        assert msgs[0]["tool_call_id"] == "t1"
        assert msgs[1]["content"] == "done"


class TestAppendAssistant:
    def test_anthropic(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)
        raw = [{"type": "text", "text": "hello"}]
        result = client.append_assistant(raw)
        assert result["role"] == "assistant"
        assert result["content"] is raw

    def test_openai_plain_text(self):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            client = LLMClient(OPENAI_SETTINGS)
        msg = MagicMock()
        msg.content = "hello"
        msg.tool_calls = None
        result = client.append_assistant(msg)
        assert result["role"] == "assistant"
        assert result["content"] == "hello"
        assert "tool_calls" not in result

    def test_openai_with_tool_calls(self):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            client = LLMClient(OPENAI_SETTINGS)
        tc = MagicMock()
        tc.id = "call_123"
        tc.function.name = "read_config"
        tc.function.arguments = '{"config_path": "/tmp/job.conf"}'
        msg = MagicMock()
        msg.content = ""
        msg.tool_calls = [tc]
        result = client.append_assistant(msg)
        assert result["role"] == "assistant"
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "call_123"
        assert result["tool_calls"][0]["function"]["name"] == "read_config"


class TestCallAnthropic:
    def test_end_turn(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done!"
        response = MagicMock()
        response.content = [text_block]
        response.stop_reason = "end_turn"
        client._client.messages.create = MagicMock(return_value=response)

        result = client.chat("system", [{"role": "user", "content": "hi"}])
        assert isinstance(result, LLMResponse)
        assert result.reply_text == "Done!"
        assert not result.wants_tool_use

    def test_tool_use(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tu_1"
        tool_block.name = "validate_config"
        tool_block.input = {"config_path": "/tmp/j.conf"}
        response = MagicMock()
        response.content = [tool_block]
        response.stop_reason = "tool_use"
        client._client.messages.create = MagicMock(return_value=response)

        result = client.chat("system", [{"role": "user", "content": "validate"}])
        assert result.wants_tool_use
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "validate_config"


class TestCallOpenAI:
    def _make_client(self):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            client = LLMClient(OPENAI_SETTINGS)
        return client

    def test_plain_response(self):
        client = self._make_client()
        msg = MagicMock()
        msg.content = "Here is the config."
        msg.tool_calls = None
        choice = MagicMock()
        choice.message = msg
        response = MagicMock()
        response.choices = [choice]
        client._client.chat.completions.create = MagicMock(return_value=response)

        result = client.chat("system", [{"role": "user", "content": "hi"}])
        assert result.reply_text == "Here is the config."
        assert not result.wants_tool_use

    def test_tool_call_response(self):
        client = self._make_client()
        tc = MagicMock()
        tc.id = "call_1"
        tc.function.name = "write_config"
        tc.function.arguments = json.dumps({"config_path": "/tmp/a.conf", "content": "env{}"})
        msg = MagicMock()
        msg.content = ""
        msg.tool_calls = [tc]
        choice = MagicMock()
        choice.message = msg
        response = MagicMock()
        response.choices = [choice]
        client._client.chat.completions.create = MagicMock(return_value=response)

        result = client.chat("system", [{"role": "user", "content": "write"}])
        assert result.wants_tool_use
        assert result.tool_calls[0].name == "write_config"
        assert result.tool_calls[0].input["config_path"] == "/tmp/a.conf"

    def test_empty_choices_raises(self):
        client = self._make_client()
        response = MagicMock()
        response.choices = []
        client._client.chat.completions.create = MagicMock(return_value=response)

        with pytest.raises(RuntimeError, match="empty response"):
            client.chat("system", [{"role": "user", "content": "hi"}])

    def test_malformed_tool_args(self):
        client = self._make_client()
        tc = MagicMock()
        tc.id = "call_1"
        tc.function.name = "read_config"
        tc.function.arguments = "not-valid-json"
        msg = MagicMock()
        msg.content = ""
        msg.tool_calls = [tc]
        choice = MagicMock()
        choice.message = msg
        response = MagicMock()
        response.choices = [choice]
        client._client.chat.completions.create = MagicMock(return_value=response)

        result = client.chat("system", [{"role": "user", "content": "go"}])
        assert result.tool_calls[0].input == {}


class TestConvertMessage:
    def _make_client(self):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            client = LLMClient(OPENAI_SETTINGS)
        return client

    def test_user_message(self):
        client = self._make_client()
        result = client._convert_message({"role": "user", "content": "hello"})
        assert result == [{"role": "user", "content": "hello"}]

    def test_assistant_with_tool_calls(self):
        client = self._make_client()
        msg = {"role": "assistant", "content": "", "tool_calls": [{"id": "t1"}]}
        result = client._convert_message(msg)
        assert result == [msg]

    def test_tool_message(self):
        client = self._make_client()
        msg = {"role": "tool", "tool_call_id": "t1", "content": "ok"}
        result = client._convert_message(msg)
        assert result == [msg]


class TestLLMResponseUsage:
    def test_default_usage_empty(self):
        r = LLMResponse(
            wants_tool_use=False, tool_calls=[], thinking_text="",
            reply_text="hi", raw_content="hi",
        )
        assert r.usage == {}

    def test_usage_from_anthropic(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done"
        response = MagicMock()
        response.content = [text_block]
        response.stop_reason = "end_turn"
        response.usage.input_tokens = 100
        response.usage.output_tokens = 50
        client._client.messages.create = MagicMock(return_value=response)

        result = client._call_anthropic("system", [{"role": "user", "content": "hi"}])
        assert result.usage["input_tokens"] == 100
        assert result.usage["output_tokens"] == 50

    def test_usage_from_openai(self):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            client = LLMClient(OPENAI_SETTINGS)

        msg = MagicMock()
        msg.content = "Hello"
        msg.tool_calls = None
        msg.reasoning_content = None
        choice = MagicMock()
        choice.message = msg
        response = MagicMock()
        response.choices = [choice]
        response.usage.prompt_tokens = 200
        response.usage.completion_tokens = 80
        client._client.chat.completions.create = MagicMock(return_value=response)

        result = client._call_openai("system", [{"role": "user", "content": "hi"}])
        assert result.usage["input_tokens"] == 200
        assert result.usage["output_tokens"] == 80


class TestRetryLogic:
    def test_call_with_retry_success(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)

        expected = LLMResponse(
            wants_tool_use=False, tool_calls=[], thinking_text="",
            reply_text="ok", raw_content="ok",
        )
        fn = MagicMock(return_value=expected)
        result = client._call_with_retry(fn, "a", "b", max_retries=3)
        assert result == expected
        assert fn.call_count == 1

    def test_call_with_retry_retries_on_429(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)

        expected = LLMResponse(
            wants_tool_use=False, tool_calls=[], thinking_text="",
            reply_text="ok", raw_content="ok",
        )
        err = Exception("rate limit")
        err.status_code = 429
        fn = MagicMock(side_effect=[err, expected])

        with patch("seatunnel_agent.llm.time.sleep"):
            result = client._call_with_retry(fn, "a", max_retries=3)
        assert result == expected
        assert fn.call_count == 2

    def test_call_with_retry_raises_non_retryable(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)

        err = ValueError("bad request")
        fn = MagicMock(side_effect=err)

        with pytest.raises(ValueError, match="bad request"):
            client._call_with_retry(fn, "a", max_retries=3)
        assert fn.call_count == 1

    def test_call_with_retry_exhausts_retries(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)

        err = Exception("server error")
        err.status_code = 500
        fn = MagicMock(side_effect=err)

        with patch("seatunnel_agent.llm.time.sleep"):
            with pytest.raises(Exception, match="server error"):
                client._call_with_retry(fn, "a", max_retries=3)
        assert fn.call_count == 3


class TestDeepSeekThinking:
    def test_reasoning_content_extracted(self):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            client = LLMClient(OPENAI_SETTINGS)

        msg = MagicMock()
        msg.content = "Final answer"
        msg.tool_calls = None
        msg.reasoning_content = "Let me think step by step..."
        choice = MagicMock()
        choice.message = msg
        response = MagicMock()
        response.choices = [choice]
        response.usage.prompt_tokens = 10
        response.usage.completion_tokens = 20
        client._client.chat.completions.create = MagicMock(return_value=response)

        result = client._call_openai("system", [{"role": "user", "content": "hi"}])
        assert result.thinking_text == "Let me think step by step..."
        assert result.reply_text == "Final answer"


class TestRetryStringCodeIgnored:
    """OpenAI errors with string `code` should not match int status codes."""

    def test_string_code_not_retryable(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)

        err = Exception("invalid_api_key")
        err.code = "invalid_api_key"
        fn = MagicMock(side_effect=err)

        with pytest.raises(Exception, match="invalid_api_key"):
            client._call_with_retry(fn, "a", max_retries=3)
        assert fn.call_count == 1

    def test_response_status_code_retryable(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)

        expected = LLMResponse(
            wants_tool_use=False, tool_calls=[], thinking_text="",
            reply_text="ok", raw_content="ok",
        )
        err = Exception("server error")
        resp_mock = MagicMock()
        resp_mock.status_code = 502
        err.response = resp_mock
        fn = MagicMock(side_effect=[err, expected])

        with patch("seatunnel_agent.llm.time.sleep"):
            result = client._call_with_retry(fn, "a", max_retries=3)
        assert result == expected
        assert fn.call_count == 2


class TestSupportsThinking:
    def test_default_keywords_match_claude_models(self):
        assert LLMClient._supports_thinking("claude-sonnet-5")
        assert LLMClient._supports_thinking("claude-opus-5")
        assert LLMClient._supports_thinking("claude-fable-5-1")

    def test_non_thinking_model(self):
        assert not LLMClient._supports_thinking("gpt-4o")
        assert not LLMClient._supports_thinking("deepseek-chat")

    def test_custom_keywords_respected(self):
        with patch("seatunnel_agent.llm._THINKING_MODEL_KEYWORDS", ("deepseek-r1",)):
            assert LLMClient._supports_thinking("deepseek-r1-distill")
            assert not LLMClient._supports_thinking("claude-sonnet-5")

    def test_default_retry_count_from_constant(self):
        import seatunnel_agent.llm as llm_mod
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            client = LLMClient(ANTHROPIC_SETTINGS)
        err = Exception("boom")
        resp_mock = MagicMock()
        resp_mock.status_code = 502
        err.response = resp_mock
        fn = MagicMock(side_effect=err)
        with patch("seatunnel_agent.llm.time.sleep"), \
             pytest.raises(Exception, match="boom"):
            client._call_with_retry(fn, "a")
        assert fn.call_count == llm_mod.DEFAULT_LLM_MAX_RETRIES
