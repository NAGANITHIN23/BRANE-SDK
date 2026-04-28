from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from .client import SDK_VERSION, RouterClient
from .config import MRouterConfig
from .context import RoutingContext, current_context, merge_context
from .decorators import node_decorator
from .errors import ModelNotRegisteredError, MRouterUnavailableError
from .providers.gateway_provider import GatewayExecutor
from .providers.langchain_provider import LocalProviderExecutor
from .schemas.events import TelemetryEvent
from .schemas.messages import SimpleAIMessage
from .schemas.route import LLMCall, RouteDecision, RouteRequest
from .telemetry import TelemetryBuffer
from .token_count import estimate_tokens, normalize_messages, prompt_fingerprint
from .validation import validate_response


class MRouter:
    def __init__(
        self,
        api_key: str | None = None,
        mode: str = "decision",
        app_name: str | None = None,
        models: dict[str, object] | None = None,
        default_model: str | object | None = None,
        base_url: str = "https://api.membranelabs.org",
        timeout_s: float = 2.0,
        fail_open: bool = True,
        send_prompts: bool = False,
        send_message_preview: bool = False,
        redactor: Any = None,
        max_local_retries: int = 1,
        client: object | None = None,
    ):
        self.config = MRouterConfig(
            api_key=api_key,
            mode=mode,  # type: ignore[arg-type]
            app_name=app_name,
            base_url=base_url,
            timeout_s=timeout_s,
            fail_open=fail_open,
            send_prompts=send_prompts,
            send_message_preview=send_message_preview,
            redactor=redactor,
            max_local_retries=max_local_retries,
        )
        self.models: dict[str, object] = dict(models or {})
        self.default_model_id = self._register_default_model(default_model)
        self.client = client or RouterClient(self.config)
        self.telemetry = TelemetryBuffer(self.client)
        self.local_executor = LocalProviderExecutor(self.models)
        self.gateway_executor = GatewayExecutor(self.client)
        self._trajectory_counters: dict[str, int] = {}

    def chat_model(self, **defaults: Any) -> "MRouterChatModel":
        return MRouterChatModel(self, **defaults)

    def node(self, **metadata: Any):
        return node_decorator(self, **metadata)

    @contextmanager
    def context(self, **metadata: Any) -> Iterator[RoutingContext]:
        parent = current_context.get()
        child = RoutingContext(**metadata)
        merged = merge_context(parent, child)
        token = current_context.set(merged)
        try:
            yield merged
        finally:
            current_context.reset(token)

    def invoke(
        self,
        messages: Any,
        context: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if context:
            with self.context(**context):
                return self.chat_model().invoke(messages, config=config, **kwargs)
        return self.chat_model().invoke(messages, config=config, **kwargs)

    async def ainvoke(
        self,
        messages: Any,
        context: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if context:
            with self.context(**context):
                return await self.chat_model().ainvoke(messages, config=config, **kwargs)
        return await self.chat_model().ainvoke(messages, config=config, **kwargs)

    def tag(self, trajectory_id: str, success: bool, **kwargs: Any) -> None:
        self.telemetry.add(
            TelemetryEvent(
                event_type="outcome_tagged",
                trajectory_id=trajectory_id,
                metadata={"success": success, **kwargs},
            )
        )
        try:
            self.client.tag_outcome(trajectory_id=trajectory_id, success=success, **kwargs)
        except Exception:
            if not self.config.fail_open:
                raise

    def register_model(self, model_id: str, model: object | None = None, **metadata: Any) -> None:
        if model is not None:
            self.models[model_id] = model
            self.local_executor = LocalProviderExecutor(self.models)
        if metadata:
            self.telemetry.add(
                TelemetryEvent(
                    event_type="model_registered",
                    actual_model=model_id,
                    metadata=metadata,
                )
            )

    def build_call(
        self,
        input: Any,
        config: dict[str, Any] | None,
        kwargs: dict[str, Any],
        defaults: dict[str, Any],
    ) -> LLMCall:
        merged_kwargs = {**defaults, **kwargs}
        context = self._merged_runtime_context(config)
        self._ensure_trajectory_and_step(context)
        messages = normalize_messages(input)
        route_request = RouteRequest(
            sdk_version=SDK_VERSION,
            mode=self.config.mode,
            app_name=self.config.app_name,
            workflow_id=context.workflow_id,
            trajectory_id=context.trajectory_id,
            node_name=context.node_name,
            step_type=context.step_type,
            agent_role=context.agent_role,
            step_index=context.step_index,
            estimated_steps=context.estimated_steps,
            criticality=context.criticality,
            difficulty=context.difficulty,
            input_tokens_estimate=estimate_tokens(input),
            output_tokens_estimate=merged_kwargs.get("max_tokens"),
            schema_required=merged_kwargs.get("response_schema") is not None,
            tools_required=bool(merged_kwargs.get("tools")),
            available_models=list(self.models),
            default_model=self.default_model_id,
            force_model=context.force_model,
            allowed_models=context.allowed_models,
            blocked_models=context.blocked_models,
            prompt_fingerprint=prompt_fingerprint(input),
            messages_preview=self._message_preview(messages),
            messages=self._messages_for_request(messages),
            metadata=context.metadata,
        )
        return LLMCall(input=input, config=config, kwargs=merged_kwargs, defaults={}, route_request=route_request)

    def execute_call(self, call: LLMCall) -> Any:
        started = time.perf_counter()
        if self.config.mode == "gateway":
            response = self.gateway_executor.invoke(call)
            self._record_completion(call, response, started)
            return response

        decision = self._route_or_fallback(call)
        actual_model = self._select_actual_model(decision, call.route_request)
        response = self._invoke_local_with_fallback(actual_model, decision, call)
        response = self._validate_if_needed(response, call)
        self._attach_router_metadata(response, call, decision, actual_model)
        self._record_completion(call, response, started, decision, actual_model)
        return response

    async def aexecute_call(self, call: LLMCall) -> Any:
        started = time.perf_counter()
        if self.config.mode == "gateway":
            response = await self.gateway_executor.ainvoke(call)
            self._record_completion(call, response, started)
            return response

        decision = await self._aroute_or_fallback(call)
        actual_model = self._select_actual_model(decision, call.route_request)
        response = await self._ainvoke_local_with_fallback(actual_model, decision, call)
        response = self._validate_if_needed(response, call)
        self._attach_router_metadata(response, call, decision, actual_model)
        self._record_completion(call, response, started, decision, actual_model)
        return response

    def _register_default_model(self, default_model: str | object | None) -> str | None:
        if isinstance(default_model, str):
            return default_model
        if default_model is not None:
            for model_id, model in self.models.items():
                if model is default_model:
                    return model_id
            self.models["default"] = default_model
            return "default"
        if len(self.models) == 1:
            return next(iter(self.models))
        return None

    def _merged_runtime_context(self, config: dict[str, Any] | None) -> RoutingContext:
        parent = current_context.get()
        metadata, nested = self._extract_config_context(config)
        child = RoutingContext(**nested, metadata=metadata)
        return merge_context(parent, child)

    def _extract_config_context(
        self,
        config: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not isinstance(config, dict):
            return {}, {}
        metadata = dict(config.get("metadata") or {})
        nested = dict(metadata.pop("m_router", {}) or {})
        configurable = config.get("configurable") or {}
        if isinstance(configurable, dict):
            thread_id = configurable.get("thread_id")
            if thread_id:
                metadata.setdefault("langgraph_thread_id", thread_id)
                nested.setdefault("trajectory_id", thread_id)
        tags = config.get("tags")
        if tags:
            metadata.setdefault("tags", tags)
        return metadata, nested

    def _ensure_trajectory_and_step(self, context: RoutingContext) -> None:
        if not context.trajectory_id:
            context.trajectory_id = f"traj_{uuid.uuid4().hex[:16]}"
        if context.step_index is None:
            next_step = self._trajectory_counters.get(context.trajectory_id, 0) + 1
            self._trajectory_counters[context.trajectory_id] = next_step
            context.step_index = next_step

    def _messages_for_request(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        if not self.config.send_prompts:
            return None
        return self._redacted_messages(messages)

    def _message_preview(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        if not self.config.send_message_preview:
            return None
        redacted = self._redacted_messages(messages)
        return [
            {
                **message,
                "content": str(message.get("content", ""))[:200],
            }
            for message in redacted
        ]

    def _redacted_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.config.redactor is None:
            return messages
        return self.config.redactor(messages)

    def _route_or_fallback(self, call: LLMCall) -> RouteDecision:
        self.telemetry.add(
            TelemetryEvent(
                event_type="route_requested",
                trajectory_id=call.route_request.trajectory_id,
                metadata=call.route_request.to_dict(),
            )
        )
        try:
            decision = self.client.route(call.route_request)
            self.telemetry.add(
                TelemetryEvent(
                    event_type="route_decided",
                    decision_id=decision.decision_id,
                    trajectory_id=call.route_request.trajectory_id,
                    selected_model=decision.selected_model,
                    metadata={"reason": decision.reason},
                )
            )
            return decision
        except Exception as exc:
            if not self.config.fail_open:
                raise
            fallback = call.route_request.force_model or self.default_model_id
            if fallback is None:
                raise MRouterUnavailableError("route failed and no default model is configured") from exc
            self.telemetry.add(
                TelemetryEvent(
                    event_type="fallback_used",
                    trajectory_id=call.route_request.trajectory_id,
                    actual_model=fallback,
                    metadata={"reason": "route_unavailable", "error": str(exc)},
                )
            )
            return RouteDecision(
                decision_id=f"local_{uuid.uuid4().hex[:12]}",
                selected_model=fallback,
                reason="Route service unavailable; fail-open fallback used.",
                raw={"local_fallback": True},
            )

    async def _aroute_or_fallback(self, call: LLMCall) -> RouteDecision:
        self.telemetry.add(
            TelemetryEvent(
                event_type="route_requested",
                trajectory_id=call.route_request.trajectory_id,
                metadata=call.route_request.to_dict(),
            )
        )
        try:
            decision = await self.client.aroute(call.route_request)
            self.telemetry.add(
                TelemetryEvent(
                    event_type="route_decided",
                    decision_id=decision.decision_id,
                    trajectory_id=call.route_request.trajectory_id,
                    selected_model=decision.selected_model,
                    metadata={"reason": decision.reason},
                )
            )
            return decision
        except Exception as exc:
            if not self.config.fail_open:
                raise
            fallback = call.route_request.force_model or self.default_model_id
            if fallback is None:
                raise MRouterUnavailableError("route failed and no default model is configured") from exc
            self.telemetry.add(
                TelemetryEvent(
                    event_type="fallback_used",
                    trajectory_id=call.route_request.trajectory_id,
                    actual_model=fallback,
                    metadata={"reason": "route_unavailable", "error": str(exc)},
                )
            )
            return RouteDecision(
                decision_id=f"local_{uuid.uuid4().hex[:12]}",
                selected_model=fallback,
                reason="Route service unavailable; fail-open fallback used.",
                raw={"local_fallback": True},
            )

    def _select_actual_model(self, decision: RouteDecision, request: RouteRequest) -> str:
        if request.force_model:
            return request.force_model
        if self.config.mode == "shadow":
            model_id = self.default_model_id
        else:
            model_id = decision.selected_model or decision.fallback_model or self.default_model_id
        if model_id is None:
            raise ModelNotRegisteredError("no model selected and no default model configured")
        if model_id in self.models:
            return model_id
        for fallback in (decision.fallback_model, self.default_model_id):
            if fallback and fallback in self.models:
                self.telemetry.add(
                    TelemetryEvent(
                        event_type="fallback_used",
                        decision_id=decision.decision_id,
                        trajectory_id=request.trajectory_id,
                        actual_model=fallback,
                        selected_model=model_id,
                        metadata={"reason": "selected_model_missing"},
                    )
                )
                return fallback
        raise ModelNotRegisteredError(f"selected model {model_id!r} is not registered")

    def _invoke_local_with_fallback(self, model_id: str, decision: RouteDecision, call: LLMCall) -> Any:
        try:
            return self.local_executor.invoke(model_id, call.input, config=call.config, **call.kwargs)
        except Exception:
            fallback = decision.fallback_model or self.default_model_id
            if fallback and fallback != model_id and fallback in self.models:
                self.telemetry.add(
                    TelemetryEvent(
                        event_type="fallback_used",
                        decision_id=decision.decision_id,
                        trajectory_id=call.route_request.trajectory_id,
                        actual_model=fallback,
                        selected_model=model_id,
                        metadata={"reason": "provider_error"},
                    )
                )
                return self.local_executor.invoke(fallback, call.input, config=call.config, **call.kwargs)
            raise

    async def _ainvoke_local_with_fallback(self, model_id: str, decision: RouteDecision, call: LLMCall) -> Any:
        try:
            return await self.local_executor.ainvoke(model_id, call.input, config=call.config, **call.kwargs)
        except Exception:
            fallback = decision.fallback_model or self.default_model_id
            if fallback and fallback != model_id and fallback in self.models:
                self.telemetry.add(
                    TelemetryEvent(
                        event_type="fallback_used",
                        decision_id=decision.decision_id,
                        trajectory_id=call.route_request.trajectory_id,
                        actual_model=fallback,
                        selected_model=model_id,
                        metadata={"reason": "provider_error"},
                    )
                )
                return await self.local_executor.ainvoke(fallback, call.input, config=call.config, **call.kwargs)
            raise

    def _validate_if_needed(self, response: Any, call: LLMCall) -> Any:
        response_schema = call.kwargs.get("response_schema")
        if response_schema is None:
            return response
        try:
            validate_response(response, response_schema)
        except Exception:
            self.telemetry.add(
                TelemetryEvent(
                    event_type="schema_validation_failed",
                    trajectory_id=call.route_request.trajectory_id,
                    validation_status="failed",
                )
            )
            raise
        return response

    def _attach_router_metadata(
        self,
        response: Any,
        call: LLMCall,
        decision: RouteDecision,
        actual_model: str,
    ) -> None:
        metadata = self._response_metadata(response)
        recommended_model = decision.selected_model
        m_router = {
            "decision_id": decision.decision_id,
            "mode": self.config.mode,
            "selected_model": decision.selected_model,
            "recommended_model": recommended_model if self.config.mode == "shadow" else None,
            "actual_model": actual_model,
            "fallback_model": decision.fallback_model,
            "reason": decision.reason,
            "estimated_cost_usd": decision.estimated_cost_usd,
            "estimated_savings_usd": self._estimated_savings(decision),
            "validation_status": "not_required",
        }
        metadata["m_router"] = {key: value for key, value in m_router.items() if value is not None}

    def _response_metadata(self, response: Any) -> dict[str, Any]:
        metadata = getattr(response, "response_metadata", None)
        if metadata is None:
            metadata = {}
            try:
                setattr(response, "response_metadata", metadata)
            except Exception:
                return metadata
        return metadata

    def _estimated_savings(self, decision: RouteDecision) -> float | None:
        if decision.estimated_cost_usd is None or decision.estimated_default_cost_usd is None:
            return None
        return max(0.0, decision.estimated_default_cost_usd - decision.estimated_cost_usd)

    def _record_completion(
        self,
        call: LLMCall,
        response: Any,
        started: float,
        decision: RouteDecision | None = None,
        actual_model: str | None = None,
    ) -> None:
        usage = self._extract_usage(response)
        self.telemetry.add(
            TelemetryEvent(
                event_type="llm_call_completed",
                decision_id=decision.decision_id if decision else None,
                trajectory_id=call.route_request.trajectory_id,
                actual_model=actual_model,
                recommended_model=decision.selected_model if decision and self.config.mode == "shadow" else None,
                selected_model=decision.selected_model if decision else None,
                latency_ms=int((time.perf_counter() - started) * 1000),
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                cost_usd=usage.get("cost_usd"),
                validation_status="not_required",
            )
        )

    def _extract_usage(self, response: Any) -> dict[str, Any]:
        metadata = getattr(response, "response_metadata", {}) or {}
        usage = metadata.get("token_usage") or metadata.get("usage") or {}
        if "prompt_tokens" in usage:
            usage.setdefault("input_tokens", usage["prompt_tokens"])
        if "completion_tokens" in usage:
            usage.setdefault("output_tokens", usage["completion_tokens"])
        return usage


class MRouterChatModel:
    def __init__(self, router: MRouter, **defaults: Any):
        self.router = router
        self.defaults = defaults

    def invoke(self, input: Any, config: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        call = self.router.build_call(
            input=input,
            config=config,
            kwargs=kwargs,
            defaults=self.defaults,
        )
        return self.router.execute_call(call)

    async def ainvoke(self, input: Any, config: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        call = self.router.build_call(
            input=input,
            config=config,
            kwargs=kwargs,
            defaults=self.defaults,
        )
        return await self.router.aexecute_call(call)

    def stream(self, input: Any, config: dict[str, Any] | None = None, **kwargs: Any):
        response = self.invoke(input, config=config, **kwargs)
        yield response

    async def astream(self, input: Any, config: dict[str, Any] | None = None, **kwargs: Any):
        response = await self.ainvoke(input, config=config, **kwargs)
        yield response

    def with_structured_output(self, schema: Any) -> "MRouterChatModel":
        defaults = {**self.defaults, "response_schema": schema}
        return MRouterChatModel(self.router, **defaults)

    def bind_tools(self, tools: list[Any], **kwargs: Any) -> "MRouterChatModel":
        defaults = {**self.defaults, **kwargs, "tools": tools}
        return MRouterChatModel(self.router, **defaults)
