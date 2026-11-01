"""Topic onboarding chain — one schema in, the landing kit out.

Onboarding a topic means running three agents by hand in the right
order: avro2ddl types the landing table, seatunnel_gen drafts the
ingestion job, contract_gen freezes the schema as a contract (and with
a data sample, dq_rulegen adds the quality gates).  This module chains
them deterministically: the Avro record / JSON Schema goes in once, and
the bundle comes out — CREATE TABLE DDL, linted SeaTunnel HOCON,
contract YAML, optional rules YAML.  Every piece is produced by the
original generator, so each round-trip guard still runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["OnboardBundle", "onboard_topic", "render_onboard"]


@dataclass
class OnboardBundle:
    table: str
    dialect: str
    source: str
    sink: str
    columns_total: int = 0
    lossy: int = 0
    ddl_text: str = ""
    hocon_text: str = ""
    contract_yaml: str = ""
    rules_yaml: str = ""          # empty without a sample
    rules_total: int = 0
    placeholders: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "dialect": self.dialect,
                "source": self.source, "sink": self.sink,
                "columns_total": self.columns_total,
                "lossy": self.lossy,
                "rules_total": self.rules_total,
                "placeholders": list(self.placeholders),
                "warnings": list(self.warnings),
                "ddl_text": self.ddl_text,
                "hocon_text": self.hocon_text,
                "contract_yaml": self.contract_yaml,
                "rules_yaml": self.rules_yaml}


def onboard_topic(schema_text: str, table: str = "",
                  dialect: str = "hive",
                  source: str = "kafka", sink: str = "hive",
                  sample_text: str = "") -> OnboardBundle:
    """Avro record / JSON Schema → DDL + SeaTunnel job + contract
    (+ DQC rules when *sample_text* carries CSV/JSONL sample rows)."""
    from seatunnel_agent.agents.data.contract_gen import generate_contract
    from seatunnel_agent.agents.data.seatunnel_gen import generate_config

    from .converter import convert_schema

    draft = convert_schema(schema_text, table=table, dialect=dialect)
    bundle = OnboardBundle(table=draft.table, dialect=dialect,
                           source=source, sink=sink,
                           columns_total=len(draft.columns),
                           lossy=draft.lossy, ddl_text=draft.ddl_text)

    conf = generate_config(draft.ddl_text, source, sink, dialect=dialect)
    bundle.hocon_text = conf.hocon_text
    bundle.placeholders = list(conf.placeholders)
    bundle.warnings += conf.warnings

    contract = generate_contract(draft.ddl_text, dialect=dialect)
    bundle.contract_yaml = contract.yaml_text
    bundle.warnings += contract.warnings

    if (sample_text or "").strip():
        from seatunnel_agent.agents.data.dq_rulegen import generate_rules
        from seatunnel_agent.agents.data.sample_profile import parse_rows

        headers, rows = parse_rows(sample_text)
        rules = generate_rules(headers, rows, bundle.table)
        bundle.rules_yaml = rules.yaml_text
        bundle.rules_total = len(rules.checks)
    return bundle


def render_onboard(bundle: OnboardBundle, lang: str = "zh") -> str:
    from seatunnel_agent.common.utils import normalize_lang

    from .i18n import tp

    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'ob_title')}", "",
             tp(lang, "ob_scope").format(
                 table=bundle.table, dialect=bundle.dialect,
                 source=bundle.source, sink=bundle.sink,
                 columns=bundle.columns_total, lossy=bundle.lossy)]
    for key, fence, text in (
            ("ob_ddl", "sql", bundle.ddl_text),
            ("ob_conf", "hocon", bundle.hocon_text),
            ("ob_contract", "yaml", bundle.contract_yaml),
            ("ob_rules", "yaml", bundle.rules_yaml)):
        if not text:
            continue
        lines += ["", f"### {tp(lang, key)}", f"```{fence}",
                  text.rstrip(), "```"]
    if not bundle.rules_yaml:
        lines += ["", tp(lang, "ob_no_sample")]
    if bundle.warnings:
        lines += ["", f"### {tp(lang, 'ob_warnings')}"]
        lines += [f"- {w}" for w in bundle.warnings[:5]]
    lines += ["", tp(lang, "ob_disclaimer")]
    return "\n".join(lines)
