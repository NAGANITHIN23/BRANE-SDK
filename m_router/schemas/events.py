from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TelemetryEvent:
    event_type: str
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex}")
    timestamp: str = field(default_factory=utc_now_iso)
    decision_id: str | None = None
    trajectory_id: str | None = None
    workflow_id: str | None = None
    node_name: str | None = None
    actual_model: str | None = None
    recommended_model: str | None = None
    selected_model: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    validation_status: str | None = None
    error: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}
