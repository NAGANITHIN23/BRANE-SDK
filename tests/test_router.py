from __future__ import annotations

import asyncio

import pytest

from m_router import MRouter, current_context
from m_router.testing import FakeChatModel, FakeRouterService


def test_decision_mode_routes_to_selected_local_model():
    mini = FakeChatModel("mini")
    strong = FakeChatModel("strong")
    service = FakeRouterService(selected_model="openai:gpt-4o-mini")
    router = MRouter(
        api_key="mr_test",
        mode="decision",
        app_name="tests",
        models={
            "openai:gpt-4o-mini": mini,
            "anthropic:claude-sonnet": strong,
        },
        default_model="anthropic:claude-sonnet",
        client=service,
    )

    response = router.invoke(
        [{"role": "user", "content": "hello"}],
        context={"workflow_id": "wf", "node_name": "plan", "step_type": "planning"},
    )

    assert response.content == "response from mini"
    assert len(mini.calls) == 1
    assert len(strong.calls) == 0
    assert service.route_requests[0].workflow_id == "wf"
    assert service.route_requests[0].node_name == "plan"
    assert service.route_requests[0].messages is None
    assert response.response_metadata["m_router"]["selected_model"] == "openai:gpt-4o-mini"


def test_shadow_mode_uses_default_but_records_recommendation():
    mini = FakeChatModel("mini")
    strong = FakeChatModel("strong")
    service = FakeRouterService(selected_model="openai:gpt-4o-mini")
    router = MRouter(
        api_key="mr_test",
        mode="shadow",
        models={
            "openai:gpt-4o-mini": mini,
            "anthropic:claude-sonnet": strong,
        },
        default_model="anthropic:claude-sonnet",
        client=service,
    )

    response = router.invoke("hello")

    assert len(strong.calls) == 1
    assert len(mini.calls) == 0
    metadata = response.response_metadata["m_router"]
    assert metadata["actual_model"] == "anthropic:claude-sonnet"
    assert metadata["recommended_model"] == "openai:gpt-4o-mini"


def test_node_decorator_sets_and_resets_context():
    service = FakeRouterService(selected_model="model:a")
    router = MRouter(
        api_key="mr_test",
        models={"model:a": FakeChatModel("a")},
        default_model="model:a",
        client=service,
    )
    llm = router.chat_model()

    @router.node(workflow_id="wf", step_type="planning", agent_role="planner")
    def node(state, config=None):
        assert current_context.get().workflow_id == "wf"
        return llm.invoke(state["messages"], config=config)

    response = node(
        {"messages": ["hello"]},
        config={"configurable": {"thread_id": "traj_1"}, "metadata": {"m_router": {"estimated_steps": 3}}},
    )

    assert current_context.get() is None
    request = service.route_requests[0]
    assert request.trajectory_id == "traj_1"
    assert request.estimated_steps == 3
    assert request.agent_role == "planner"
    assert response.response_metadata["m_router"]["decision_id"] == "dec_1"


def test_fail_open_uses_default_model_when_route_service_fails():
    default = FakeChatModel("default")
    service = FakeRouterService(unavailable=True)
    router = MRouter(
        api_key="mr_test",
        models={"default:model": default},
        default_model="default:model",
        client=service,
    )

    response = router.invoke("hello")

    assert response.content == "response from default"
    assert response.response_metadata["m_router"]["actual_model"] == "default:model"


def test_missing_selected_model_uses_registered_fallback():
    fallback = FakeChatModel("fallback")
    service = FakeRouterService(selected_model="missing:model", fallback_model="fallback:model")
    router = MRouter(
        api_key="mr_test",
        models={"fallback:model": fallback},
        default_model="fallback:model",
        client=service,
    )

    response = router.invoke("hello")

    assert response.content == "response from fallback"
    assert response.response_metadata["m_router"]["selected_model"] == "missing:model"
    assert response.response_metadata["m_router"]["actual_model"] == "fallback:model"


def test_gateway_mode_sends_full_messages():
    service = FakeRouterService(selected_model="gateway:model")
    router = MRouter(api_key="mr_test", mode="gateway", client=service)

    response = router.invoke([{"role": "user", "content": "hello"}], temperature=0.2)

    assert response.content == "gateway response"
    assert service.execute_requests[0].messages[0]["content"] == "hello"
    assert service.execute_requests[0].model_params["temperature"] == 0.2
    assert response.response_metadata["m_router"]["mode"] == "gateway"


def test_async_node_and_ainvoke():
    service = FakeRouterService(selected_model="model:a")
    router = MRouter(
        api_key="mr_test",
        models={"model:a": FakeChatModel("a")},
        default_model="model:a",
        client=service,
    )
    llm = router.chat_model()

    @router.node(workflow_id="wf", node_name="async_plan")
    async def node(state, config=None):
        return await llm.ainvoke(state["messages"], config=config)

    response = asyncio.run(node({"messages": ["hello"]}))

    assert response.content == "response from a"
    assert service.route_requests[0].node_name == "async_plan"


def test_structured_output_validation_failure_emits_event():
    service = FakeRouterService(selected_model="model:a")
    router = MRouter(
        api_key="mr_test",
        models={"model:a": FakeChatModel("a", content='{"ok": true}')},
        default_model="model:a",
        client=service,
    )

    response = router.chat_model().with_structured_output({"required": ["ok"]}).invoke("hello")

    assert response.content == '{"ok": true}'

    router_bad = MRouter(
        api_key="mr_test",
        models={"model:a": FakeChatModel("a", content='{"nope": true}')},
        default_model="model:a",
        client=FakeRouterService(selected_model="model:a"),
    )
    with pytest.raises(Exception):
        router_bad.chat_model().with_structured_output({"required": ["ok"]}).invoke("hello")
