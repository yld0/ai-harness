"""Semantic LLM output caching via RedisVL."""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, TypeVar

from redisvl.extensions.cache.llm import SemanticCache

from ai.config import redis_config

F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)

# Parameter names we look for, in priority order, when no cache_key_func
# is supplied — both as kwargs and as positional args.
_PROMPT_PARAM_NAMES: tuple[str, ...] = ("query", "prompt", "text", "input", "message")

# Decoration-time settings claimed for each cache `name`. Re-declarations
# with the same name MUST match these settings or `_claim_name` raises.
_DECLARED_SETTINGS: dict[str, tuple[float, int | None, str | None]] = {}


def _claim_name(
    name: str,
    *,
    threshold: float,
    ttl: int | None,
    redis_url: str | None,
) -> None:
    """Reserve a cache `name` with its settings; raise on conflict.

    Two ``@semantic_cached`` decorations sharing the same ``name`` MUST agree on
    ``(threshold, ttl, redis_url)``. The check fires at decoration time (module
    import) so mismatches surface loudly and order-independently rather than
    silently sharing the first-registered settings at first call.
    """
    settings = (threshold, ttl, redis_url)
    existing = _DECLARED_SETTINGS.get(name)
    if existing is not None and existing != settings:
        raise ValueError(
            f"semantic_cached name={name!r} already declared with settings "
            f"(threshold, ttl, redis_url)={existing}; got {settings}. "
            "Use a distinct name or align the settings."
        )
    _DECLARED_SETTINGS[name] = settings


@functools.cache
def _get_cache(
    name: str,
    redis_url: str,
    threshold: float,
    ttl: int | None,
) -> SemanticCache | None:
    """Lazily build (and memoise) a SemanticCache for `name`.

    On construction failure, logs and returns ``None``. The ``None`` is itself
    memoised, so a single boot-time Redis outage disables this ``name``'s
    cache for the process lifetime — restart the process to retry.
    """
    try:
        return SemanticCache(
            name=name,
            redis_url=redis_url,
            distance_threshold=threshold,
            ttl=ttl,
        )
    except Exception as e:
        logger.error("Failed to init SemanticCache for %r: %s", name, e)
        return None


def semantic_cached(
    name: str | None = None,
    threshold: float = 0.1,
    ttl: int | None = None,
    redis_url: str | None = None,
    cache_key_func: Callable[..., str] | None = None,
) -> Callable[[F], F]:
    """
    A decorator that provides semantic caching using RedisVL.
    
    Args:
        name: The name/index prefix for the cache in Redis.
            If not provided, uses the decorated function's name.
        threshold: Semantic distance threshold (0.0 = exact, 0.2 = loose).
            Must be between 0.0 and 1.0.
        ttl: Time to live in seconds (optional).
        redis_url: Connection string for Redis.
            If not provided, constructs from redis_config.
        cache_key_func: Optional function that receives function arguments (*args, **kwargs)
            and returns the cache key.
    
    Returns:
        Decorator function that wraps the target function with semantic caching.
    
    Raises:
        ValueError: If threshold is not between 0.0 and 1.0.
    """

    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"threshold must be between 0.0 and 1.0, got {threshold}")
    if threshold > 0.2:
        logger.warning(
            "threshold %s is above recommended 0.0-0.2; higher values may return less relevant hits",
            threshold,
        )

    def decorator(func: F) -> F:
        cache_name = name if name is not None else func.__name__
        _claim_name(cache_name, threshold=threshold, ttl=ttl, redis_url=redis_url)

        prompt_param: str | None = None
        prompt_index: int | None = None
        try:
            param_names = list(inspect.signature(func).parameters.keys())
            for pname in _PROMPT_PARAM_NAMES:
                if pname in param_names:
                    prompt_param = pname
                    prompt_index = param_names.index(pname)
                    break
        except (TypeError, ValueError) as e:
            logger.debug("signature introspection failed for %s: %s", func.__name__, e)

        def _resolve_prompt(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
            if cache_key_func is not None:
                value = cache_key_func(*args, **kwargs)
                return value if isinstance(value, str) and value else None
            if prompt_param is None:
                return None
            if prompt_param in kwargs:
                value = kwargs[prompt_param]
            elif prompt_index is not None and prompt_index < len(args):
                value = args[prompt_index]
            else:
                return None
            return value if isinstance(value, str) and value else None

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Resolve redis_url lazily so test/env overrides applied after
            # import time still take effect at first cache materialisation.
            effective_redis_url = redis_url if redis_url is not None else redis_config.url()
            llm_cache = _get_cache(cache_name, effective_redis_url, threshold, ttl)
            if llm_cache is None:
                return await func(*args, **kwargs)

            prompt_text = _resolve_prompt(args, kwargs)
            if prompt_text is None:
                return await func(*args, **kwargs)

            try:
                cached_results = llm_cache.check(prompt=prompt_text)
                if isinstance(cached_results, list) and cached_results:
                    hit = cached_results[0]
                    if isinstance(hit, dict) and "response" in hit:
                        return hit["response"]
            except Exception as e:
                logger.warning("Cache check failed for %s: %s", func.__name__, e)

            result = await func(*args, **kwargs)
            if isinstance(result, str):
                try:
                    llm_cache.store(prompt=prompt_text, response=result)
                except Exception as e:
                    logger.warning("Cache store failed for %s: %s", func.__name__, e)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
