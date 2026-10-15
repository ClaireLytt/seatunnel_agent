"""Machine-readable review output: JSON and SARIF 2.1.0.

SARIF output can be uploaded to GitHub Code Scanning via
``github/codeql-action/upload-sarif``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .report import CHECK_CATALOG, ReviewReport, Severity

# findings cite locations as "行 6" (zh linter/LLM) or "Line 6" (en LLM)
_LINE_RE = re.compile(r"(?:行|line)\s*(\d+)", re.IGNORECASE)

_SARIF_LEVEL = {
    Severity.CRITICAL: "error",
    Severity.RISK: "warning",
    Severity.SUGGESTION: "note",
}


def finding_line(location: str) -> int:
    m = _LINE_RE.search(location)
    return int(m.group(1)) if m else 1


def _uri(label: str) -> str:
    if label == "<inline>":
        return "inline.sql"
    return label.replace("\\", "/")


def results_to_json(results: list[tuple[str, ReviewReport]]) -> str:
    """One object per source; a single-source review yields a bare object."""
    docs: list[dict[str, Any]] = []
    for label, rep in results:
        stats = rep.stats()
        doc: dict[str, Any] = {
            "source": _uri(label),
            "dialect": rep.dialect,
            "stats": stats,
            "findings": [
                {**f.to_dict(), "line": finding_line(f.location)}
                for f in rep.findings
            ],
        }
        if rep.lineage:
            doc["lineage"] = rep.lineage.to_dict()
        docs.append(doc)
    payload: Any = docs[0] if len(docs) == 1 else docs
    return json.dumps(payload, ensure_ascii=False, indent=2)


def results_to_sarif(results: list[tuple[str, ReviewReport]]) -> str:
    rules = [
        {
            "id": cat,
            "name": cat,
            "shortDescription": {"text": label},
        }
        for cat, label in CHECK_CATALOG.items()
    ]
    rule_index = {cat: i for i, cat in enumerate(CHECK_CATALOG)}
    sarif_results: list[dict[str, Any]] = []
    for label, rep in results:
        uri = _uri(label)
        for f in rep.findings:
            text = f.description
            if f.suggestion:
                text = f"{text}。{f.suggestion}"
            result: dict[str, Any] = {
                "ruleId": f.category,
                "level": _SARIF_LEVEL.get(f.severity, "note"),
                "message": {"text": text},
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": uri},
                        "region": {"startLine": finding_line(f.location)},
                    },
                }],
            }
            idx = rule_index.get(f.category)
            if idx is not None:
                result["ruleIndex"] = idx
            sarif_results.append(result)
    doc = {
        "$schema": ("https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
                    "master/Schemata/sarif-schema-2.1.0.json"),
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "seatunnel-sqlreview",
                    "informationUri": (
                        "https://github.com/ClaireLytt/seatunnel_agent"
                    ),
                    "rules": rules,
                },
            },
            "results": sarif_results,
        }],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2)
