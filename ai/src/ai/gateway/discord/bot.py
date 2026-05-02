"""
Discord gateway bot — stub implementation.

The full Discord integration (using ``discord.py``) is tracked in FUTURE.md.
This stub allows the module to be imported without errors and raises
``NotImplementedError`` at runtime so callers fail loudly rather than silently.

To implement:
    1. ``uv add 'discord.py>=2.3'`` (or add to ``[project.optional-dependencies]``).
    2. Replace this stub with a real ``discord.Client`` subclass.
    3. Wire ``DiscordBot`` → ``HarnessForwarder.forward()`` in the message handler.

Configuration (environment variables, once implemented):
    DISCORD_BOT_TOKEN   — Bot token from discord.com/developers.
    DISCORD_GUILD_ID    — Optional guild ID to restrict events.
    HARNESS_URL         — Harness base URL for the HTTP forwarder.
    GATEWAY_JWT         — Bearer token for forwarded requests.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

NOT_IMPLEMENTED_MSG = "Discord gateway is not yet implemented. " "See FUTURE.md for the planned discord.py-based integration."


class DiscordBot:
    """ Stub Discord bot — raises ``NotImplementedError`` on ``start()``. """

    def __init__(self, **kwargs) -> None:  # accept any kwargs for future compat
        logger.warning("DiscordBot: %s", NOT_IMPLEMENTED_MSG)

    def start(self) -> None:
        raise NotImplementedError(NOT_IMPLEMENTED_MSG)

    async def start_async(self) -> None:
        raise NotImplementedError(NOT_IMPLEMENTED_MSG)
