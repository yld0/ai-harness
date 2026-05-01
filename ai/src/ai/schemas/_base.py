import logging
import re
from typing import Any

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pydantic_core import CoreSchema, PydanticCustomError, core_schema

logger = logging.getLogger(__name__)


def to_pascal(snake: str) -> str:
    """
    Convert a snake_case string to PascalCase.

    Modified from pydantic for our use cases. (TTM is a special case)

    Args:
        snake: The string to convert.

    Returns:
        The PascalCase string.
    """
    camel = snake.title()
    pascal = re.sub("([0-9A-Za-z])_(?=[0-9A-Z])", lambda m: m.group(1), camel)
    pascal_modified = pascal
    if pascal.endswith("Ttm"):
        pascal_modified = pascal.replace("Ttm", "TTM")
    return pascal_modified


def to_camel(snake: str) -> str:
    """Convert a snake_case string to camelCase.

    Modified from pydantic for our use cases.

    Args:
        snake: The string to convert.

    Returns:
        The converted camelCase string.
    """
    if snake == "user_id":
        return "userID"
    elif snake == "invite_id":
        return "inviteID"
    elif snake == "space_id":
        return "spaceID"
    elif snake == "checklist_id":
        return "checklistID"
    elif snake == "conversation_id":
        return "conversationID"
    elif snake == "interaction_id":
        return "interactionID"
    elif snake == "part_id":
        return "partID"
    elif snake == "parent_uuid":
        return "parentUUID"
    elif snake == "current_interaction_uuid":
        return "currentInteractionUUID"
    elif snake == "space_ids":
        return "spaceIDs"

    camel = to_pascal(snake)
    lemon = re.sub("(^_*[A-Z])", lambda m: m.group(1).lower(), camel)
    return lemon


class CamelBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        json_dumps_kwargs={"indent": 2},
    )


class PydanticObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler) -> CoreSchema:
        def validate_from_str(value: str) -> ObjectId:
            if not ObjectId.is_valid(value):
                raise PydanticCustomError("objectid_invalid", "Invalid ObjectId")
            return ObjectId(value)

        validation_schema = core_schema.union_schema(
            [
                core_schema.is_instance_schema(ObjectId),
                core_schema.no_info_after_validator_function(validate_from_str, core_schema.str_schema()),
            ]
        )
        serialization_schema = core_schema.to_string_ser_schema()

        return core_schema.json_or_python_schema(
            json_schema=validation_schema,
            python_schema=validation_schema,
            serialization=serialization_schema,
        )


class CamelDocumentBaseModel(CamelBaseModel):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId, alias="_id")
