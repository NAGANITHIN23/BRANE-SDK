# Brane SDK

Brane is a Python SDK for routing agent LLM calls through a hosted decision service while keeping provider execution local by default.

Install:

```bash
pip install brane-sdk
```

Set your Brane API key once before running your app:

```bash
export BRANE_API_KEY="brane_..."
```

## Install

From PyPI, once published:

```bash
pip install brane-sdk
```

From this repository:

```bash
pip install .
```

For local development and tests:

```bash
pip install -e ".[test]"
pytest
```

## Quick Start

```python
from m_router import MRouter

router = MRouter(
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

Provider API keys stay in your app. Register the model clients you already use, and Brane chooses which one to call:

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

router = MRouter(
    mode="decision",
    models={
        "openai:gpt-4o-mini": ChatOpenAI(model="gpt-4o-mini"),
        "anthropic:claude-sonnet": ChatAnthropic(model="claude-sonnet-4-5"),
    },
    default_model="openai:gpt-4o-mini",
)
```

The current package includes the MVP core: shadow and decision modes, context propagation, local model execution, fail-open fallback, route request building, telemetry buffering, outcome tagging, and fakes for tests.

## Gateway Mode

Gateway mode sends the full request to the Brane Cloud `/v1/execute` endpoint and returns the hosted response:

```python
from m_router import MRouter

router = MRouter(
    api_key="brane_dev_...",
    mode="gateway",
    base_url="http://127.0.0.1:8080",
)

response = router.invoke([{"role": "user", "content": "Hello"}])
print(response.content)
print(response.response_metadata["m_router"])
```

## Build for PyPI

```bash
python -m pip install -U build twine
python -m build
twine check dist/*
```

To publish to TestPyPI:

```bash
twine upload --repository testpypi dist/*
```

To publish to PyPI:

```bash
twine upload dist/*
```
