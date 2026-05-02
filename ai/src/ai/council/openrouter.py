""" Shared OpenRouter transport for council model calls. """

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

DEFAULT_TIMEOUT = 120.0


@dataclass(frozen=True)
class CouncilModelResponse:
    """ Normalised response from one council model. """
    content: str
    reasoning_details: object | None = None


async def query_model(
    model: str,
    messages: list[dict[str, str]],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    task: TaskUpdateMessage | None = None,
) -> CouncilModelResponse | None:
    """ Query one OpenRouter model and return normalised assistant content. 
    Args:
        model: OpenRouter model identifier
        messages: List of message dicts to send to the model
        timeout: Timeout in seconds
        task: TaskUpdateMessage to update the task with progress
    Returns:
        CouncilModelResponse or None if failed
    """
    
    api_key = council_config.OPENROUTER_API_KEY
    api_url = council_config.OPENROUTER_API_URL

    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set, council will fail")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]

            await capture(data)

            if task:
                task.items.append(TaskItemUpdate(type="item", content=f"{model} responded"))
                await send_ws_task_update(task)

            logger.info(f"OpenRouter response: {data} {type(data)}")

            return CouncilModelResponse(
                content=message.get("content", ""),
                reasoning_details=message.get("reasoning_details"),
            )

    except Exception as e:
        logger.warning("Error querying model %s: %s", model, e)
        if task:
            task.items.append(TaskItemUpdate(type="item", content=f"{model} failed to respond: {e}"))
            await send_ws_task_update(task)
        return None


async def query_models_parallel(
    models: Sequence[str], messages: list[dict[str, str]], *, task: TaskUpdateMessage | None = None, timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, CouncilModelResponse | None]:
    """
    Query multiple OpenRouter models in parallel. 
    
    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model
    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio
    tasks = [query_model(model, messages, task=task, timeout=timeout) for model in models]
    responses = await asyncio.gather(*tasks)
    return {model: response for model, response in zip(models, responses)}


def response_texts(responses: Mapping[str, CouncilModelResponse | None]) -> dict[str, str | None]:
    """ Extract content strings from model responses. 
    Args:
        responses: Dict mapping model identifier to response dict (or None if failed)
    Returns:
        Dict mapping model identifier to content string (or None if failed)
    """
    return {model: response.content if response is not None else None for model, response in responses.items()}

