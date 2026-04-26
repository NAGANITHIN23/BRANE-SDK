from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

RouterMode = Literal["shadow", "decision", "gateway"]
Redactor = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


@dataclass(slots=True)
class MRouterConfig:
    api_key: str
    mode: RouterMode = "decision"
    app_name: str | None = None
    base_url: str = "https://api.m-router.ai"
    timeout_s: float = 2.0
    fail_open: bool = True
    send_prompts: bool = False
    send_message_preview: bool = False
    max_local_retries: int = 1
    redactor: Redactor | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"shadow", "decision", "gateway"}:
            raise ValueError("mode must be one of: shadow, decision, gateway")
        if self.mode == "gateway":
            self.send_prompts = True
