"""Provider-specific tool schema cleanup."""

from copy import deepcopy
from typing import Any


def normalize_for_gemini(openai_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tools = deepcopy(openai_tools)
    for tool in tools:
        function = tool.get("function", tool)
        parameters = function.get("parameters")
        if isinstance(parameters, dict):
            _strip_additional_properties(parameters)
            _normalize_enums(parameters)
    return tools


def normalize_for_openai(openai_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tools = deepcopy(openai_tools)
    for tool in tools:
        function = tool.get("function", tool)
        parameters = function.get("parameters")
        if isinstance(parameters, dict):
            _ensure_object_roots(parameters)
    return tools


def _strip_additional_properties(schema: dict[str, Any]) -> None:
    schema.pop("additionalProperties", None)
    for key in ("properties", "$defs", "definitions"):
        nested = schema.get(key)
        if isinstance(nested, dict):
            for value in nested.values():
                if isinstance(value, dict):
                    _strip_additional_properties(value)
    for key in ("items", "anyOf", "oneOf", "allOf"):
        value = schema.get(key)
        if isinstance(value, dict):
            _strip_additional_properties(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _strip_additional_properties(item)


def _normalize_enums(schema: dict[str, Any]) -> None:
    enum = schema.get("enum")
    if isinstance(enum, list):
        schema["enum"] = [str(item) for item in enum]
    for value in schema.values():
        if isinstance(value, dict):
            _normalize_enums(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _normalize_enums(item)


def _ensure_object_roots(schema: dict[str, Any]) -> None:
    schema.setdefault("type", "object")
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for value in properties.values():
            if isinstance(value, dict):
                _ensure_nested_types(value)


def _ensure_nested_types(schema: dict[str, Any]) -> None:
    if "properties" in schema and "type" not in schema:
        schema["type"] = "object"
    for value in schema.values():
        if isinstance(value, dict):
            _ensure_nested_types(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _ensure_nested_types(item)
