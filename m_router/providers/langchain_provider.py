from __future__ import annotations

import asyncio
from typing import Any

from ..errors import ModelNotRegisteredError


class LocalProviderExecutor:
    def __init__(self, models: dict[str, object]):
        self.models = models

    def invoke(
        self,
        model_id: str,
        input: Any,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        model = self._get_model(model_id)
        if hasattr(model, "invoke"):
            return model.invoke(input, config=config, **kwargs)
        if callable(model):
            return model(input, config=config, **kwargs)
        raise TypeError(f"registered model {model_id!r} is not invokable")

    async def ainvoke(
        self,
        model_id: str,
        input: Any,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        model = self._get_model(model_id)
        if hasattr(model, "ainvoke"):
            return await model.ainvoke(input, config=config, **kwargs)
        return await asyncio.to_thread(self.invoke, model_id, input, config, **kwargs)

    def stream(
        self,
        model_id: str,
        input: Any,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        model = self._get_model(model_id)
        if hasattr(model, "stream"):
            yield from model.stream(input, config=config, **kwargs)
            return
        yield self.invoke(model_id, input, config=config, **kwargs)

    async def astream(
        self,
        model_id: str,
        input: Any,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        model = self._get_model(model_id)
        if hasattr(model, "astream"):
            async for chunk in model.astream(input, config=config, **kwargs):
                yield chunk
            return
        yield await self.ainvoke(model_id, input, config=config, **kwargs)

    def _get_model(self, model_id: str) -> object:
        try:
            return self.models[model_id]
        except KeyError as exc:
            raise ModelNotRegisteredError(f"model {model_id!r} is not registered") from exc
