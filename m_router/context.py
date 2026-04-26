from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator


@dataclass
class RoutingContext:
    workflow_id: str | None = None
    trajectory_id: str | None = None
    node_name: str | None = None
    step_type: str | None = None
    agent_role: str | None = None
    step_index: int | None = None
    estimated_steps: int | None = None
    criticality: str | None = None
    difficulty: str | None = None
    force_model: str | None = None
    allowed_models: list[str] | None = None
    blocked_models: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


current_context: ContextVar[RoutingContext | None] = ContextVar(
    "m_router_current_context",
    default=None,
)


def merge_context(
    parent: RoutingContext | None,
    child: RoutingContext | None,
) -> RoutingContext:
    if parent is None and child is None:
        return RoutingContext()
    if parent is None:
        return child or RoutingContext()
    if child is None:
        return parent

    merged = parent.to_dict()
    metadata = dict(parent.metadata)
    metadata.update(child.metadata)
    for key, value in child.to_dict().items():
        if key != "metadata":
            merged[key] = value
    merged["metadata"] = metadata
    return RoutingContext(**merged)


@contextmanager
def routing_context(**metadata: Any) -> Iterator[RoutingContext]:
    parent = current_context.get()
    child = RoutingContext(**metadata)
    merged = merge_context(parent, child)
    token = current_context.set(merged)
    try:
        yield merged
    finally:
        current_context.reset(token)
