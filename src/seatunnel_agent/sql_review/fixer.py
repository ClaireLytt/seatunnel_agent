"""LLM-based auto-fix: rewrite the SQL according to the review findings."""

from __future__ import annotations

import re

from ..config import Settings
from ..llm import LLMClient
from .linter import normalize_dialect
from .prompts import DIALECT_NAMES

_FIX_SYSTEM_PROMPT = """\
You are an expert {dialect_name} engineer. You receive a SQL statement and a
code-review report listing its problems. Rewrite the SQL so that every
critical problem and risk in the report is fixed, while preserving the
original business logic and output columns.

Rules:
- Fix only what the report flags; do not restructure working logic.
- Keep table names, output column names and overall statement shape.
- Where a fix needs a business value you cannot know (e.g. a partition
  date), use a placeholder like '${{bizdate}}' and add a `-- TODO` comment.
- Output ONLY the fixed SQL inside one ```sql code block. No explanations
  before or after the block. You may use `--` comments inside the SQL to
  mark what changed.
"""

_SQL_BLOCK_RE = re.compile(r"```sql\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def generate_fix(
    settings: Settings, sql: str, dialect: str, report_md: str
) -> str:
    """Ask the LLM for a fixed version of *sql* based on *report_md*.

    Returns the fixed SQL text. Raises RuntimeError when the model returns
    no usable SQL block.
    """
    dialect = normalize_dialect(dialect)
    llm = LLMClient(settings)
    system = _FIX_SYSTEM_PROMPT.format(
        dialect_name=DIALECT_NAMES.get(dialect, "SQL")
    )
    user = (
        f"原始 SQL：\n```sql\n{sql}\n```\n\n"
        f"审查报告：\n{report_md}\n\n"
        "请给出修复后的 SQL。"
    )
    resp = llm.chat(system, [{"role": "user", "content": user}])
    text = resp.reply_text or ""
    m = _SQL_BLOCK_RE.search(text)
    if m:
        fixed = m.group(1).strip()
        if fixed:
            return fixed
    # model ignored the code-block instruction but returned bare SQL
    stripped = text.strip()
    if stripped.lower().lstrip("(").startswith(("select", "insert", "with", "create")):
        return stripped
    raise RuntimeError("模型未返回可用的修复 SQL")
