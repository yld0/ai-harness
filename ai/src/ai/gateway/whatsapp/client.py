"""Neonize WhatsApp session client.

Neonize is an *optional* dependency.  This module imports it lazily inside
``WhatsAppClient.start()`` so the harness can boot without the extra.

Install with:
    pip install ai[whatsapp]   # or: uv add neonize

Configuration (environment variables):
    WHATSAPP_DEVICE_NAME   — Display name shown to contacts (default "ai-harness").
    WHATSAPP_STORE_PATH    — Path to the neonize SQLite session store
                             (default "./wa_session.db").
    WHATSAPP_PAIR_PHONE    — Phone number for phone-pairing auth, e.g. "+447700900000".
                             If unset, QR code is used.
    HARNESS_URL            — Harness base URL for the HTTP forwarder.
    GATEWAY_JWT            — Bearer token for forwarded requests.

Security:
    The session store (``WHATSAPP_STORE_PATH``) contains long-lived credentials.
    Never commit it to version control.  Run this gateway as an isolated process
    with minimal filesystem permissions.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from ai.gateway.http_forwarder import HarnessForwarder
from ai.gateway.whatsapp.handlers import WhatsAppMessageHandler

if TYPE_CHECKING:  # pragma: no cover
    pass

logger = logging.getLogger(__name__)

_NEONIZE_MISSING = "neonize is not installed.  Install the optional extra: " "pip install 'ai[whatsapp]'  or  uv add neonize"


class WhatsAppClient:
    """Manages a neonize WhatsApp session and routes messages to the harness.

    Parameters
    ----------
    device_name:
        Friendly name shown to contacts (env: ``WHATSAPP_DEVICE_NAME``).
    store_path:
        SQLite file for the neonize session store (env: ``WHATSAPP_STORE_PATH``).
    pair_phone:
        Phone number for phone-pairing authentication (env: ``WHATSAPP_PAIR_PHONE``).
        Omit to use QR-code pairing instead.
    forwarder:
        Optional pre-built ``HarnessForwarder``; constructed from env vars if None.
    """

    def __init__(
        self,
        device_name: str | None = None,
        store_path: str | None = None,
        pair_phone: str | None = None,
        forwarder: HarnessForwarder | None = None,
    ) -> None:
        self.device_name = device_name or os.getenv("WHATSAPP_DEVICE_NAME", "ai-harness")
        self.store_path = store_path or os.getenv("WHATSAPP_STORE_PATH", "./wa_session.db")
        self.pair_phone = pair_phone or os.getenv("WHATSAPP_PAIR_PHONE") or None
        self.forwarder = forwarder or HarnessForwarder()
        self._handler = WhatsAppMessageHandler(self.forwarder)
        self._client = None  # set after neonize import in start()

    def start(self) -> None:
        """Start the neonize event loop (blocking).

        Raises ``ImportError`` with a helpful message if neonize is not installed.
        """
        try:
            import neonize  # noqa: F401 — optional dep
            from neonize.client import NewAClient
            from neonize.events import (
                ConnectedEv,
                MessageEv,
                PairStatusEv,
                QRChangedEv,
            )
        except ImportError as exc:
            raise ImportError(_NEONIZE_MISSING) from exc

        logger.info(
            "whatsapp: starting neonize client (device=%r store=%r)",
            self.device_name,
            self.store_path,
        )

        client = NewAClient(self.store_path)
        self._client = client

        @client.event(ConnectedEv)
        def _on_connected(_: ConnectedEv) -> None:
            logger.info("whatsapp: connected")

        @client.event(QRChangedEv)
        def _on_qr(ev: QRChangedEv) -> None:
            logger.info("whatsapp: QR code updated — scan with WhatsApp")

        @client.event(PairStatusEv)
        def _on_pair(ev: PairStatusEv) -> None:
            if ev.ID.User:
                logger.info("whatsapp: paired as %s", ev.ID.User)

        @client.event(MessageEv)
        def _on_message(ctx, ev: MessageEv) -> None:
            self._handler.handle(client, ev)

        if self.pair_phone:
            client.PairPhone(self.pair_phone, True)

        client.Connect()

    def disconnect(self) -> None:
        """Gracefully disconnect if a neonize client is active."""
        if self._client is not None:
            try:
                self._client.Disconnect()
            except Exception:  # noqa: BLE001
                pass
            self._client = None
