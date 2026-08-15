from types import SimpleNamespace

import httpx
import pytest
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from backend.agent.api_client import AgentAPIClient
from backend.api.agent import _wants_saved_diagnosis
from backend.agent.graph import AgentContext, AgentDecision, AgentRunResult, AgentService
from backend.agent.tools import TOOLS_BY_NAME
from backend.core.config import Settings


class FakeAgentService:
    settings = SimpleNamespace(ollama_model="gemma3:4b")

    def status(self):
        return {"reachable": True, "model": "gemma3:4b", "model_installed": True, "installed_models": ["gemma3:4b"]}

    def run(self, query, token, user_id, thread_id=None, verified_context=""):
        assert token
        assert user_id > 0
        return AgentRunResult(
            answer="The crop image was analyzed." if verified_context else "You have one farm.",
            thread_id=thread_id or "generated-thread",
            model="gemma3:4b",
            tool_calls=[{"tool": "get_dashboard", "status": "success"}],
        )


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Analyze this crop", False),
        ("Analyze this crop but don't save it", False),
        ("Analyze and save this result", True),
        ("Check this image and add it", True),
        ("Please record the diagnosis", True),
    ],
)
def test_image_save_intent_is_explicit(query, expected):
    assert _wants_saved_diagnosis(query) is expected


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


