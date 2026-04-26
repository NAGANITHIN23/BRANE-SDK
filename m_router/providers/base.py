from __future__ import annotations

from typing import Any, Protocol


class ProviderExecutor(Protocol):
    def invoke(self, model_id: str, input: Any, config: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        ...

    async def ainvoke(
        self,
        model_id: str,
        input: Any,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        ...
