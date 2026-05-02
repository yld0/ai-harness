"""Tool permission modes (Claw-code–inspired) and session checks."""

from __future__ import annotations

from enum import IntEnum
from typing import Literal

SessionPermissionT = Literal["ReadOnly", "ReadWrite"]


class PermissionMode(IntEnum):
    """Least privilege: ReadOnly < WorkspaceWrite < DangerFullAccess."""

    ReadOnly = 0
    WorkspaceWrite = 1
    DangerFullAccess = 2


def session_effective_mode(session: SessionPermissionT) -> PermissionMode:
    if session == "ReadOnly":
        return PermissionMode.ReadOnly
    return PermissionMode.WorkspaceWrite


def allows(mode: SessionPermissionT, required: PermissionMode) -> bool:
    """Return True if a session in `mode` is allowed to run a tool with `required` permission."""
    if required is PermissionMode.DangerFullAccess:
        return False
    eff = session_effective_mode(mode)
    return eff.value >= required.value


def parse_session(value: str | None) -> SessionPermissionT:
    if value is not None and str(value) == "ReadOnly":
        return "ReadOnly"
    return "ReadWrite"
