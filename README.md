# M-Router SDK

M-Router is a Python SDK for routing LLM calls through a hosted decision service while keeping provider execution local by default.

```python
from m_router import MRouter

router = MRouter(
    api_key="mr_...",
    mode="decision",
    models={"openai:gpt-4o-mini": local_chat_model},
    default_model="openai:gpt-4o-mini",
)

llm = router.chat_model()

@router.node(workflow_id="research_agent", step_type="planning")
def plan_node(state, config=None):
    response = llm.invoke(state["messages"], config=config)
    return {"messages": [response]}
```

The current package includes the MVP core: shadow and decision modes, context propagation, local model execution, fail-open fallback, route request building, telemetry buffering, outcome tagging, and fakes for tests.
