"""MongoDB vector search utilities."""

from __future__ import annotations

import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.errors import OperationFailure
from pymongo.operations import SearchIndexModel

logger = logging.getLogger(__name__)


async def ensure_vector_index(
    collection: AsyncIOMotorCollection,
    default_embedding_dimension: int = 384,
    index_name: str = "vector_index",
) -> None:
    """Create a MongoDB Atlas vector search index on the *embedding* field."""

    async def _create() -> None:
        search_index_model = SearchIndexModel(
            definition={
                "fields": [
                    {
                        "type": "vector",
                        "numDimensions": default_embedding_dimension,
                        "path": "embedding",
                        "similarity": "cosine",
                    }
                ]
            },
            name=index_name,
            type="vectorSearch",
        )
        await collection.create_search_index(model=search_index_model)

    try:
        await _create()
    except OperationFailure as exc:
        logger.warning("Vector index creation skipped or failed: %s", exc)


async def vector_search(
    embedding_vector: list[float],
    collection: AsyncIOMotorCollection,
    n_results: int = 1,
    index_name: str = "vector_index",
    oversampling_factor: int = 10,
    extra_pipeline: list[dict[str, Any]] | None = None,
) -> list[tuple[dict[str, Any], float]]:
    """Run ``$vectorSearch`` and return ``(document, score)`` tuples."""

    pipeline: list[dict[str, Any]] = [
        {
            "$vectorSearch": {
                "index": index_name,
                "limit": n_results,
                "numCandidates": n_results * oversampling_factor,
                "queryVector": embedding_vector,
                "path": "embedding",
            }
        },
        {"$set": {"score": {"$meta": "vectorSearchScore"}}},
    ]

    if extra_pipeline:
        pipeline.extend(extra_pipeline)

    pipeline.append({"$project": {"embedding": 0}})

    agg = await collection.aggregate(pipeline).to_list(length=None)
    return [(doc, doc.pop("score")) for doc in agg]
