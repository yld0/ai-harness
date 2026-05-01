"""Behavioural tests for the semantic_cached decorator."""

from __future__ import annotations

import logging
from typing import Any

import pytest

import ai.utils.caching.decorators as decorators_mod
from ai.utils.caching.decorators import semantic_cached


class FakeSemanticCache:
    """In-memory stand-in for redisvl's SemanticCache, with knobs for failure injection."""

    raise_on_init: bool = False
    raise_on_check: bool = False
    raise_on_store: bool = False

    def __init__(
        self,
        *,
        name: str,
        redis_url: str,
        distance_threshold: float,
        ttl: int | None,
    ) -> None:
        if FakeSemanticCache.raise_on_init:
            raise RuntimeError("simulated init failure")
        self.name = name
        self.redis_url = redis_url
        self.threshold = distance_threshold
        self.ttl = ttl
        self._store: dict[str, str] = {}

    def check(self, *, prompt: str) -> list[dict[str, Any]]:
        if FakeSemanticCache.raise_on_check:
            raise RuntimeError("simulated check failure")
        if prompt in self._store:
            return [{"response": self._store[prompt]}]
        return []

    def store(self, *, prompt: str, response: str) -> None:
        if FakeSemanticCache.raise_on_store:
            raise RuntimeError("simulated store failure")
        self._store[prompt] = response


_FAKE_REDIS_URL = "redis://test:6379/0"


@pytest.fixture(autouse=True)
def _patch_semantic_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub redisvl SemanticCache and reset per-process state between tests."""
    FakeSemanticCache.raise_on_init = False
    FakeSemanticCache.raise_on_check = False
    FakeSemanticCache.raise_on_store = False
    monkeypatch.setattr(decorators_mod, "SemanticCache", FakeSemanticCache)
    monkeypatch.setattr(decorators_mod.redis_config, "url", lambda: _FAKE_REDIS_URL)
    decorators_mod._get_cache.cache_clear()
    decorators_mod._DECLARED_SETTINGS.clear()


# 1. Cache miss → underlying called once → result stored.
async def test_cache_miss_calls_underlying_and_stores() -> None:
    calls: list[str] = []

    @semantic_cached(name="t1")
    async def fn(query: str) -> str:
        calls.append(query)
        return f"answer({query})"

    result = await fn(query="hello")

    assert result == "answer(hello)"
    assert calls == ["hello"]
    cache = decorators_mod._get_cache("t1", _FAKE_REDIS_URL, 0.1, None)
    assert cache._store == {"hello": "answer(hello)"}


# 2. Cache hit → underlying not called → cached value returned.
async def test_cache_hit_returns_cached_value() -> None:
    calls: list[str] = []

    @semantic_cached(name="t2")
    async def fn(query: str) -> str:
        calls.append(query)
        return f"answer({query})"

    await fn(query="hello")
    result = await fn(query="hello")

    assert result == "answer(hello)"
    assert calls == ["hello"]


# 3. Non-string return → underlying runs → nothing stored.
async def test_non_string_return_not_stored() -> None:
    @semantic_cached(name="t3")
    async def fn(query: str) -> Any:
        return {"data": query}

    result = await fn(query="hello")

    assert result == {"data": "hello"}
    cache = decorators_mod._get_cache("t3", _FAKE_REDIS_URL, 0.1, None)
    assert cache._store == {}


# 4. No prompt found → bypass cache.
async def test_no_prompt_bypasses_cache() -> None:
    @semantic_cached(name="t4")
    async def fn(other: int) -> str:
        return "x"

    result = await fn(other=1)

    assert result == "x"
    cache = decorators_mod._get_cache("t4", _FAKE_REDIS_URL, 0.1, None)
    assert cache._store == {}


# 5. cache_key_func overrides param introspection.
async def test_cache_key_func_overrides_introspection() -> None:
    @semantic_cached(name="t5", cache_key_func=lambda *a, **kw: f"key:{kw['x']}")
    async def fn(x: int, query: str = "ignored") -> str:
        return f"value-{x}"

    result1 = await fn(x=1, query="ignored")
    result2 = await fn(x=1, query="different")

    assert result1 == "value-1"
    assert result2 == "value-1"


# 6. SemanticCache construction raises → wrapper falls through; sticky for the process lifetime.
async def test_construction_failure_falls_through_and_sticks() -> None:
    FakeSemanticCache.raise_on_init = True

    @semantic_cached(name="t6")
    async def fn(query: str) -> str:
        return "ok"

    first = await fn(query="hi")
    assert first == "ok"

    # Even if Redis "comes back" mid-process, the memoised None keeps the cache disabled.
    FakeSemanticCache.raise_on_init = False
    second = await fn(query="hi")
    assert second == "ok"
    assert decorators_mod._get_cache("t6", _FAKE_REDIS_URL, 0.1, None) is None


# 7. .check() raises → bypass cache, no exception.
async def test_check_failure_swallowed() -> None:
    FakeSemanticCache.raise_on_check = True

    @semantic_cached(name="t7")
    async def fn(query: str) -> str:
        return "ok"

    result = await fn(query="hi")

    assert result == "ok"


# 8. .store() raises → result returned, no exception.
async def test_store_failure_swallowed() -> None:
    FakeSemanticCache.raise_on_store = True

    @semantic_cached(name="t8")
    async def fn(query: str) -> str:
        return "ok"

    result = await fn(query="hi")

    assert result == "ok"


# 9. threshold outside [0, 1] → ValueError at decoration.
def test_threshold_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match="threshold must be between"):
        semantic_cached(name="t9", threshold=1.5)


# 10. threshold > 0.2 → logger warning.
def test_threshold_above_soft_cap_warns(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="ai.utils.caching.decorators"):
        semantic_cached(name="t10", threshold=0.5)

    assert any("above recommended" in r.message for r in caplog.records)


# 11. Conflicting redeclaration → ValueError at decoration time.
def test_conflicting_redeclaration_raises() -> None:
    @semantic_cached(name="t11", threshold=0.05)
    async def _fn1(query: str) -> str:
        return "a"

    with pytest.raises(ValueError, match="already declared"):

        @semantic_cached(name="t11", threshold=0.15)
        async def _fn2(query: str) -> str:
            return "b"


# 12. Identical redeclaration → no raise; share the same cache instance.
async def test_identical_redeclaration_shares_cache() -> None:
    @semantic_cached(name="t12", threshold=0.1, ttl=None)
    async def fn1(query: str) -> str:
        return f"fn1:{query}"

    @semantic_cached(name="t12", threshold=0.1, ttl=None)
    async def fn2(query: str) -> str:
        return f"fn2:{query}"

    await fn1(query="hello")
    cache_a = decorators_mod._get_cache("t12", _FAKE_REDIS_URL, 0.1, None)
    await fn2(query="hello")
    cache_b = decorators_mod._get_cache("t12", _FAKE_REDIS_URL, 0.1, None)

    assert cache_a is cache_b
    # fn2 hits the cache populated by fn1.
    result = await fn2(query="hello")
    assert result == "fn1:hello"
