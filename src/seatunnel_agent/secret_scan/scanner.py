# -*- coding: utf-8 -*-
"""Secret scanner core — deterministic, offline, never prints the secret.

Scan inline text or walk a directory (binary files, vendored dirs and big
files skipped).  Suppression: the inline pragma ``secretscan:ignore`` on the
flagged line, or a ``.secretscan.yaml`` next to the scan root::

    ignore_rules: [jwt]
    ignore_paths: ["tests/fixtures/*", "*.lock"]

Findings carry a MASKED preview only (first 4 + last 2 chars) — a security
scanner that echoes the full secret into reports/logs defeats itself.
"""

from __future__ import annotations

import fnmatch
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .rules import ENTROPY_RULE, RULES, entropy_hit, is_placeholder

_PRAGMA = "secretscan:ignore"
_MAX_FILE_BYTES = 1 * 1024 * 1024
_SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__",
              ".venv", "venv", ".tox", "dist", "build", ".idea", ".vscode"}
_SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Finding:
    rule_id: str
    severity: str
    file: str
    line: int
    masked: str
    rule_name_en: str = ""
    rule_name_zh: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0

    @property
    def severities(self) -> dict[str, int]:
        out = {"high": 0, "medium": 0, "low": 0}
        for f in self.findings:
            out[f.severity] += 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {"findings": [f.to_dict() for f in self.findings],
                "severities": self.severities,
                "files_scanned": self.files_scanned,
                "files_skipped": self.files_skipped}


@dataclass
class ScanConfig:
    ignore_rules: set[str] = field(default_factory=set)
    ignore_paths: list[str] = field(default_factory=list)


def load_config(root: str | Path) -> ScanConfig:
    """Read ``.secretscan.yaml`` under *root*; missing file → defaults."""
    p = Path(root) / ".secretscan.yaml"
    if not p.is_file():
        return ScanConfig()
    try:
        import yaml
    except ImportError:  # pragma: no cover - pyyaml ships with [all]/[dev]
        raise ValueError("配置文件需要 pyyaml: pip install pyyaml")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"无法读取 {p}: {exc}")
    if not isinstance(raw, dict):
        raise ValueError(f"{p}: 期望顶层为映射")
    return ScanConfig(
        ignore_rules={str(r) for r in raw.get("ignore_rules") or []},
        ignore_paths=[str(g) for g in raw.get("ignore_paths") or []],
    )


def mask(value: str) -> str:
    if len(value) <= 8:
        return value[:2] + "…"
    return value[:4] + "…" + value[-2:]


def scan_text(text: str, name: str = "<inline>",
              config: ScanConfig | None = None) -> list[Finding]:
    config = config or ScanConfig()
    findings: list[Finding] = []
    # generic assignment rules a high-severity hit on the same line makes
    # redundant (the AWS secret IS an apikey_assign match too)
    _GENERIC_ASSIGNS = {"apikey_assign", "password_assign"}
    for lineno, line in enumerate((text or "").splitlines(), 1):
        if _PRAGMA in line:
            continue
        matched_explicit = False
        high_on_line = False
        for rule in RULES:
            if rule.id in config.ignore_rules:
                continue
            if high_on_line and rule.id in _GENERIC_ASSIGNS:
                continue
            m = rule.pattern.search(line)
            if not m:
                continue
            value = m.group(1) if m.groups() else m.group(0)
            # the placeholder filter applies to generic assignment values
            # only — provider-format rules (no capture group) are specific
            # enough to flag even values containing "example"
            if m.groups() and is_placeholder(value):
                continue
            matched_explicit = True
            high_on_line = high_on_line or rule.severity == "high"
            findings.append(Finding(
                rule_id=rule.id, severity=rule.severity, file=name,
                line=lineno, masked=mask(value),
                rule_name_en=rule.name_en, rule_name_zh=rule.name_zh))
        if matched_explicit or ENTROPY_RULE.id in config.ignore_rules:
            continue
        m = ENTROPY_RULE.pattern.search(line)
        if m and entropy_hit(m.group(1)):
            findings.append(Finding(
                rule_id=ENTROPY_RULE.id, severity=ENTROPY_RULE.severity,
                file=name, line=lineno, masked=mask(m.group(1)),
                rule_name_en=ENTROPY_RULE.name_en,
                rule_name_zh=ENTROPY_RULE.name_zh))
    return findings


def _is_binary(path: Path) -> bool:
    try:
        return b"\x00" in path.open("rb").read(8192)
    except OSError:
        return True


def _ignored(rel: str, config: ScanConfig) -> bool:
    rel = rel.replace("\\", "/")
    return any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(Path(rel).name, g)
               for g in config.ignore_paths)


def scan_dir(root: str | Path, config: ScanConfig | None = None) -> ScanResult:
    root = Path(root)
    config = config if config is not None else load_config(root)
    result = ScanResult()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        rel = str(path.relative_to(root))
        if path.name == ".secretscan.yaml" or _ignored(rel, config):
            result.files_skipped += 1
            continue
        try:
            if path.stat().st_size > _MAX_FILE_BYTES or _is_binary(path):
                result.files_skipped += 1
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            result.files_skipped += 1
            continue
        result.files_scanned += 1
        result.findings.extend(scan_text(text, rel, config))
    result.findings.sort(key=lambda f: (_SEV_ORDER[f.severity],
                                        f.file, f.line))
    return result


def scan_paths(paths: list[str | Path],
               config: ScanConfig | None = None) -> ScanResult:
    """Scan a mix of files and directories (pre-commit style)."""
    result = ScanResult()
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            sub = scan_dir(p, config)
            result.findings.extend(sub.findings)
            result.files_scanned += sub.files_scanned
            result.files_skipped += sub.files_skipped
        elif p.is_file():
            cfg = config if config is not None else load_config(p.parent)
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                result.files_skipped += 1
                continue
            result.files_scanned += 1
            result.findings.extend(scan_text(text, str(p), cfg))
    result.findings.sort(key=lambda f: (_SEV_ORDER[f.severity],
                                        f.file, f.line))
    return result


def check_fail(result: ScanResult, fail_on: str) -> bool:
    """True when findings at/above *fail_on* severity exist."""
    threshold = _SEV_ORDER[fail_on]
    return any(_SEV_ORDER[f.severity] <= threshold for f in result.findings)
