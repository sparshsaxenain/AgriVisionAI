from types import SimpleNamespace

import httpx
import pytest
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from backend.agent.api_client import AgentAPIClient
from backend.agent.graph import AgentContext, AgentDecision, AgentRunResult, AgentService
from backend.agent.tools import TOOLS_BY_NAME
from backend.core.config import Settings


class FakeAgentService:
    settings = SimpleNamespace(ollama_model="gemma3:4b")

    def status(self):
        return {"reachable": True, "model": "gemma3:4b", "model_installed": True, "installed_models": ["gemma3:4b"]}

    def run(self, query, token, user_id, thread_id=None):
        assert query == "show my dashboard"
        assert token
        assert user_id > 0
        return AgentRunResult(
            answer="You have one farm.",
            thread_id=thread_id or "generated-thread",
            model="gemma3:4b",
            tool_calls=[{"tool": "get_dashboard", "status": "success"}],
        )


def test_agent_query_requires_authentication(client):
    response = client.post("/agent/query", json={"query": "show my dashboard"})
    assert response.status_code == 401


def test_agent_query_uses_authenticated_service(client, auth_headers):
    from backend.agent.graph import get_agent_service
    from backend.main import app

    app.dependency_overrides[get_agent_service] = lambda: FakeAgentService()
    response = client.post(
        "/agent/query",
        headers=auth_headers,
        json={"query": "show my dashboard", "thread_id": "test-thread"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "answer": "You have one farm.",
        "thread_id": "test-thread",
        "model": "gemma3:4b",
        "tool_calls": [{"tool": "get_dashboard", "status": "success"}],
    }


def test_agent_api_client_passes_bearer_token():
    def handler(request: httpx.Request):
        assert request.headers["authorization"] == "Bearer test-token"
        assert request.url.path == "/farms"
        return httpx.Response(200, json=[{"id": 7, "farm_name": "North Field"}])

    api = AgentAPIClient("http://agri.test", "test-token", transport=httpx.MockTransport(handler))
    result = TOOLS_BY_NAME["list_farms"].run({}, api)
    assert result[0]["id"] == 7


def test_tool_arguments_are_validated_before_api_call():
    api = AgentAPIClient("http://agri.test", "test-token", transport=httpx.MockTransport(lambda _: pytest.fail("API must not be called")))
    with pytest.raises(ValidationError):
        TOOLS_BY_NAME["record_health_observation"].run({"animal_id": 1, "temperature": 52}, api)


def test_langgraph_loops_from_planner_to_tool_and_final_answer():
    service = AgentService(Settings(agent_max_steps=4))

    class Planner:
        def __init__(self):
            self.calls = 0

        def invoke(self, _messages):
            self.calls += 1
            if self.calls == 1:
                return AgentDecision(action="get_dashboard", arguments={})
            return AgentDecision(action="finish", answer="Your dashboard has 2 active alerts.")

    class API:
        def get(self, path, params=None):
            assert path == "/dashboard/summary"
            return {"kpis": {"active_alerts": 2}}

    service.planner = Planner()
    result = service.graph.invoke(
        {
            "messages": [HumanMessage(content="How many active alerts do I have?")],
            "scratchpad": [],
            "decision": None,
            "iterations": 0,
            "answer": "",
            "tool_trace": [],
        },
        config={"configurable": {"thread_id": "graph-test"}},
        context=AgentContext(api=API()),
    )
    assert result["answer"] == "Your dashboard has 2 active alerts."
    assert result["tool_trace"][0]["tool"] == "get_dashboard"


def test_langgraph_prevents_duplicate_writes_in_one_turn():
    service = AgentService(Settings(agent_max_steps=5))

    class Planner:
        decisions = iter(
            [
                AgentDecision(action="create_farm", arguments={"farm_name": "New Farm"}),
                AgentDecision(action="create_farm", arguments={"farm_name": "New Farm"}),
                AgentDecision(action="finish", answer="New Farm was created once."),
            ]
        )

        def invoke(self, _messages):
            return next(self.decisions)

    class API:
        calls = 0

        def post(self, path, payload):
            self.calls += 1
            return {"id": 9, **payload}

    api = API()
    service.planner = Planner()
    result = service.graph.invoke(
        {
            "messages": [HumanMessage(content="Create a farm called New Farm")],
            "scratchpad": [],
            "decision": None,
            "iterations": 0,
            "answer": "",
            "tool_trace": [],
        },
        config={"configurable": {"thread_id": "duplicate-write-test"}},
        context=AgentContext(api=api),
    )
    assert api.calls == 1
    assert [call["status"] for call in result["tool_trace"]] == ["success", "skipped"]
