from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .config import MRouterConfig
from .errors import GatewayExecutionError, MRouterUnavailableError, RouteDecisionError
from .schemas.events import TelemetryEvent
from .schemas.route import ExecuteRequest, ExecuteResponse, RouteDecision, RouteRequest

SDK_VERSION = "0.1.0"


class RouterClient:
    def __init__(self, config: MRouterConfig):
        self.config = config

    def route(self, request: RouteRequest) -> RouteDecision:
        data = self._post("/v1/route", request.to_dict(), timeout_s=self.config.timeout_s)
        decision = RouteDecision.from_dict(data)
        if not decision.decision_id:
            raise RouteDecisionError("route response did not include decision_id")
        return decision

    async def aroute(self, request: RouteRequest) -> RouteDecision:
        import asyncio

        return await asyncio.to_thread(self.route, request)

    def execute(self, request: ExecuteRequest) -> ExecuteResponse:
        try:
            data = self._post("/v1/execute", request.to_dict(), timeout_s=None)
        except MRouterUnavailableError as exc:
            raise GatewayExecutionError(str(exc)) from exc
        return ExecuteResponse.from_dict(data)

    async def aexecute(self, request: ExecuteRequest) -> ExecuteResponse:
        import asyncio

        return await asyncio.to_thread(self.execute, request)

    def send_events(self, events: list[TelemetryEvent]) -> None:
        if not events:
            return
        self._post(
            "/v1/events",
            {"events": [event.to_dict() for event in events]},
            timeout_s=self.config.timeout_s,
        )

    async def asend_events(self, events: list[TelemetryEvent]) -> None:
        import asyncio

        await asyncio.to_thread(self.send_events, events)

    def tag_outcome(
        self,
        trajectory_id: str,
        success: bool,
        **kwargs: Any,
    ) -> None:
        payload = {"trajectory_id": trajectory_id, "success": success, **kwargs}
        self._post("/v1/outcomes", payload, timeout_s=self.config.timeout_s)

    def health(self) -> dict[str, Any]:
        try:
            return self._get("/v1/health", timeout_s=self.config.timeout_s)
        except MRouterUnavailableError as exc:
            if "404:" not in str(exc):
                raise
            return self._get("/healthz", timeout_s=self.config.timeout_s)

    def _url(self, path: str) -> str:
        return self.config.base_url.rstrip("/") + path

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"m-router-python/{SDK_VERSION}",
        }

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        timeout_s: float | None,
    ) -> dict[str, Any]:
        body = json.dumps(payload, default=str).encode("utf-8")
        request = urllib.request.Request(
            self._url(path),
            data=body,
            headers=self._headers(),
            method="POST",
        )
        return self._open_json(request, timeout_s)

    def _get(self, path: str, timeout_s: float | None) -> dict[str, Any]:
        request = urllib.request.Request(
            self._url(path),
            headers=self._headers(),
            method="GET",
        )
        return self._open_json(request, timeout_s)

    def _open_json(
        self,
        request: urllib.request.Request,
        timeout_s: float | None,
    ) -> dict[str, Any]:
        timeout = timeout_s if timeout_s is not None else self.config.timeout_s
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except (TimeoutError, OSError, urllib.error.URLError) as exc:
            raise MRouterUnavailableError(str(exc)) from exc
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MRouterUnavailableError(f"{exc.code}: {detail}") from exc

        if not raw:
            return {}
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MRouterUnavailableError("service returned invalid JSON") from exc
        if not isinstance(loaded, dict):
            raise MRouterUnavailableError("service returned a non-object JSON payload")
        return loaded
