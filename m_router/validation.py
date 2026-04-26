from __future__ import annotations

import json
from typing import Any

from .errors import SchemaValidationError


def validate_response(response: Any, response_schema: Any | None) -> Any:
    if response_schema is None:
        return response

    content = getattr(response, "content", response)
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise SchemaValidationError("response content is not valid JSON") from exc
    else:
        parsed = content

    if hasattr(response_schema, "model_validate"):
        return response_schema.model_validate(parsed)
    if hasattr(response_schema, "parse_obj"):
        return response_schema.parse_obj(parsed)
    if isinstance(response_schema, dict):
        _validate_json_schema_subset(parsed, response_schema)
        return parsed
    if callable(response_schema):
        return response_schema(parsed)
    return parsed


def _validate_json_schema_subset(value: Any, schema: dict[str, Any]) -> None:
    required = schema.get("required", [])
    if required:
        if not isinstance(value, dict):
            raise SchemaValidationError("schema requires an object response")
        missing = [field for field in required if field not in value]
        if missing:
            raise SchemaValidationError(f"response missing required fields: {missing}")
