"""Lightweight prompt-injection scan for memory before prompt insertion."""

import re

THREAT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"ignore\s+(previous|all|above|prior)\s+instructions", re.I),
        "prompt_injection",
    ),
    (re.compile(r"you\s+are\s+now\s+", re.I), "role_hijack"),
    (re.compile(r"system\s+prompt\s+override", re.I), "system_override"),
    (
        re.compile(r"curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET)", re.I),
        "secret_exfiltration",
    ),
    (re.compile(r"authorized_keys", re.I), "ssh_backdoor"),
    (re.compile(r"[\u200b-\u200f\u202a-\u202e]"), "invisible_unicode"),
)


class MemoryThreatError(ValueError):
    pass


def scan_memory_text(text: str, *, source: str = "memory") -> None:
    for pattern, code in THREAT_PATTERNS:
        if pattern.search(text):
            raise MemoryThreatError(f"{source} failed memory threat scan: {code}")


def safe_memory_text(text: str, *, source: str = "memory") -> str:
    scan_memory_text(text, source=source)
    return text
