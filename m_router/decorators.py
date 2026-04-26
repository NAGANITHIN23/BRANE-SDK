from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable

from .context import RoutingContext, current_context, merge_context


def node_decorator(router: object, **metadata: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        signature = inspect.signature(fn)
        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                ctx = _build_context(fn, signature, metadata, args, kwargs)
                token = current_context.set(ctx)
                try:
                    return await fn(*args, **kwargs)
                finally:
                    current_context.reset(token)

            return async_wrapper

        @wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = _build_context(fn, signature, metadata, args, kwargs)
            token = current_context.set(ctx)
            try:
                return fn(*args, **kwargs)
            finally:
                current_context.reset(token)

        return sync_wrapper

    return decorator


def _build_context(
    fn: Callable[..., Any],
    signature: inspect.Signature,
    metadata: dict[str, Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> RoutingContext:
    parent = current_context.get()
    data = dict(metadata)
    data.setdefault("node_name", fn.__name__)
    config_metadata = _extract_config_metadata(_extract_config(signature, args, kwargs))
    nested = config_metadata.pop("m_router", {})
    child_metadata = data.pop("metadata", {})
    child_metadata.update(config_metadata)
    child = RoutingContext(**{**data, **nested, "metadata": child_metadata})
    return merge_context(parent, child)


def _extract_config(
    signature: inspect.Signature,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    if "config" in kwargs:
        return kwargs["config"]
    try:
        bound = signature.bind_partial(*args, **kwargs)
    except TypeError:
        return None
    return bound.arguments.get("config")


def _extract_config_metadata(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    metadata = dict(config.get("metadata") or {})
    configurable = config.get("configurable") or {}
    if isinstance(configurable, dict):
        thread_id = configurable.get("thread_id")
        if thread_id:
            metadata.setdefault("thread_id", thread_id)
            metadata.setdefault("m_router", {}).setdefault("trajectory_id", thread_id)
    return metadata
