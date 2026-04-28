from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Literal

from .errors import MRouterConfigurationError

RouterMode = Literal["shadow", "decision", "gateway"]
Redactor = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


@dataclass(slots=True)
class MRouterConfig:
    api_key: str | None = None
    mode: RouterMode = "decision"
    app_name: str | None = None
    base_url: str = "https://api.membranelabs.org"
    timeout_s: float = 2.0
    fail_open: bool = True
    send_prompts: bool = False
    send_message_preview: bool = False
    max_local_retries: int = 1
    redactor: Redactor | None = None

    def __post_init__(self) -> None:
        if self.api_key is None:
            self.api_key = os.getenv("BRANE_API_KEY")
        if not self.api_key:
            raise MRouterConfigurationError("BRANE_API_KEY is required when api_key is not provided.")
        if self.mode not in {"shadow", "decision", "gateway"}:
            raise ValueError("mode must be one of: shadow, decision, gateway")
        if self.mode == "gateway":
            self.send_prompts = True
