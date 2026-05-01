"""Gateway package is a stub; optional WhatsApp stack must not require neonize at import."""

from __future__ import annotations

import importlib


def test_gateway_import_does_not_require_neonize() -> None:
    import ai.gateway as gateway

    assert gateway.__doc__


def test_neonize_is_not_loaded_after_gateway_import() -> None:
    import sys

    importlib.import_module("ai.gateway")
    assert "neonize" not in sys.modules
