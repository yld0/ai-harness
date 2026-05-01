"""Slash command base classes, CommandResult, and process-local registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class CommandResult:
    """Return value of a command handler.

    *text*        — user-visible response (Markdown OK).
    *side_effects* — opaque dict for the runner to act on (e.g. personality change,
                     hook trigger).  Keys recognised by runner:
                       ``"personality"``   → set session personality name
                       ``"trigger_hook"``  → run named hook (compact / auto_dream)
    *dispatched*  — always True for matched commands; False signals pass-through.
    *error*       — set when the command failed soft; still has a user-facing *text*.
    """

    text: str
    side_effects: dict[str, Any] = field(default_factory=dict)
    dispatched: bool = True
    error: str | None = None


class CommandHandler(ABC):
    """Abstract base for a slash command handler.

    Subclasses must set ``name`` as a class-level ``ClassVar[str]``.
    ``aliases`` is an optional tuple of additional trigger names.
    """

    name: ClassVar[str]
    aliases: ClassVar[tuple[str, ...]] = ()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

    @abstractmethod
    async def handle(self, args: list[str], *, context: dict[str, Any]) -> CommandResult:
        """Execute the command.

        Must never raise — return a ``CommandResult`` with ``error`` set instead.

        *context* is a dict provided by the runner; typical keys:
            ``"repo_root"``       — Path to the project root
            ``"workspace_root"``  — optional Path to workspace root
            ``"user_id"``         — user identifier string
            ``"request"``         — raw AgentChatRequestV3
        """


# --------------------------------------------------------------------------- #
# Process-local registry                                                        #
# --------------------------------------------------------------------------- #

_REGISTRY: dict[str, "CommandHandler"] = {}


class CommandRegistrationError(RuntimeError):
    """Raised when two handlers claim the same name or alias."""


def register(handler: "CommandHandler", *, replace: bool = False) -> "CommandHandler":
    """Add *handler* to the registry under its (lowercased) name and aliases.

    Raises ``CommandRegistrationError`` on a name/alias collision unless
    ``replace=True`` (useful for tests or hot-reload).
    """
    keys = [handler.name.lower()] + [str(a).lower() for a in handler.aliases]
    if not replace:
        for key in keys:
            existing = _REGISTRY.get(key)
            if existing is not None and existing is not handler:
                raise CommandRegistrationError(
                    f"Command key {key!r} already registered to " f"{type(existing).__name__}; cannot register {type(handler).__name__}"
                )
    for key in keys:
        _REGISTRY[key] = handler
    return handler


def unregister(handler: "CommandHandler") -> None:
    """Remove *handler* from the registry (name + aliases).  Safe if absent."""
    keys = [handler.name.lower()] + [str(a).lower() for a in handler.aliases]
    for key in keys:
        if _REGISTRY.get(key) is handler:
            _REGISTRY.pop(key, None)


def get_handler(name: str) -> "CommandHandler | None":
    """Look up a handler by command name (case-insensitive)."""
    return _REGISTRY.get(name.lower())


def all_handlers() -> dict[str, "CommandHandler"]:
    """Snapshot of the current registry."""
    return dict(_REGISTRY)


def register_builtins(*, replace: bool = False) -> None:
    """Register the built-in slash command handlers.

    Called explicitly (e.g. from :class:`ai.agent.runner.AgentRunner`) instead
    of relying on package-import side effects.  Imports are local to break the
    ``base ↔ handler`` import cycle — see AGENTS.md "Refrain from import inside
    functions" (cycle-breaking is the documented exception).
    """
    from ai.commands.compact import CompactCommand
    from ai.commands.dream import DreamCommand
    from ai.commands.personality import PersonalityCommand
    from ai.commands.skills import SkillCommand

    for handler in (
        CompactCommand(),
        DreamCommand(),
        PersonalityCommand(),
        SkillCommand(),
    ):
        register(handler, replace=replace)
