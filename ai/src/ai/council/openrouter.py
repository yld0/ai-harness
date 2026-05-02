"""Shared OpenRouter transport for council model calls."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import httpx

from ai.api.send import send_ws_task_update
from ai.config import council_config
from ai.schemas.agent import TaskItemUpdate, TaskUpdateMessage
from ai.usage.capture import capture

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120.0


@dataclass(frozen=True)
class CouncilModelResponse:
    """Normalised response from one council model."""

    content: str
    reasoning_details: object | None = None


async def query_model(
    model: str,
    messages: list[dict[str, str]],
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    task: TaskUpdateMessage | None = None,
    api_key: str | None = None,
    api_url: str | None = None,
) -> CouncilModelResponse | None:
    """Query one OpenRouter model and return normalised assistant content."""
    key = api_key or council_config.OPENROUTER_API_KEY
    url = api_url or council_config.OPENROUTER_API_URL
    if not key:
        logger.warning(f"OPENROUTER_API_KEY not set, council model {model} skipped")
        return None

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={"model": model, "messages": messages},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            message = data["choices"][0]["message"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning(f"Error querying model {model}: {exc}")
        if task:
            task.items.append(TaskItemUpdate(type="item", content=f"{model} failed to respond: {exc}"))
            await send_ws_task_update(task)
        return None

    await capture(data)
    if task:
        task.items.append(TaskItemUpdate(type="item", content=f"{model} responded"))
        await send_ws_task_update(task)

    logger.info(f"OpenRouter response: {data} {type(data)}")
    return CouncilModelResponse(
        content=message.get("content") or "",
        reasoning_details=message.get("reasoning_details"),
    )


async def query_models_parallel(
    models: Sequence[str],
    messages: list[dict[str, str]],
    *,
    task: TaskUpdateMessage | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> dict[str, CouncilModelResponse | None]:
    """Query multiple OpenRouter models concurrently."""
    responses = await asyncio.gather(
        *[query_model(model, messages, task=task, timeout=timeout) for model in models],
        return_exceptions=False,
    )
    return dict(zip(models, responses))


def response_texts(responses: Mapping[str, CouncilModelResponse | None]) -> dict[str, str | None]:
    """Extract content strings from model responses."""
    return {model: response.content if response is not None else None for model, response in responses.items()}
