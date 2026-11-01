"""Guards for the two collision classes agents keep reintroducing.

1. Duplicate CLI command names: click silently replaces an earlier
   command with a later one of the same name (the ``datadict`` incident
   — the quality command shadowed the lineage one until two unrelated
   tests failed). This test names the colliding pair directly.

2. Router pins: a new tool's keywords can silently outrank an existing
   tool for its signature ask (the ddl_evolve vs ddl_guard incident).
   PINS is the single source of truth for contested asks; every entry
   asserts its query still routes to its owner, so adding any new tool
   re-checks all of them. When adding an agent whose domain brushes an
   existing one, add a pin here for the existing tool's signature ask.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_CLI_CMDS = ROOT / "src" / "seatunnel_agent" / "cli_cmds"
_CMD_RE = re.compile(r'@click\.command\(\s*"([^"]+)"')


def test_no_duplicate_cli_command_names():
    names: list[tuple[str, str]] = []
    for py in sorted(_CLI_CMDS.glob("*.py")):
        for m in _CMD_RE.finditer(py.read_text(encoding="utf-8")):
            names.append((m.group(1), py.name))
    dupes = {n for n, c in Counter(n for n, _ in names).items() if c > 1}
    assert not dupes, (
        "duplicate CLI command name(s) — click silently replaces the "
        "earlier one: "
        + "; ".join(f"'{n}' in "
                    + ", ".join(f for name, f in names if name == n)
                    for n in sorted(dupes)))


# (query, expected tool) — the contested asks between neighbouring tools.
# Add a pin when a new agent's domain brushes an existing tool.
PINS: list[tuple[str, str]] = [
    # ddl_guard vs ddl_evolve (2026-10-31: evolve's 迁移/脚本/上线
    # keywords stole this ask until they were trimmed)
    ("上线前帮我看看这份迁移脚本能不能回滚", "ddl_guard"),
    ("新旧两版建表语句帮我生成迁移 ALTER 脚本", "ddl_evolve"),
    # the clash-prone neighbour families (top keyword overlaps)
    ("帮我把这批告警日志聚类看看是不是告警风暴", "alert_storm"),
    ("失败任务按签名聚类,连续失败要点名", "task_failure"),
    ("两份数据行帮我审计一下 join 的匹配率和爆炸系数", "join_audit"),
    ("表写坏了,沿血缘帮我编排回滚和下游重跑", "rollback_plan"),
    ("这张表要退役了,沿血缘出一个 offboard 下线方案", "offboard_plan"),
    # partition_health vs partition_plan (neighbouring domains)
    ("这张表的分区帮我体检一下有没有断档和倾斜", "partition_health"),
    ("新表还没分区,按样例和查询帮我选分区键", "partition_plan"),
    # topic_onboard chains its three neighbours — their signature asks
    # must keep routing to the originals
    ("这份 avro record 帮我落成 hive 建表语句", "avro2ddl"),
    ("照这张表的 DDL 生成 kafka 到 hive 的 seatunnel 配置",
     "seatunnel_gen"),
    ("按这份样例数据帮我生成 DQC 规则 yaml", "dq_rulegen"),
    ("新 topic 接入三连,一次出建表、作业和契约", "topic_onboard"),
]


def test_router_pins_hold():
    from seatunnel_agent.agents.ai.orchestrator.catalog import build_catalog
    from seatunnel_agent.agents.ai.orchestrator.router import suggest

    cat = build_catalog()
    misses = []
    for query, owner in PINS:
        got = suggest(query, cat)
        top = got[0].tool if got else "<nothing>"
        if top != owner:
            misses.append(f"'{query}' -> {top} (pinned to {owner})")
    assert not misses, (
        "router pins lost — a tool's keywords steal a neighbour's "
        "signature ask; trim the thief's keywords, don't move the pin:\n"
        + "\n".join(misses))
