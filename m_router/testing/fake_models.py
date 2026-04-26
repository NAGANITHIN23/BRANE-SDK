from __future__ import annotations

import asyncio
from typing import Any

from ..schemas.messages import SimpleAIMessage


class FakeChatModel:
    def __init__(self, name: str, fail: bool = False, content: str | None = None):
        self.name = name
        self.fail = fail
        self.content = content
        self.calls: list[dict[str, Any]] = []

    def invoke(
        self,
        input: Any,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SimpleAIMessage:
        self.calls.append({"input": input, "config": config, "kwargs": kwargs})
        if self.fail:
            raise RuntimeError(f"{self.name} failed")
        return SimpleAIMessage(
            content=self.content or f"response from {self.name}",
            response_metadata={
                "model_name": self.name,
                "token_usage": {
                    "input_tokens": 10,
                    "output_tokens": 20,
                },
            },
        )

    async def ainvoke(
        self,
        input: Any,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SimpleAIMessage:
        await asyncio.sleep(0)
        return self.invoke(input, config=config, **kwargs)
