"""Live utils.web port (no references/ai-master path)."""

from __future__ import annotations

from ai.utils.web.description import get_description
from ai.utils.web.redirect import resolve_final_url


def test_utils_web_exports() -> None:
    assert callable(get_description)
    assert callable(resolve_final_url)
