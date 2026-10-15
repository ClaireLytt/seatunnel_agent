# -*- coding: utf-8 -*-
"""Dependency health core — declared vs installed, pins, licenses. Offline.

Input is the project's own metadata (pyproject ``[project]`` deps + extras,
and/or ``requirements*.txt``); the environment is read via
``importlib.metadata`` (injectable for tests).  No network: CVE/outdated
checks against PyPI are deliberately out of scope — this is the always-on
hygiene layer a CI can gate on.

Severity ladder: **high** = declared but not installed, or the installed
version violates the declared specifier; **medium** = no version pin at
all, conflicting duplicate declarations, or a copyleft license (worth a
conscious decision); **info** = unknown license.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

_SEV_ORDER = {"high": 0, "medium": 1, "info": 2}
_COPYLEFT = re.compile(r"\b[AL]?GPL\b", re.I)

# name[extras]spec — PEP 508 light (no env markers / URLs needed here)
_REQ_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"(?:\[[^\]]*\])?\s*(?P<spec>[<>=!~][^;#]*)?")


@dataclass
class Requirement:
    name: str            # normalized (lower, - for _)
    raw_name: str
    spec: str            # ">=1.0", "" when unpinned
    group: str           # "project" | extra name | requirements file name


@dataclass
class DepFinding:
    severity: str        # high | medium | info
    category: str        # missing | violated | unpinned | conflict | copyleft | unknown_license
    package: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"severity": self.severity, "category": self.category,
                "package": self.package, "detail": self.detail}


@dataclass
class DepReport:
    findings: list[DepFinding] = field(default_factory=list)
    packages: list[dict[str, Any]] = field(default_factory=list)

    @property
    def severities(self) -> dict[str, int]:
        out = {"high": 0, "medium": 0, "info": 0}
        for f in self.findings:
            out[f.severity] += 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {"findings": [f.to_dict() for f in self.findings],
                "severities": self.severities, "packages": self.packages}


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", (name or "").strip()).lower()


def parse_requirement(line: str, group: str) -> Requirement | None:
    line = line.strip()
    if not line or line.startswith(("#", "-")):  # comments, -r/-e options
        return None
    m = _REQ_RE.match(line)
    if not m:
        return None
    return Requirement(name=normalize_name(m.group("name")),
                       raw_name=m.group("name"),
                       spec=(m.group("spec") or "").strip(),
                       group=group)


def parse_requirements_text(text: str,
                            group: str = "requirements") -> list[Requirement]:
    reqs = []
    for line in (text or "").splitlines():
        r = parse_requirement(line, group)
        if r:
            reqs.append(r)
    return reqs


def parse_pyproject_text(text: str) -> list[Requirement]:
    """[project].dependencies + [project.optional-dependencies] via tomllib."""
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10: tomli via the marker dep
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            raise ValueError(
                "解析 pyproject 需要 Python 3.11+ 或 pip install tomli")
    try:
        data = tomllib.loads(text or "")
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"pyproject.toml 解析失败: {exc}")
    project = data.get("project") or {}
    reqs: list[Requirement] = []
    for line in project.get("dependencies") or []:
        r = parse_requirement(str(line), "project")
        if r:
            reqs.append(r)
    for extra, lines in (project.get("optional-dependencies") or {}).items():
        for line in lines or []:
            r = parse_requirement(str(line), f"extra:{extra}")
            if r:
                reqs.append(r)
    return reqs


# ── environment resolver (injectable) ───────────────────────────────────────

def installed_lookup(name: str) -> tuple[str, str] | None:
    """(version, license) for an installed dist, or None."""
    from importlib import metadata
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return None
    # runtime object is an email.Message (has .get/.get_all); the
    # PackageMetadata protocol in typeshed is narrower
    meta: Any = dist.metadata
    lic = (meta.get("License-Expression") or "").strip()
    if not lic or len(lic) > 60:
        lic = (meta.get("License") or "").strip()
    if not lic or lic.upper() == "UNKNOWN" or len(lic) > 60:
        for cl in meta.get_all("Classifier") or []:
            if cl.startswith("License ::"):
                lic = cl.split("::")[-1].strip()
                break
        else:
            lic = ""
    return dist.version, lic


def _spec_satisfied(version: str, spec: str) -> bool | None:
    """None = cannot evaluate (packaging missing or bad spec)."""
    if not spec:
        return True
    try:
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version
        return Version(version) in SpecifierSet(spec)
    except Exception:  # noqa: BLE001 — packaging absent or exotic spec
        return None


def check(requirements: list[Requirement],
          resolver: Callable[[str], tuple[str, str] | None] | None = None,
          ) -> DepReport:
    resolver = resolver or installed_lookup
    report = DepReport()
    by_name: dict[str, list[Requirement]] = {}
    for r in requirements:
        by_name.setdefault(r.name, []).append(r)

    for name in sorted(by_name):
        reqs = by_name[name]
        specs = sorted({r.spec for r in reqs if r.spec})
        groups = ", ".join(sorted({r.group for r in reqs}))
        installed = resolver(name)
        version, lic = installed if installed else ("", "")
        report.packages.append({
            "package": name, "declared": " | ".join(specs) or "(unpinned)",
            "installed": version or "—", "license": lic or "unknown",
            "groups": groups})

        if len(specs) > 1:
            report.findings.append(DepFinding(
                "medium", "conflict", name,
                f"declared with different specs: {' vs '.join(specs)}"))
        if installed is None:
            report.findings.append(DepFinding(
                "high", "missing", name,
                f"declared in {groups} but not installed"))
        else:
            for spec in specs:
                ok = _spec_satisfied(version, spec)
                if ok is False:
                    report.findings.append(DepFinding(
                        "high", "violated", name,
                        f"installed {version} violates {spec}"))
        if not specs:
            report.findings.append(DepFinding(
                "medium", "unpinned", name,
                "no version specifier — builds are not reproducible"))
        if installed is not None:
            if not lic:
                report.findings.append(DepFinding(
                    "info", "unknown_license", name,
                    "no license metadata on the installed dist"))
            elif _COPYLEFT.search(lic):
                report.findings.append(DepFinding(
                    "medium", "copyleft", name,
                    f"copyleft license: {lic}"))

    report.findings.sort(key=lambda f: (_SEV_ORDER[f.severity],
                                        f.category, f.package))
    return report


def collect_from_path(root: str | Path) -> list[Requirement]:
    """pyproject.toml + every requirements*.txt directly under *root*."""
    root = Path(root)
    reqs: list[Requirement] = []
    py = root / "pyproject.toml"
    if py.is_file():
        reqs.extend(parse_pyproject_text(py.read_text(encoding="utf-8")))
    for f in sorted(root.glob("requirements*.txt")):
        reqs.extend(parse_requirements_text(
            f.read_text(encoding="utf-8"), group=f.name))
    return reqs


def check_fail(report: DepReport, fail_on: str) -> bool:
    threshold = _SEV_ORDER[fail_on]
    return any(_SEV_ORDER[f.severity] <= threshold for f in report.findings)
