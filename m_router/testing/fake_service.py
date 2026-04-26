from __future__ import annotations

from typing import Any

from ..schemas.events import TelemetryEvent
from ..schemas.route import ExecuteRequest, ExecuteResponse, RouteDecision, RouteRequest


class FakeRouterService:
    def __init__(
        self,
        selected_model: str | None = None,
        fallback_model: str | None = None,
        unavailable: bool = False,
    ):
        self.selected_model = selected_model
        self.fallback_model = fallback_model
        self.unavailable = unavailable
        self.route_requests: list[RouteRequest] = []
        self.execute_requests: list[ExecuteRequest] = []
        self.events: list[TelemetryEvent] = []
        self.outcomes: list[dict[str, Any]] = []

    def route(self, request: RouteRequest) -> RouteDecision:
        if self.unavailable:
            raise RuntimeError("fake service unavailable")
        self.route_requests.append(request)
        selected = request.force_model or self.selected_model or request.default_model
        return RouteDecision(
            decision_id=f"dec_{len(self.route_requests)}",
            selected_model=selected,
            fallback_model=self.fallback_model,
            estimated_cost_usd=0.001,
            estimated_default_cost_usd=0.005,
            reason="test decision",
        )

    async def aroute(self, request: RouteRequest) -> RouteDecision:
        return self.route(request)

    def execute(self, request: ExecuteRequest) -> ExecuteResponse:
        self.execute_requests.append(request)
        return ExecuteResponse(
            decision_id=f"dec_exec_{len(self.execute_requests)}",
            selected_model=self.selected_model or "gateway:test",
            message={"role": "assistant", "content": "gateway response"},
            usage={"input_tokens": 5, "output_tokens": 7},
            validation={"status": "not_required"},
            reason="gateway test decision",
        )

    async def aexecute(self, request: ExecuteRequest) -> ExecuteResponse:
        return self.execute(request)

    def send_events(self, events: list[TelemetryEvent]) -> None:
        self.events.extend(events)

    async def asend_events(self, events: list[TelemetryEvent]) -> None:
        self.send_events(events)

    def tag_outcome(self, trajectory_id: str, success: bool, **kwargs: Any) -> None:
        self.outcomes.append({"trajectory_id": trajectory_id, "success": success, **kwargs})
