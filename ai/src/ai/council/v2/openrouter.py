"""OpenRouter API client for council LLM requests."""

import logging
from typing import Any, Dict, List, Optional

import httpx

from ai.usage.capture import capture
from ai.config import council_config
from ai.schemas.agent import TaskUpdateMessage, TaskItemUpdate
from ai.api.send import send_ws_partial, send_ws_task_update

logger = logging.getLogger(__name__)


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    task: Optional[TaskUpdateMessage] = None,
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
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

            return {
                "content": message.get("content"),
                "reasoning_details": message.get("reasoning_details"),
            }

    except Exception as e:  # noqa: BLE001
        logger.warning("Error querying model %s: %s", model, e)
        if task:
            task.items.append(TaskItemUpdate(type="item", content=f"{model} failed to respond: {e}"))
            await send_ws_task_update(task)
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    task: Optional[TaskUpdateMessage] = None,
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    tasks = [query_model(model, messages, task=task) for model in models]
    responses = await asyncio.gather(*tasks)
    return {model: response for model, response in zip(models, responses)}