def test_agent_query_with_image_saves_only_when_explicitly_requested(client, auth_headers):
    from io import BytesIO

    from PIL import Image

    from backend.agent.graph import get_agent_service
    from backend.main import app

    app.dependency_overrides[get_agent_service] = lambda: FakeAgentService()
    farm = client.post("/farms", headers=auth_headers, json={"farm_name": "Image Farm"}).json()
    crop = client.post(
        "/crops", headers=auth_headers, json={"farm_id": farm["id"], "crop_name": "Tomato"}
    ).json()
    client.post(
        "/crops", headers=auth_headers, json={"farm_id": farm["id"], "crop_name": "Potato"}
    )
    buffer = BytesIO()
    Image.new("RGB", (80, 80), "green").save(buffer, "JPEG")

    response = client.post(
        "/agent/query-with-image",
        headers=auth_headers,
        data={"query": "Analyze and save this Tomato leaf from Image Farm", "thread_id": "image-thread"},
        files={"image": ("leaf.jpg", buffer.getvalue(), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "The crop image was analyzed."
    assert response.json()["image_analysis"]["predicted_class"] == "Tomato___Early_blight"
    assert response.json()["diagnosis_context"] == {"farm_id": farm["id"], "crop_id": crop["id"]}
    assert response.json()["saved_diagnosis_id"] is not None
    history = client.get("/diagnosis/history", headers=auth_headers).json()
    assert [item["id"] for item in history] == [response.json()["saved_diagnosis_id"]]


def test_agent_image_query_is_general_and_temporary_by_default(client, auth_headers):
    from io import BytesIO

    from PIL import Image

    from backend.agent.graph import get_agent_service
    from backend.main import app

    app.dependency_overrides[get_agent_service] = lambda: FakeAgentService()
    farm = client.post("/farms", headers=auth_headers, json={"farm_name": "Mixed Farm"}).json()
    client.post("/crops", headers=auth_headers, json={"farm_id": farm["id"], "crop_name": "Tomato"})
    client.post("/crops", headers=auth_headers, json={"farm_id": farm["id"], "crop_name": "Potato"})
    buffer = BytesIO()
    Image.new("RGB", (80, 80), "green").save(buffer, "JPEG")

    response = client.post(
        "/agent/query-with-image",
        headers=auth_headers,
        data={"query": "Analyze this crop image"},
        files={"image": ("leaf.jpg", buffer.getvalue(), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["image_analysis"]["predicted_class"] == "Tomato___Early_blight"
    assert response.json()["image_analysis"]["image_token"] == ""
    assert response.json()["diagnosis_context"] is None
    assert response.json()["saved_diagnosis_id"] is None
    assert client.get("/diagnosis/history", headers=auth_headers).json() == []


def test_agent_image_save_request_requires_unambiguous_crop(client, auth_headers):
    from io import BytesIO

    from PIL import Image

    farm = client.post("/farms", headers=auth_headers, json={"farm_name": "Mixed Farm"}).json()
    client.post("/crops", headers=auth_headers, json={"farm_id": farm["id"], "crop_name": "Tomato"})
    client.post("/crops", headers=auth_headers, json={"farm_id": farm["id"], "crop_name": "Potato"})
    buffer = BytesIO()
    Image.new("RGB", (80, 80), "green").save(buffer, "JPEG")

    response = client.post(
        "/agent/query-with-image",
        headers=auth_headers,
        data={"query": "Analyze this image and save the result"},
        files={"image": ("leaf.jpg", buffer.getvalue(), "image/jpeg")},
    )

    assert response.status_code == 400
    assert "Mention the farm and crop" in response.json()["detail"]


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


def test_update_farm_tool_sends_only_requested_property():
    def handler(request: httpx.Request):
        assert request.method == "PATCH"
        assert request.url.path == "/farms/12"
        assert request.content == b'{"status":"Dry"}'
        return httpx.Response(
            200,
            json={
                "id": 12, "farmer_id": 1, "farm_name": "Jodhpur Farm", "village": "", "district": "",
                "state": "", "latitude": None, "longitude": None, "total_area": 0, "area_unit": "acres",
                "soil_type": "Unknown", "irrigation_type": "Rainfed", "status": "Dry",
                "created_at": "2026-08-15T00:00:00",
            },
        )

    api = AgentAPIClient("http://agri.test", "test-token", transport=httpx.MockTransport(handler))
    result = TOOLS_BY_NAME["update_farm"].run({"farm_id": 12, "status": "Dry"}, api)
    assert result["status"] == "Dry"


def test_crop_tools_list_catalog_update_and_delete():
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        if request.url.path == "/diagnosis/supported-crops":
            return httpx.Response(200, json=["Potato", "Tomato"])
        if request.method == "PATCH":
            assert request.url.path == "/crops/8"
            assert request.content == b'{"crop_name":"Potato","crop_stage":"Flowering"}'
            return httpx.Response(200, json={"id": 8, "crop_name": "Potato", "crop_stage": "Flowering"})
        assert request.method == "DELETE"
        assert request.url.path == "/crops/8"
        assert request.url.params["confirm_name"] == "Potato"
        return httpx.Response(204)

    api = AgentAPIClient("http://agri.test", "test-token", transport=httpx.MockTransport(handler))
    assert TOOLS_BY_NAME["list_supported_crop_types"].run({}, api) == ["Potato", "Tomato"]
    updated = TOOLS_BY_NAME["update_crop"].run(
        {"crop_id": 8, "crop_name": "potato", "crop_stage": "Flowering"}, api
    )
    assert updated["crop_name"] == "Potato"
    assert TOOLS_BY_NAME["delete_crop"].run(
        {"crop_id": 8, "confirm_name": "Potato"}, api
    )["deleted"] is True
    assert len(requests) == 3


def test_agent_crop_tool_rejects_unsupported_crop_before_api_call():
    api = AgentAPIClient(
        "http://agri.test",
        "test-token",
        transport=httpx.MockTransport(lambda _: pytest.fail("API must not be called")),
    )
    with pytest.raises(ValidationError, match="Unsupported crop type"):
        TOOLS_BY_NAME["create_crop"].run({"farm_id": 1, "crop_name": "Wheat"}, api)


def test_global_vaccination_tool_does_not_require_animal_id():
    def handler(request: httpx.Request):
        assert request.method == "GET"
        assert request.url.path == "/livestock/vaccinations/due"
        return httpx.Response(200, json=[{"animal": "Gauri", "vaccine_name": "FMD", "status": "Due Soon"}])

    api = AgentAPIClient("http://agri.test", "test-token", transport=httpx.MockTransport(handler))
    result = TOOLS_BY_NAME["list_due_vaccinations"].run({}, api)
    assert result[0]["animal"] == "Gauri"


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
