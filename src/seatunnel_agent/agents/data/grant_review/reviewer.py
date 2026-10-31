"""Deterministic risk review of data-permission applications.

Input is one application (JSON object) or a batch (JSON list)::

    {"applicant": "zhang3", "role": "analyst",
     "purpose": "月度经营分析看板",
     "tables": [{"table": "dwd.users",
                 "columns": ["user_id", "phone", "city"]}],
     "duration_days": 30, "write": false}

Every application is scored transparently: the column names are graded
against a built-in sensitivity vocabulary (S3 direct identifiers and
money, S2 quasi-identifiers, S1 the rest — same idea as the pii_scan
word list), and risk accrues from sensitivity, whole-table wildcards,
write access, long durations, role/purpose mismatch and empty purposes.
The verdict is approve / downgrade (with the concrete downgrades) /
reject.  No database connection.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

__all__ = ["GrantReview", "ReviewResult", "parse_applications",
           "review_grants"]

# sensitivity vocabulary: level -> name patterns (CN pinyin + EN)
_S3 = re.compile(r"(phone|mobile|id_?card|idcard|identity|passport|bank|"
                 r"card_?no|salary|income|password|secret|token|身份证|手机|"
                 r"银行卡|工资|密码)", re.IGNORECASE)
_S2 = re.compile(r"(name|birth|age|gender|address|addr|city|email|ip|"
                 r"device|姓名|生日|地址|邮箱)", re.IGNORECASE)

_WRITE_ROLES = {"admin", "dba", "etl", "owner", "developer"}
_DECISIONS = (("reject", 70.0), ("downgrade", 40.0))


def _sensitivity(column: str) -> int:
    if _S3.search(column):
        return 3
    if _S2.search(column):
        return 2
    return 1


@dataclass
class GrantReview:
    applicant: str
    risk: float
    decision: str                      # approve / downgrade / reject
    reasons: list[str] = field(default_factory=list)
    s3_columns: list[str] = field(default_factory=list)
    s2_columns: list[str] = field(default_factory=list)
    downgrades: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"applicant": self.applicant, "risk": round(self.risk, 1),
                "decision": self.decision, "reasons": self.reasons,
                "s3_columns": self.s3_columns,
                "s2_columns": self.s2_columns,
                "downgrades": self.downgrades}


@dataclass
class ReviewResult:
    reviews: list[GrantReview]

    def to_dict(self) -> dict:
        return {"reviews": [r.to_dict() for r in self.reviews]}


def parse_applications(text: str) -> list[dict]:
    body = (text or "").strip()
    if not body:
        raise ValueError("empty application / 申请单为空")
    try:
        obj = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"application must be JSON: {exc}") from exc
    items = obj if isinstance(obj, list) else [obj]
    for i, it in enumerate(items, start=1):
        if not isinstance(it, dict) or not (it.get("applicant") or "").strip():
            raise ValueError(f"application {i}: needs 'applicant'")
        if not it.get("tables"):
            raise ValueError(f"application {i}: needs 'tables'")
    return items


def _review_one(app: dict) -> GrantReview:
    risk = 0.0
    reasons: list[str] = []
    downgrades: list[str] = []
    s3: list[str] = []
    s2: list[str] = []
    wildcard = False

    for entry in app.get("tables", ()):
        table = str(entry.get("table", "?"))
        columns = entry.get("columns") or []
        if not columns or "*" in columns:
            wildcard = True
            reasons.append(f"whole_table:{table}")
        for col in columns:
            lvl = _sensitivity(str(col))
            ref = f"{table}.{col}"
            if lvl == 3:
                s3.append(ref)
            elif lvl == 2:
                s2.append(ref)

    risk += 25.0 * min(len(s3), 2) + 5.0 * min(len(s2), 3)
    if s3:
        downgrades.append("mask_s3")
    if wildcard:
        risk += 20.0
        downgrades.append("narrow_columns")

    if bool(app.get("write")):
        role = str(app.get("role") or "").lower()
        if role in _WRITE_ROLES:
            risk += 10.0
            reasons.append("write_access")
        else:
            risk += 30.0
            reasons.append(f"write_for_role:{role or '?'}")
            downgrades.append("read_only")

    duration = int(app.get("duration_days") or 0)
    if duration <= 0 or duration > 180:
        risk += 15.0
        reasons.append(f"duration:{duration or 'permanent'}")
        downgrades.append("cap_90d")
    elif duration > 90:
        risk += 8.0
        reasons.append(f"duration:{duration}")
        downgrades.append("cap_90d")

    purpose = str(app.get("purpose") or "").strip()
    if len(purpose) < 8:
        risk += 15.0
        reasons.append("thin_purpose")
        downgrades.append("ask_purpose")

    if s3:
        reasons.insert(0, f"s3_columns:{len(s3)}")
    if s2:
        reasons.append(f"s2_columns:{len(s2)}")

    decision = "approve"
    for name, floor in _DECISIONS:
        if risk >= floor:
            decision = name
            break
    if decision == "approve":
        downgrades = []
    # dedupe downgrades, keep order
    seen: set[str] = set()
    downgrades = [d for d in downgrades
                  if not (d in seen or seen.add(d))]
    return GrantReview(applicant=str(app.get("applicant")), risk=min(risk, 100.0),
                       decision=decision, reasons=reasons,
                       s3_columns=s3[:6], s2_columns=s2[:6],
                       downgrades=downgrades)


def review_grants(apps: list[dict]) -> ReviewResult:
    reviews = [_review_one(a) for a in apps]
    reviews.sort(key=lambda r: (-r.risk, r.applicant))
    return ReviewResult(reviews=reviews)
