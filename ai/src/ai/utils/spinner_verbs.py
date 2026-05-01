""" Async, vector-based spinner verb selector.

Replaces the old ``qmd``-based lookup with OpenRouter embeddings and
MongoDB Atlas ``$vectorSearch``.  A ``@semantic_cached`` layer on Redis
short-circuits repeated / similar queries so that the embedding +
vector-search round-trip is only paid for genuinely novel contexts.
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
import re
from typing import Any

import httpx
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from shared.timing.utils import async_timer

from ai.config import agent_config, mongo_config
from ai.const import SPINNER_VERBS, _SPINNER_VERBS_SET
from ai.mongo.utils import vector_search
from ai.utils.caching.decorators import semantic_cached

logger = logging.getLogger(__name__)

# OpenRouter embeddings endpoint (OpenAI-compatible).
_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"

# Lazy singletons — created on first use.
_motor_client: AsyncIOMotorClient | None = None
_http_client: httpx.AsyncClient | None = None


def _truncate_query(context: str) -> str:
    """ Extract the first sentence from *context* for embedding.

    Splits on period or newline, takes the first non-empty segment, and
    strips whitespace.
    """
    parts = re.split(r"[.\n]", context, maxsplit=1)
    first = parts[0].strip() if parts else context.strip()
    return first or context.strip()


# def _get_collection() -> AsyncIOMotorCollection:
#     """ Return the spinner-verbs MongoDB collection (lazy singleton). """
#     global _motor_client  # noqa: PLW0603
#     if _motor_client is None:
#         _motor_client = AsyncIOMotorClient(
#             mongo_config.MONGO_URL,
#             mongo_config.MONGO_PORT,
#             uuidRepresentation="standard",
#         )
#     return _motor_client[mongo_config.MONGO_DB][agent_config.SPINNER_VERBS_COLLECTION]


# def _get_http_client() -> httpx.AsyncClient:
#     """ Return a shared ``httpx.AsyncClient`` (lazy singleton). """
#     global _http_client  # noqa: PLW0603
#     if _http_client is None:
#         _http_client = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0))
#     return _http_client


# async def _embed_query(text: str) -> list[float]:
#     """ Embed *text* via the OpenRouter embeddings endpoint. """
#     api_key = agent_config.OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY", "")
#     client = _get_http_client()
#     response = await client.post(
#         _EMBEDDINGS_URL,
#         headers={
#             "Authorization": f"Bearer {api_key}",
#             "Content-Type": "application/json",
#         },
#         json={
#             "model": agent_config.EMBEDDING_MODEL,
#             "input": [text],
#         },
#     )
#     response.raise_for_status()
#     data: dict[str, Any] = response.json()
#     return data["data"][0]["embedding"]


# def _cache_key(context: str | None = None) -> str | None:
#     """ Extract the cache key for ``@semantic_cached``. """
#     return context if context else None


# @async_timer(logger, threshold=0.5, only_log_slow=True)
# @semantic_cached(
#     name="spinner_verb",
#     threshold=0.1,
#     ttl=86400,
#     cache_key_func=_cache_key,
# )
# async def choose_spinner_verb(context: str | None = None) -> str:
#     """ Return a short spinner label ending with ``…``.

#     When *context* is provided, embeds it via OpenRouter and runs a
#     ``$vectorSearch`` against a MongoDB collection of pre-embedded verbs.
#     Falls back to a random pick on any failure.
#     """
#     if not context:
#         return f"{random.choice(SPINNER_VERBS)}…"

#     try:
#         truncated = _truncate_query(context)
#         embedding = await _embed_query(truncated)
#         collection = _get_collection()
#         results = await vector_search(embedding, collection, n_results=1)
#         if results:
#             doc, _score = results[0]
#             verb = doc.get("verb")

#             if verb:
#                 return f"{verb}…"
#             else:
#                 logger.warning("Spinner verb document has no verb field. Falling back to random.")
#                 return f"{random.choice(SPINNER_VERBS)}…"
#     except Exception:
#         logger.warning("Spinner verb vector lookup failed; falling back to random", exc_info=True)
#         return f"{random.choice(SPINNER_VERBS)}…"


