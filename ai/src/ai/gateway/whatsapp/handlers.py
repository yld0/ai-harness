"""WhatsApp inbound message → harness request mapper.

Extracts sender JID + text from a neonize ``MessageEv``, calls the
``HarnessForwarder``, and replies on the same WhatsApp thread.

Design:
- One ``WhatsAppMessageHandler`` per ``WhatsAppClient``.
- Message routing is synchronous (neonize callback) but delegates to
  ``asyncio.run()`` for the async forwarder.  This is acceptable for a
  separate gateway process; do NOT use inside the main FastAPI event loop.
- Ignores: own messages, non-text messages (group/media/status).
- Error reply: sends a user-visible error message so the conversation doesn't
  silently hang.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any, Optional

from ai.gateway.http_forwarder import HarnessForwarder, RateLimitError

if TYPE_CHECKING:  # pragma: no cover
    pass

logger = logging.getLogger(__name__)

_MAX_TEXT_LEN = int(os.getenv("GATEWAY_MAX_TEXT_LEN", "4000"))
_ERROR_REPLY = "Sorry, I encountered an error. Please try again."
_RATE_LIMIT_REPLY = "You're sending messages too quickly. Please wait a moment."


def _extract_text(message_ev: Any) -> Optional[str]:
    """Extract plain text from a neonize MessageEv; return None for non-text."""
    try:
        msg = message_ev.Message.Message
        if msg is None:
            return None
        # Try conversation (plain DM text)
        text = getattr(msg, "Conversation", None) or ""
        if not text:
            # Try extended text message
            ext = getattr(msg, "ExtendedTextMessage", None)
            text = (getattr(ext, "Text", None) or "") if ext else ""
        return text.strip() or None
    except Exception:  # noqa: BLE001
        return None


def _sender_jid(message_ev: Any) -> str:
    """Return a stable sender identifier from MessageEv."""
    try:
        return str(message_ev.Info.MessageSource.Sender)
    except Exception:  # noqa: BLE001
        return "unknown"


def _conversation_id(message_ev: Any) -> str:
    """Return a conversation/chat JID string."""
    try:
        return str(message_ev.Info.MessageSource.Chat)
    except Exception:  # noqa: BLE001
        return "unknown"


def _is_own_message(message_ev: Any) -> bool:
    try:
        return bool(message_ev.Info.MessageSource.IsFromMe)
    except Exception:  # noqa: BLE001
        return False


class WhatsAppMessageHandler:
    """Handles inbound WhatsApp messages and dispatches to the harness."""

    def __init__(self, forwarder: HarnessForwarder | None = None) -> None:
        self.forwarder = forwarder or HarnessForwarder()

    def handle(self, client: Any, message_ev: Any) -> None:
        """Process one inbound MessageEv (called from neonize callback thread)."""
        if _is_own_message(message_ev):
            return

        text = _extract_text(message_ev)
        if text is None:
            logger.debug("whatsapp: ignoring non-text message")
            return

        text = text[:_MAX_TEXT_LEN]
        sender = _sender_jid(message_ev)
        conv_id = _conversation_id(message_ev)

        logger.debug("whatsapp: message from %s: %s", sender, text[:80])

        try:
            reply_text = asyncio.run(
                self.forwarder.forward(
                    text,
                    user_id=sender,
                    conversation_id=conv_id,
                    channel="whatsapp",
                )
            )
        except RateLimitError:
            reply_text = _RATE_LIMIT_REPLY
        except Exception as exc:  # noqa: BLE001
            logger.exception("whatsapp: forwarder error for %s", sender)
            reply_text = _ERROR_REPLY

        if reply_text:
            self._send_reply(client, message_ev, reply_text)

    def _send_reply(self, client: Any, message_ev: Any, text: str) -> None:
        """Best-effort reply; logs and swallows errors."""
        try:
            from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import (  # type: ignore[import]
                Message,
                ExtendedTextMessage,
            )

            chat = message_ev.Info.MessageSource.Chat
            reply_msg = Message(extendedTextMessage=ExtendedTextMessage(text=text))
            client.SendMessage(chat, reply_msg)
        except ImportError:
            logger.warning("whatsapp: neonize not available, reply dropped")
        except Exception as exc:  # noqa: BLE001
            logger.warning("whatsapp: failed to send reply to %s: %s", _sender_jid(message_ev), exc)
