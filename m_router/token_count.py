from __future__ import annotations

import hashlib
import json
from typing import Any


def normalize_messages(input_value: Any) -> list[dict[str, Any]]:
    if isinstance(input_value, str):
        return [{"role": "user", "content": input_value}]
    if isinstance(input_value, dict):
        return [input_value]
    if isinstance(input_value, list):
        return [_message_to_dict(item) for item in input_value]
    return [_message_to_dict(input_value)]


def _message_to_dict(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        return dict(message)
    role = getattr(message, "role", None) or getattr(message, "type", None) or "user"
    content = getattr(message, "content", message)
    return {"role": role, "content": content}


def estimate_tokens(input_value: Any) -> int:
    messages = normalize_messages(input_value)
    text = json.dumps(messages, sort_keys=True, default=str)
    return max(1, len(text) // 4)


def prompt_fingerprint(input_value: Any) -> str:
    messages = normalize_messages(input_value)
    payload = json.dumps(messages, sort_keys=True, default=str).encode("utf-8")
    return "pf_" + hashlib.sha256(payload).hexdigest()[:24]