# Keyword buckets: (keyword_prefixes, verb_pool).
# Every entry in ``SPINNER_VERBS`` appears in at least one pool (union equals the full list).
# Prefix length of 6 covers most stems without a stemmer
# (e.g. "financ" matches "finance", "financial", "financing").
_VERB_BUCKETS: list[tuple[frozenset[str], list[str]]] = [
    # 1. Math & Calculation
    (
        frozenset(
            {
                "math", "calcul", "crunch", "number", "quant", "metric", "comput",
                "equati", "formul", "statis",
            },
        ),
        ["Calculating", "Computing", "Crunching", "Quantumizing"],
    ),
    # 2. Finance Core
    (
        frozenset(
            {
                "financ", "earn", "valuat", "market", "dcf", "wealth", "family", "tax",
                "invest", "portfo", "trade", "tradin", "fund", "asset", "equiti",
                "divide", "yield", "profit", "margin", "revenu", "instit",
            },
        ),
        ["Allocating", "Concentrating", "Deliberating"],
    ),
    # 3. Finance Alpha & Moat
    (
        frozenset(
            {
                "alpha", "beta", "benchm", "outper", "flywhe", "moat", "moatin",
                "pitch", "pitchi", "swing", "buffet",
            },
        ),
        ["Alphaing", "Betaing", "FatPitching", "Flywheeling", "Moating"],
    ),
    # 4. Finance Hedging & Risk
    (
        frozenset(
            {
                "hedge", "hedgin", "mitiga", "fattai", "tail", "tailri", "privat",
                "credit", "alloca", "harves", "churn",
            },
        ),
        ["FatTailing", "Harvesting", "Hedging", "Mitigating", "Churning"],
    ),
    # 5. Research & Information Gathering
    (
        frozenset(
            {
                "resear", "paper", "study", "read", "source", "ref", "gather",
                "collec", "search", "explor", "find", "hunt", "scour",
            },
        ),
        ["Spelunking", "Deciphering"],
    ),
    # 6. Thinking & Deep Reasoning
    (
        frozenset(
            {
                "think", "ponder", "muse", "cogita", "contem", "philos", "pontif",
                "cerebr", "noodle", "waffle", "puzzle", "infer", "reason", "wonder",
                "analyz", "analys", "assess", "evalua", "logic", "deduce", "deduct",
            },
        ),
        [
            "Pondering", "Ruminating", "Inferring", "Elucidating", "Cogitating",
            "Contemplating", "Cerebrating", "Philosophising", "Pontificating",
            "Puzzling", "Musing", "Noodling", "Waffling",
        ],
    ),
    # 7. Architecture & System Design
    (
        frozenset(
            {
                "archit", "design", "system", "bluepr", "workfl", "struct", "model",
                "schema", "infras", "topolo", "patter", "framew",
            },
        ),
        ["Architecting", "Orchestrating"],
    ),
    # 8. Ideation & Creation
    (
        frozenset(
            {
                "plan", "ideati", "imagin", "hatchi", "sprout", "metamo", "transm",
                "evolve", "create", "invent", "brains", "vision", "origin", "spark",
            },
        ),
        [
            "Forging", "Crystallizing", "Coalescing", "Crafting", "Ideating",
            "Imagining", "Hatching", "Sprouting", "Metamorphosing", "Transmuting",
        ],
    ),
    # 9. Writing & Drafting
    (
        frozenset(
            {
                "write", "draft", "compos", "genera", "conten", "narrat", "report",
                "author", "scribe", "pen", "pennin", "docume", "blog", "post", "essay",
                "articl", "prose",
            },
        ),
        ["Composing", "Generating", "Synthesizing", "Manifesting", "Crafting", "Germinating"],
    ),
    # 10. Memory & Context
    (
        frozenset(
            {
                "memory", "recall", "fetch", "load", "retrie", "contex", "knowle", "base",
                "embed", "vector", "index", "storag", "databa", "cache", "cachi",
            },
        ),
        ["Recombobulating", "Reticulating", "Percolating", "Harmonizing", "Bootstrapping"],
    ),
    # 11. Summarization & Condensation
    (
        frozenset(
            {
                "hook", "compac", "conden", "collap", "cleanu", "summar", "trim",
                "prune", "short", "abridg", "digest", "minify", "reduce", "squash",
            },
        ),
        ["Simmering", "Crystallizing", "Synthesizing", "Mulling", "Coalescing"],
    ),
    # 12. Coding & Implementation
    (
        frozenset(
            {
                "code", "codin", "implem", "build", "script", "progra", "softwa", "app",
                "applic", "dev", "develo", "api", "interf", "librar", "packag", "module",
            },
        ),
        ["Forging", "Processing", "Bootstrapping"],
    ),
    # 13. Debugging & Testing
    (
        frozenset(
            {
                "debug", "test", "fix", "refact", "deploy", "patch", "error", "bug",
                "issue", "crash", "except", "failur", "resolv", "troubl", "diagno",
                "lint", "profil",
            },
        ),
        ["Wrangling", "Finagling", "Whirring"],
    ),
    # 14. Cooking Metaphors
    (
        frozenset(
            {
                "baking", "brewin", "fermen", "marina", "stew", "stewin", "concoc",
                "recipe", "simmer", "cook", "cookin", "chef", "flavor", "spice",
                "spicin", "roast", "roasti",
            },
        ),
        ["Baking", "Brewing", "Fermenting", "Marinating", "Stewing", "Concocting"],
    ),
    # 15. Playful & Chaotic
    (
        frozenset(
            {
                "buffet", "playfu", "roamin", "wander", "vibe", "vibing", "silly",
                "chaoti", "galliv", "scampe", "canood", "discom", "bamboo", "shenan",
                "goof", "goofin", "prank", "quirk",
            },
        ),
        ["Buffeting", "Canoodling", "Discombobulating", "Gallivanting", "Scampering", "Vibing"],
    ),
    # 16. Data & Parsing
    (
        frozenset(
            {
                "data", "format", "parse", "parsin", "transf", "conver", "mappin",
                "map", "filter", "sort", "sortin", "clean", "munge", "munger", "mungin",
                "scrape", "scrapin", "extrac", "loadin", "etl", "pipeli",
            },
        ),
        ["Mungering", "Wrangling"],
    ),
]


def choose_spinner_verb_bucket(context: str | None = None) -> str:
    """ Return a spinner label deterministically from keyword-matched buckets.

    Hashes the first 40 characters of *context* so the same context always
    produces the same verb (no network calls, no I/O).  Falls back to a
    deterministic pick across the full ``SPINNER_VERBS`` list when no bucket
    matches.
    """
    if not context:
        return f"{random.choice(SPINNER_VERBS)}…"

    # Better tokenization: alphanumeric words only, avoiding punctuation edge cases.
    words = {w[:6] for w in re.findall(r"[a-z0-9]+", context.lower())}
    key = context[:40].encode()
    idx = int(hashlib.md5(key, usedforsecurity=False).hexdigest(), 16)

    for prefixes, pool in _VERB_BUCKETS:
        if prefixes & words:
            return f"{pool[idx % len(pool)]}…"

    return f"{SPINNER_VERBS[idx % len(SPINNER_VERBS)]}…"
