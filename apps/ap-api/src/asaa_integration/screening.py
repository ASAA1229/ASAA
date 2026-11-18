"""Payload screening for ecosystem events: credential-looking keys and values, nesting depth and non-finite numbers.

Keys are normalised (NFKC, zero-width and other format characters removed, camelCase and separators split) before matching, so
`pass​word`, `API-Key`, `accessToken` and `client_secret` are all caught. String values are scanned for credential shapes
(JWT, Bearer, sk-, ghp_, AKIA, URL userinfo, private key blocks). Findings contain only a sanitised path and a kind, never a value.
Homoglyph look-alikes from other scripts are not folded; the value scan is the second line of defence.
"""
from __future__ import annotations

import math
import re
import unicodedata

MAX_DEPTH = 12

# Long, distinctive words: matched anywhere in the joined, separator-free key.
_LONG_DENY = ("password", "passwd", "passphrase", "secret", "apikey", "accesskey", "privatekey", "signingkey", "credential",
              "authorization", "bearer", "cookie", "sessionid", "sessiontoken", "token", "jwt", "otpcode", "recoverycode")
# Short words: matched only as whole segments (so "author" or "pinned" are not flagged).
_SHORT_DENY = {"auth", "jwt", "ssn", "otp", "totp", "pwd", "pin", "cvv", "sid", "mfa", "passcode"}
# Usage counters that merely contain the word token.
_ALLOWED_JOINED = {"prompttokens", "completiontokens", "inputtokens", "outputtokens", "totaltokens", "cachedtokens",
                   "tokensused", "tokenscount", "tokenstotal"}

_VALUE_PATTERNS = [
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")),
    ("sk-key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("aws-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("url-userinfo", re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in folded if unicodedata.category(ch) not in {"Cf", "Cc", "Mn"} or ch in "\t\n\r ")


def segments(key: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", normalize(key))
    return [part.lower() for part in re.split(r"[^A-Za-z0-9]+", spaced) if part]


def key_is_secret_like(key: str) -> bool:
    parts = segments(str(key))
    joined = "".join(parts)
    if joined in _ALLOWED_JOINED:
        return False
    if _SHORT_DENY & set(parts):
        return True
    return any(word in joined for word in _LONG_DENY)


def _safe_path(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\[\]-]", "?", path)[:80]


def screen(value, path: str = "data") -> list[str]:
    """Findings such as 'data.nested.apiKey: key' or 'data.note: bearer'. Iterative, bounded by MAX_DEPTH + 1 levels."""
    findings: list[str] = []
    stack = [(value, path, 0)]
    while stack and len(findings) < 20:
        item, where, depth = stack.pop()
        if depth > MAX_DEPTH + 1:
            findings.append(f"{_safe_path(where)}: nesting")
            continue
        if isinstance(item, dict):
            for key, child in item.items():
                child_path = f"{where}.{key}"
                if key_is_secret_like(key):
                    findings.append(f"{_safe_path(child_path)}: key")
                stack.append((child, child_path, depth + 1))
        elif isinstance(item, list):
            stack.extend((child, f"{where}[{index}]", depth + 1) for index, child in enumerate(item))
        elif isinstance(item, str):
            text = normalize(item)
            for kind, pattern in _VALUE_PATTERNS:
                if pattern.search(text):
                    findings.append(f"{_safe_path(where)}: {kind}")
                    break
    return findings[:20]


def depth_of(value) -> int:
    """Maximum nesting depth, computed iteratively (no recursion)."""
    deepest, stack = 0, [(value, 1)]
    while stack:
        item, depth = stack.pop()
        deepest = max(deepest, depth)
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return deepest


def has_non_finite(value) -> bool:
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, float) and not math.isfinite(item):
            return True
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return False
