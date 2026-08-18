"""Executive routing: the decision of which specialist should answer."""

import pytest

from ray.agents.router import ExecutiveRouter
from ray.config import get_settings
from ray.llm.registry import ProviderRegistry
from tests.fakes import FakeProvider


def _settings():
    return get_settings().model_copy(update={"llm_provider": "mock", "llm_fallback_provider": None})


@pytest.fixture
def router() -> ExecutiveRouter:
    # Register the fake under the name the chain will resolve to.
    registry = ProviderRegistry(_settings())
    registry.register("mock", FakeProvider())
    return ExecutiveRouter(registry)


async def test_keyword_route_matches_planning(router: ExecutiveRouter) -> None:
    decision = await router.decide("Plan my week", enabled={"planning", "coding"})
    assert decision.agents == ("planning",)
    assert decision.mode == "keyword"


async def test_keyword_route_matches_coding(router: ExecutiveRouter) -> None:
    decision = await router.decide("debug my Python function", enabled={"coding"})
    assert decision.agents == ("coding",)


async def test_chat_question_is_answered_directly(router: ExecutiveRouter) -> None:
    decision = await router.decide("thanks", enabled={"planning", "coding"})
    assert decision.agents == ()
    assert decision.mode == "keyword"


async def test_function_call_routes_to_named_agent() -> None:
    provider = FakeProvider(tool_routing={"planning": {"message": "plan it"}})
    registry = ProviderRegistry(_settings())
    registry.register("mock", provider)
    router = ExecutiveRouter(registry)

    decision = await router.decide("I have a lot to do", enabled={"planning", "coding"})

    assert decision.mode == "function_call"
    assert "planning" in decision.agents
    assert len(decision.agents) <= 2


async def test_disabled_agents_are_not_routed_to(router: ExecutiveRouter) -> None:
    decision = await router.decide("Plan my week", enabled={"coding"})
    # Keyword match for planning, but planning is disabled.
    assert "planning" not in decision.agents
