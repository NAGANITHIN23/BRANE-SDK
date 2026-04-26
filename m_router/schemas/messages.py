from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimpleAIMessage:
    content: str
    response_metadata: dict[str, Any] = field(default_factory=dict)
    role: str = "assistant"
    type: str = "ai"
