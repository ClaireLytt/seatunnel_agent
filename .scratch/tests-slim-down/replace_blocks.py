"""Literal, per-file block replacement for ticket 03 (no regex heuristics)."""
from pathlib import Path

RUN_CLI_OLD = """from click.testing import CliRunner

from seatunnel_agent.cli import cli as _cli_root


def _run_cli(args):
    return CliRunner().invoke(_cli_root, args)
"""
RUN_CLI_NEW = "from tests.conftest import run_cli as _run_cli\n"

TEXT_TOOL_OLD = """def _text(reply):
    return LLMResponse(wants_tool_use=False, tool_calls=[], thinking_text="",
                       reply_text=reply, raw_content={"f": 1}, usage={})


def _tool(name, inp, cid="c1"):
    return LLMResponse(wants_tool_use=True,
                       tool_calls=[ToolCall(id=cid, name=name, input=inp)],
                       thinking_text="", reply_text="",
                       raw_content={"f": 1}, usage={})
"""
TEXT_TOOL_NEW = ("from tests.conftest import llm_text as _text, "
                 "llm_tool as _tool\n")

ORCH_OLD = '''def _text(reply: str) -> LLMResponse:
    return LLMResponse(wants_tool_use=False, tool_calls=[], thinking_text="",
                       reply_text=reply, raw_content={"fake": True},
                       usage={"input_tokens": 5, "output_tokens": 5})


def _tool(name: str, tool_input: dict, call_id: str = "t1") -> LLMResponse:
    return LLMResponse(
        wants_tool_use=True,
        tool_calls=[ToolCall(id=call_id, name=name, input=tool_input)],
        thinking_text="", reply_text="", raw_content={"fake": True},
        usage={"input_tokens": 5, "output_tokens": 5})
'''

JOBS = [
    ("tests/test_data_lineage.py", RUN_CLI_OLD, RUN_CLI_NEW),
    ("tests/test_sql_review.py", RUN_CLI_OLD, RUN_CLI_NEW),
    ("tests/test_code_fix.py", TEXT_TOOL_OLD, TEXT_TOOL_NEW),
    ("tests/test_doctor.py", TEXT_TOOL_OLD, TEXT_TOOL_NEW),
    ("tests/test_issue_triage.py", TEXT_TOOL_OLD, TEXT_TOOL_NEW),
    ("tests/test_web_task.py", TEXT_TOOL_OLD, TEXT_TOOL_NEW),
    ("tests/test_orchestrator.py", ORCH_OLD, TEXT_TOOL_NEW),
]

for path, old, new in JOBS:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    n = text.count(old)
    assert n == 1, f"{path}: expected 1 occurrence, found {n}"
    p.write_text(text.replace(old, new), encoding="utf-8")
    print(f"{path}: replaced")
