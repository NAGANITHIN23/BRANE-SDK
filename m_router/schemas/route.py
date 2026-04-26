from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RouteRequest:
    sdk_version: str
    mode: str
    app_name: str | None = None
    workflow_id: str | None = None
    trajectory_id: str | None = None
    node_name: str | None = None
    step_type: str | None = None
    agent_role: str | None = None
    step_index: int | None = None
    estimated_steps: int | None = None
    criticality: str | None = None
    difficulty: str | None = None
    input_tokens_estimate: int | None = None
    output_tokens_estimate: int | None = None
    schema_required: bool = False
    tools_required: bool = False
    available_models: list[str] = field(default_factory=list)
    default_model: str | None = None
    force_model: str | None = None
    allowed_models: list[str] | None = None
    blocked_models: list[str] | None = None
    prompt_fingerprint: str | None = None
    messages_preview: list[dict[str, Any]] | None = None
    messages: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class RouteDecision:
    decision_id: str
    selected_model: str | None = None
    fallback_model: str | None = None
    effective_threshold: float | None = None
    estimated_cost_usd: float | None = None
    estimated_default_cost_usd: float | None = None
    reason: str | None = None
    policy: dict[str, Any] = field(default_factory=dict)
    expires_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RouteDecision":
        return cls(
            decision_id=data.get("decision_id") or data.get("id") or "",
            selected_model=data.get("selected_model") or data.get("recommended_model"),
            fallback_model=data.get("fallback_model"),
            effective_threshold=data.get("effective_threshold"),
            estimated_cost_usd=data.get("estimated_cost_usd"),
            estimated_default_cost_usd=data.get("estimated_default_cost_usd"),
            reason=data.get("reason"),
            policy=data.get("policy") or {},
            expires_at=data.get("expires_at"),
            raw=dict(data),
        )


@dataclass
class LLMCall:
    input: Any
    config: dict[str, Any] | None
    kwargs: dict[str, Any]
    defaults: dict[str, Any]
    route_request: RouteRequest


@dataclass
class ExecuteRequest:
    route_request: RouteRequest
    messages: list[dict[str, Any]]
    model_params: dict[str, Any] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    response_schema: Any = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["route_request"] = self.route_request.to_dict()
        return data


@dataclass
class ExecuteResponse:
    decision_id: str
    selected_model: str | None
    message: dict[str, Any]
    usage: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecuteResponse":
        return cls(
            decision_id=data.get("decision_id") or "",
            selected_model=data.get("selected_model"),
            message=data.get("message") or {},
            usage=data.get("usage") or {},
            validation=data.get("validation") or {},
            reason=data.get("reason"),
            raw=dict(data),
        )
