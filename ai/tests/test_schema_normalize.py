from ai.providers.schema_normalize import normalize_for_gemini, normalize_for_openai

SAMPLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "screen",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "ticker": {"type": "string", "enum": ["AAPL", 123]},
                    "filters": {
                        "additionalProperties": {"type": "string"},
                        "properties": {"country": {"enum": ["US", "GB"]}},
                    },
                },
            },
        },
    }
]


def test_gemini_normalization_strips_additional_properties_and_stringifies_enums() -> None:
    normalized = normalize_for_gemini(SAMPLE_TOOLS)
    params = normalized[0]["function"]["parameters"]

    assert "additionalProperties" not in params
    assert "additionalProperties" not in params["properties"]["filters"]
    assert params["properties"]["ticker"]["enum"] == ["AAPL", "123"]
    assert SAMPLE_TOOLS[0]["function"]["parameters"]["additionalProperties"] is False


def test_openai_normalization_preserves_root_object_shape() -> None:
    normalized = normalize_for_openai(
        [
            {
                "type": "function",
                "function": {
                    "name": "nested",
                    "parameters": {"properties": {"payload": {"properties": {"x": {"type": "string"}}}}},
                },
            }
        ]
    )

    params = normalized[0]["function"]["parameters"]
    assert params["type"] == "object"
    assert params["properties"]["payload"]["type"] == "object"


# ── FileComponent validator ────────────────────────────────────────────────────


def test_file_component_requires_content_or_ref_id() -> None:
    import pytest
    from pydantic import ValidationError
    from ai.schemas.agent import FileComponent

    # Both absent → validation error
    with pytest.raises(ValidationError, match="content or ref_id"):
        FileComponent(title="doc.pdf")

    # content present → OK
    fc = FileComponent(title="doc.pdf", content="base64==")
    assert fc.content == "base64=="

    # ref_id present → OK
    fc2 = FileComponent(title="doc.pdf", ref_id="file-abc")
    assert fc2.ref_id == "file-abc"
