# """ One-shot script to embed spinner verbs into MongoDB for vector search.

# Embeds each verb (with its category context) via the OpenRouter embeddings
# endpoint, and upserts into the configured MongoDB collection.  Re-running
# is idempotent (upserts by verb key).

# Usage::

#     python -m ai.utils.seed_spinner_verbs
# """

# from __future__ import annotations

# import asyncio
# import logging
# import os
# from collections import defaultdict
# from datetime import datetime, timezone
# from typing import Any

# import httpx
# from motor.motor_asyncio import AsyncIOMotorClient

# from ai.config import agent_config, mongo_config
# from ai.const import SPINNER_VERBS
# from ai.mongo.utils import ensure_vector_index

# logger = logging.getLogger(__name__)

# _EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"

# # Context-tagged verb categories.  Each key is a space-separated set of
# # domain keywords; the values are the verbs that best match that domain.
# _VERB_CATEGORIES: dict[str, list[str]] = {
#     "financial analysis valuation earnings computation numbers data models dcf crunching": [
#         "Calculating", "Computing", "Crunching", "Quantumizing",
#         "Synthesizing", "Deliberating", "Wrangling",
#     ],
#     "research reading synthesis discovery knowledge papers learning study": [
#         "Spelunking", "Pondering", "Ruminating", "Elucidating",
#         "Deliberating", "Deciphering", "Inferring",
#     ],
#     "planning architecting designing structure system workflow blueprint": [
#         "Architecting", "Orchestrating", "Forging", "Crafting",
#         "Wrangling", "Crystallizing", "Coalescing",
#     ],
#     "writing composing drafting generating content creation narrative": [
#         "Composing", "Crafting", "Generating", "Synthesizing",
#         "Manifesting", "Germinating",
#     ],
#     "memory recall context loading fetching retrieving knowledge base": [
#         "Recombobulating", "Reticulating", "Percolating",
#         "Harmonizing", "Coalescing", "Bootstrapping",
#     ],
#     "hooks compacting summarising condensing collapsing cleanup": [
#         "Simmering", "Crystallizing", "Composing",
#         "Synthesizing", "Mulling",
#     ],
#     "general thinking reasoning processing pondering": [
#         "Cogitating", "Musing", "Mulling", "Philosophising",
#         "Noodling", "Waffling", "Pondering", "Cerebrating",
#     ],
# }


# def _build_verb_context_map() -> dict[str, list[str]]:
#     """ Invert ``_VERB_CATEGORIES`` to ``{verb: [category_keywords, ...]}``. """
#     verb_map: dict[str, list[str]] = defaultdict(list)
#     for category_keywords, verbs in _VERB_CATEGORIES.items():
#         for verb in verbs:
#             verb_map[verb].append(category_keywords)
#     return dict(verb_map)


# async def embed_texts(texts: list[str]) -> list[list[float]]:
#     """ Batch-embed *texts* via the OpenRouter embeddings endpoint. """
#     api_key = agent_config.OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY", "")
#     if not api_key:
#         raise RuntimeError("OPENROUTER_API_KEY is required for seeding")

#     async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
#         response = await client.post(
#             _EMBEDDINGS_URL,
#             headers={
#                 "Authorization": f"Bearer {api_key}",
#                 "Content-Type": "application/json",
#             },
#             json={
#                 "model": agent_config.EMBEDDING_MODEL,
#                 "input": texts,
#             },
#         )
#         response.raise_for_status()
#         data: dict[str, Any] = response.json()

#     # OpenAI format: data is a list of {index, embedding} objects.
#     items = sorted(data["data"], key=lambda d: d["index"])
#     return [item["embedding"] for item in items]


# async def seed() -> None:
#     """ Embed all spinner verbs and upsert into MongoDB. """
#     verb_context_map = _build_verb_context_map()

#     # Build embedding texts.
#     embedding_texts: list[str] = []
#     verb_docs: list[dict[str, Any]] = []
#     now = datetime.now(timezone.utc)

#     for verb in SPINNER_VERBS:
#         categories = verb_context_map.get(verb, [])
#         context = " ".join(categories) if categories else "general"
#         embedding_text = f"{verb}: {context}"
#         embedding_texts.append(embedding_text)
#         verb_docs.append(
#             {
#                 "verb": verb,
#                 "context": context,
#                 "categories": categories,
#                 "embedding_text": embedding_text,
#                 "created_at": now,
#                 "updated_at": now,
#             }
#         )

#     logger.info("Embedding %d verbs via %s …", len(embedding_texts), agent_config.EMBEDDING_MODEL)
#     embeddings = await embed_texts(embedding_texts)
#     dims = len(embeddings[0])
#     logger.info("Embedding dimension: %d", dims)

#     for doc, emb in zip(verb_docs, embeddings):
#         doc["embedding"] = emb

#     # Upsert into MongoDB.
#     motor_client: AsyncIOMotorClient = AsyncIOMotorClient(
#         mongo_config.MONGO_URL,
#         mongo_config.MONGO_PORT,
#         uuidRepresentation="standard",
#     )
#     collection = motor_client[mongo_config.MONGO_DB][agent_config.SPINNER_VERBS_COLLECTION]

#     for doc in verb_docs:
#         await collection.update_one(
#             {"verb": doc["verb"]},
#             {"$set": doc},
#             upsert=True,
#         )

#     count = await collection.count_documents({})
#     logger.info("Upserted %d documents into %s.%s", count, mongo_config.MONGO_DB, agent_config.SPINNER_VERBS_COLLECTION)

#     await ensure_vector_index(collection, default_embedding_dimension=dims)
#     logger.info("Vector index ensured (dims=%d). Done.", dims)

#     motor_client.close()


# def main() -> None:
#     """ Entry point for ``python -m ai.utils.seed_spinner_verbs``. """
#     logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
#     asyncio.run(seed())


# if __name__ == "__main__":
#     main()
