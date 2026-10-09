# -*- coding: utf-8 -*-
"""PII rule catalog: category → name regexes + comment keywords.

``name_patterns`` match with high confidence; ``weak_patterns`` are
deliberately loose (e.g. a bare ``name`` column) and only produce
low-confidence findings. Custom rules load from a YAML file and are
appended to the catalog — they never replace built-ins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class PiiRule:
    category: str
    severity: str = "medium"                 # high | medium | low (base)
    name_patterns: tuple[str, ...] = ()      # regex vs lower-cased column name
    weak_patterns: tuple[str, ...] = ()      # loose regex → low confidence
    comment_keywords: tuple[str, ...] = ()   # substring vs column comment
    builtin: bool = field(default=True, compare=False)

    def compiled(self) -> tuple[list[re.Pattern], list[re.Pattern]]:
        return ([re.compile(p) for p in self.name_patterns],
                [re.compile(p) for p in self.weak_patterns])


# Expression is considered masked when it calls one of these before landing
# downstream (hash/encrypt/redact families + lossy truncation). Reversible
# encodings (hex / base64 / translate) deliberately do NOT count — a
# decodable copy of the value is still a leak.
MASKING_FUNCS = frozenset({
    "md5", "sha", "sha1", "sha2", "sha256", "hash", "crc32", "murmur_hash",
    "mask", "mask_hash", "mask_first_n", "mask_last_n",
    "mask_show_first_n", "mask_show_last_n",
    "aes_encrypt", "encrypt",
    "regexp_replace", "overlay",
    "substr", "substring",
})

_MASK_RE = re.compile(
    r"\b(" + "|".join(sorted(MASKING_FUNCS)) + r")\s*\(", re.IGNORECASE)


def expression_is_masked(expression: str) -> bool:
    """True when the propagation expression applies a masking function."""
    return bool(expression) and bool(_MASK_RE.search(expression))


DEFAULT_RULES: tuple[PiiRule, ...] = (
    PiiRule(
        category="phone", severity="high",
        name_patterns=(r"(^|_)(mobile|phone|tel|telephone|msisdn)"
                       r"(_?(no|num|number))?(_|$)",),
        comment_keywords=("手机", "电话", "联系方式"),
    ),
    PiiRule(
        category="id_card", severity="high",
        name_patterns=(r"(^|_)(id_?card|idcard|identity|id_?no|cert_?no"
                       r"|citizen_?id)(_|$)",),
        comment_keywords=("身份证", "证件号", "证件号码"),
    ),
    PiiRule(
        category="bank_card", severity="high",
        name_patterns=(r"(^|_)(bank_?(card|acct|account)|card_?no"
                       r"|acct_?no|account_?no|iban)(_|$)",),
        comment_keywords=("银行卡", "卡号", "银行账号"),
    ),
    PiiRule(
        category="passport", severity="high",
        name_patterns=(r"passport",),
        comment_keywords=("护照",),
    ),
    PiiRule(
        category="email", severity="medium",
        name_patterns=(r"(^|_)e?mail(_?addr(ess)?)?(_|$)",),
        comment_keywords=("邮箱", "电子邮件"),
    ),
    PiiRule(
        category="person_name", severity="medium",
        name_patterns=(r"(^|_)((user|real|full|cust(omer)?|contact|legal)"
                       r"_?name)(_|$)",),
        weak_patterns=(r"(^|_)name(_|$)",),
        comment_keywords=("姓名", "联系人"),
    ),
    PiiRule(
        category="address", severity="medium",
        # (?<!ip_) keeps ip_addr / client_ip_address with the low-severity
        # ip_address rule instead of being inflated to a home address
        name_patterns=(r"(^|_)(?<!ip_)(addr|address|home_?addr(ess)?"
                       r"|ship(ping)?_?addr(ess)?)(_|$)",),
        comment_keywords=("地址", "住址"),
    ),
    PiiRule(
        category="salary", severity="medium",
        name_patterns=(r"(^|_)(salary|income|wage)(_|$)",),
        comment_keywords=("工资", "薪资", "薪酬", "收入"),
    ),
    PiiRule(
        category="birthday", severity="medium",
        name_patterns=(r"(^|_)(birth(day|date)?|date_?of_?birth|dob)(_|$)",),
        comment_keywords=("出生", "生日"),
    ),
    PiiRule(
        category="license_plate", severity="medium",
        name_patterns=(r"(^|_)(license_?plate|plate_?no|car_?no)(_|$)",),
        comment_keywords=("车牌",),
    ),
    PiiRule(
        category="ip_address", severity="low",
        name_patterns=(r"(^|_)(ip|ip_?addr(ess)?|client_?ip)(_|$)",),
        comment_keywords=("IP地址", "ip地址"),
    ),
)

_SEVERITIES = ("high", "medium", "low")
_SEV_RANK = {"low": 1, "medium": 2, "high": 3}


def match_column(name: str, comment: str,
                 rules: "Iterable[PiiRule]",
                 ) -> tuple[PiiRule, str, str, str] | None:
    """Best ``(rule, confidence, matched_by, evidence)`` for one column.

    Shared by the lineage scanner and sync_gen's masking injection —
    one source of truth for "does this column look like PII".
    """
    best: tuple[int, int, PiiRule, str, str, str] | None = None
    name = (name or "").lower()
    comment = comment or ""
    for rule in rules:
        strong, weak = rule.compiled()

        def _hit_text(patterns: list) -> str:
            for p in patterns:
                m = p.search(name)
                if m:
                    return m.group(0).strip("_") or name
            return ""

        matched_name = _hit_text(strong)
        matched_weak = "" if matched_name else _hit_text(weak)
        matched_kw = next(
            (k for k in rule.comment_keywords if k and k in comment), "")
        if not (matched_name or matched_weak or matched_kw):
            continue
        if matched_name and matched_kw:
            matched_by, evidence, conf = ("name+comment",
                                          f"{matched_name} + {matched_kw}",
                                          "high")
        elif matched_name:
            matched_by, evidence, conf = "name", matched_name, "high"
        elif matched_kw:
            matched_by, evidence, conf = "comment", matched_kw, "high"
        else:
            matched_by, evidence, conf = "name", matched_weak, "low"
        score = (_SEV_RANK[rule.severity], 1 if conf == "high" else 0)
        if best is None or score > (best[0], best[1]):
            best = (*score, rule, conf, matched_by, evidence)
    if best is None:
        return None
    return best[2], best[3], best[4], best[5]


def load_extra_rules(path: str | Path) -> list[PiiRule]:
    """Load custom rules from YAML: ``rules: [{category, severity,
    name_patterns, weak_patterns, comment_keywords}, ...]``.

    Raises ValueError with a readable message on any problem."""
    try:
        import yaml
    except ImportError:  # pragma: no cover - pyyaml ships with [uitest]
        raise ValueError("自定义规则需要 pyyaml: pip install pyyaml")
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"无法读取规则文件 {path}: {exc}")
    items = raw.get("rules") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError(f"{path}: 期望顶层为 rules: [...] 列表")
    rules: list[PiiRule] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict) or not item.get("category"):
            raise ValueError(f"{path}: 第 {i + 1} 条规则缺少 category")
        severity = str(item.get("severity", "medium")).lower()
        if severity not in _SEVERITIES:
            raise ValueError(
                f"{path}: 规则 {item['category']} severity 必须是 "
                f"{'/'.join(_SEVERITIES)}")
        patterns = tuple(str(p) for p in item.get("name_patterns") or ())
        weak = tuple(str(p) for p in item.get("weak_patterns") or ())
        keywords = tuple(str(k) for k in item.get("comment_keywords") or ())
        if not patterns and not weak and not keywords:
            raise ValueError(
                f"{path}: 规则 {item['category']} 至少需要一个 "
                "name_patterns / weak_patterns / comment_keywords")
        for p in patterns + weak:
            try:
                re.compile(p)
            except re.error as exc:
                raise ValueError(
                    f"{path}: 规则 {item['category']} 正则无效 {p!r}: {exc}")
        rules.append(PiiRule(
            category=str(item["category"]), severity=severity,
            name_patterns=patterns, weak_patterns=weak,
            comment_keywords=keywords, builtin=False))
    return rules
