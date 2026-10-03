# -*- coding: utf-8 -*-
"""Secret detection rule catalog — provider token patterns, credential
assignments, and a high-entropy fallback.

Severity ladder: **high** = a concrete provider credential (works as-is if
real), **medium** = a generic credential assignment or embedded DSN
password, **low** = a high-entropy string that merely looks like a secret.
Placeholders (``${VAR}``, ``your-key-here``, ``changeme`` …) are filtered
before anything is reported.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretRule:
    id: str
    name_en: str
    name_zh: str
    severity: str          # high | medium | low
    pattern: re.Pattern


RULES: list[SecretRule] = [
    SecretRule("aws_access_key", "AWS access key ID", "AWS AccessKey",
               "high", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    # no capture group on purpose: provider-format rules skip the
    # placeholder filter (a 40-char base64 after secret_key is AWS-shaped
    # even when it contains the word EXAMPLE)
    SecretRule("aws_secret_key", "AWS secret access key", "AWS SecretKey",
               "high", re.compile(
                   r"(?i)(?:aws[_-]?)?secret[_-]?(?:access[_-]?)?key\s*"
                   r"[:=]\s*['\"][A-Za-z0-9/+=]{40}['\"]")),
    SecretRule("github_token", "GitHub token", "GitHub Token",
               "high", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,255}\b")),
    SecretRule("gitlab_pat", "GitLab personal access token", "GitLab PAT",
               "high", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b")),
    SecretRule("slack_token", "Slack token", "Slack Token",
               "high", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    SecretRule("aliyun_ak", "Aliyun AccessKey ID", "阿里云 AccessKey",
               "high", re.compile(r"\bLTAI[A-Za-z0-9]{12,24}\b")),
    SecretRule("private_key", "Private key block", "私钥块",
               "high", re.compile(
                   r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY")),
    SecretRule("jwt", "JSON Web Token", "JWT",
               "medium", re.compile(
                   r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."
                   r"[A-Za-z0-9_-]{5,}\b")),
    SecretRule("password_assign", "Password assignment", "明文密码赋值",
               "medium", re.compile(
                   r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*"
                   r"['\"]([^'\"\s]{6,})['\"]")),
    SecretRule("apikey_assign", "API key / token assignment", "API Key 赋值",
               "medium", re.compile(
                   r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|"
                   r"auth[_-]?token)\s*[:=]\s*"
                   r"['\"]([A-Za-z0-9_\-.]{16,})['\"]")),
    SecretRule("url_credentials", "Password embedded in URL/DSN",
               "URL/DSN 内嵌密码",
               "medium", re.compile(
                   r"\b[a-z][a-z0-9+.-]{1,20}://[^/\s:@'\"]{1,64}:"
                   r"([^@/\s'\"]{4,64})@")),
]

# applied only when no explicit rule matched the line
ENTROPY_RULE = SecretRule(
    "high_entropy", "High-entropy string", "高熵字符串", "low",
    re.compile(r"[:=]\s*['\"]([A-Za-z0-9/+_\-]{20,})['\"]"))

_ENTROPY_THRESHOLD = 4.0

# a value containing any of these is a placeholder, not a secret
_PLACEHOLDER_MARKERS = (
    "${", "{{", "<", "$(", "%s", "xxx", "***", "...",
    "your", "example", "changeme", "change_me", "dummy", "placeholder",
    "sample", "redacted", "insert", "fixme", "todo", "secret_here",
)


def is_placeholder(value: str) -> bool:
    v = (value or "").lower()
    return any(m in v for m in _PLACEHOLDER_MARKERS)


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    freq: dict[str, int] = {}
    for ch in value:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(value)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def entropy_hit(value: str) -> bool:
    """Looks random: long, mixed charset, entropy above threshold."""
    if len(value) < 20 or is_placeholder(value):
        return False
    classes = sum((any(c.islower() for c in value),
                   any(c.isupper() for c in value),
                   any(c.isdigit() for c in value)))
    return classes >= 2 and shannon_entropy(value) >= _ENTROPY_THRESHOLD
