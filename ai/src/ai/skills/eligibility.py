"""Runtime eligibility from YAML frontmatter (OpenClaw-style)."""

from __future__ import annotations

import os
import shutil
import sys
from typing import Any

_PLATFORM_ALIASES: dict[str, str] = {
    "darwin": "darwin",
    "macos": "darwin",
    "linux": "linux",
    "linux2": "linux",
    "win32": "win32",
    "windows": "win32",
}


def _current_platform_tag() -> str:
    plat = sys.platform.lower()
    if plat.startswith("linux"):
        return "linux"
    if plat == "win32" or plat == "cygwin":
        return "win32"
    if plat == "darwin":
        return "darwin"
    return plat


def _as_str_list(value: Any) -> list[str]:
    if value is None or value is False:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]
    return [str(value)]


def _requires_block(fm: dict[str, Any]) -> dict[str, Any]:
    r = fm.get("requires")
    if isinstance(r, dict):
        return r
    return {}


def skill_requires_write(fm: dict[str, Any]) -> bool:
    if fm.get("requires_write") is True:
        return True
    tools = fm.get("tools")
    if isinstance(tools, str):
        return tools.strip() == "WorkspaceWrite"
    if isinstance(tools, (list, tuple)):
        return "WorkspaceWrite" in {str(t) for t in tools}
    return False


def passes_permission(fm: dict[str, Any], permission: str) -> bool:
    if skill_requires_write(fm) and permission == "ReadOnly":
        return False
    return True


def is_eligible(
    fm: dict[str, Any],
    *,
    permission: str = "ReadWrite",
    config: dict[str, Any] | None = None,
) -> bool:
    if fm.get("enabled") is False:
        return False
    if not passes_permission(fm, permission):
        return False
    if fm.get("always") is True:
        return True

    cfg = config or {}

    os_list = _as_str_list(fm.get("os"))
    if os_list:
        want = {_PLATFORM_ALIASES.get(s.lower().strip(), s.lower().strip()) for s in os_list}
        cur = _current_platform_tag()
        if cur not in want:
            return False

    req = _requires_block(fm)
    for key in ("bin", "bins"):
        for binary in _as_str_list(fm.get(key) or req.get(key)):
            if not shutil.which(binary):
                return False
    for binary in _as_str_list(req.get("anyBins") or req.get("any_bins") or fm.get("anyBins")):
        if not shutil.which(binary):
            return False
    for env_name in _as_str_list(fm.get("env") or req.get("env")):
        if not os.environ.get(env_name) and not cfg.get("env", {}).get(env_name):
            return False
    for path in _as_str_list(req.get("config") or fm.get("config")):
        if not _is_truthy_config(path, cfg):
            return False
    return True


def _is_truthy_config(dotted: str, cfg: dict[str, Any]) -> bool:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return bool(cur)
