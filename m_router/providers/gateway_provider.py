from __future__ import annotations

from typing import Any

from ..schemas.messages import SimpleAIMessage
from ..schemas.route import ExecuteRequest, LLMCall
from ..token_count import normalize_messages


class GatewayExecutor:
    def __init__(self, client: object):
        self.client = client

    def invoke(self, call: LLMCall) -> SimpleAIMessage:
        response = self.client.execute(self._execute_request(call))
        return self._message_from_response(response)

    async def ainvoke(self, call: LLMCall) -> SimpleAIMessage:
        response = await self.client.aexecute(self._execute_request(call))
        return self._message_from_response(response)

    def _execute_request(self, call: LLMCall) -> ExecuteRequest:
        params = {**call.defaults, **call.kwargs}
        response_schema = params.pop("response_schema", None)
        tools = params.pop("tools", []) or []
        return ExecuteRequest(
            route_request=call.route_request,
            messages=normalize_messages(call.input),
            model_params=params,
            tools=tools,
            response_schema=response_schema,
        )

    def _message_from_response(self, response: Any) -> SimpleAIMessage:
        message = response.message
        content = message.get("content", "")
        return SimpleAIMessage(
            content=content,
            response_metadata={
                "token_usage": response.usage,
                "m_router": {
                    "decision_id": response.decision_id,
                    "mode": "gateway",
                    "selected_model": response.selected_model,
                    "reason": response.reason,
                    "validation_status": response.validation.get("status", "not_required"),
                },
            },
        )
