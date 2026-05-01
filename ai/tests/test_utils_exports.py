"""Public `ai.utils` exports (no dependency on references/ai-master)."""


def test_utils_web_and_caching_exports() -> None:
    from ai.utils.caching.decorators import semantic_cached
    from ai.utils.web.description import get_description
    from ai.utils.web.redirect import resolve_final_url

    assert callable(semantic_cached)
    assert callable(get_description)
    assert callable(resolve_final_url)
