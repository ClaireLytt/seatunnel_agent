"""Chat/MCP tool entry point for the mock-data generator.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def mock_data(sample: str, count: int = 50, seed: int = 42,
              lang: str = "") -> str:
    """测试数据生成（确定性）：粘贴 CSV（带表头）或 JSONL 样例,按样例形状
    生成 count 行 mock 数据——数值区间/日期窗口/值分布/空值率保留,敏感列
    （手机号/身份证/邮箱/姓名等）现场合成绝不取样。同样例同种子必得同
    结果;完整 CSV 在 JSON 载荷。不连数据库。"""
    from seatunnel_agent.agents.data.mock_data import (
        generate_mock,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    if not (sample or "").strip():
        return "样例不能为空 / sample must not be empty"
    try:
        headers, rows = parse_rows(sample)
        result = generate_mock(headers, rows, count=count, seed=seed)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
