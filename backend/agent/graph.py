"""Gemma-compatible LangGraph planner/tool loop powered by local Ollama."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Annotated, Any, TypedDict
from uuid import uuid4

import httpx
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field, ValidationError

from backend.agent.api_client import AgentAPIClient, AgentAPIError
from backend.agent.tools import ActionName, TOOLS, TOOLS_BY_NAME
from backend.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AgentDecision(BaseModel):
    """One next step selected by the local model."""

    action: ActionName = Field(description="One tool name, or finish when ready to answer or ask the user for missing information.")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments matching the selected tool schema; use an empty object for finish or no-argument tools.")
    answer: str = Field(default="", description="Final user-facing response when action is finish; otherwise leave empty.")


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    scratchpad: list[str]
    decision: AgentDecision | None
    iterations: int
    answer: str
    tool_trace: list[dict[str, Any]]


@dataclass(frozen=True)
class AgentContext:
    api: AgentAPIClient


@dataclass(frozen=True)
class AgentRunResult:
    answer: str
    thread_id: str
    model: str
    tool_calls: list[dict[str, Any]]


SYSTEM_PROMPT = """You are the AgriVision farm operations agent. Turn the user's plain-language request into verified actions using the available tools.

Rules:
- Use tools for every claim about the user's farms, crops, animals, diagnoses, vaccinations, dashboard, or alerts. Never guess their records or numeric IDs.
- Before a write, use list/read tools when needed to resolve the correct entity. Never invent missing user data.
- Only use a tool that changes data when the user clearly requested that change. If required details are missing or the target is ambiguous, finish with one concise follow-up question.
- Dates in tool arguments must use YYYY-MM-DD. Today is supplied in each planning request.
- Treat crop and livestock results as preliminary decision support. For urgent/high-risk animal findings, recommend a qualified veterinarian; do not claim a definitive diagnosis or invent medication doses.
- After a tool succeeds, base the answer on its returned data. If it fails, correct the arguments or clearly explain what the user must provide.
- Match the user's language when practical. Keep the final response direct and useful.
- Choose exactly one next action. Use action=finish only when the task is complete or user input is required. Put the complete user-facing response in answer when finishing.

Available tools (JSON):
{tool_catalog}
"""


def _content(message: AnyMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)


def _history(messages: list[AnyMessage], limit: int = 10) -> str:
    rows: list[str] = []
    for message in messages[-limit:]:
        role = "User" if isinstance(message, HumanMessage) else "Assistant"
        rows.append(f"{role}: {_content(message)}")
    return "\n".join(rows)


def _model_text(value: Any, limit: int = 9000) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return text
    return text[:limit] + "... [response truncated]"


class AgentService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.model = ChatOllama(
            model=self.settings.ollama_model,
            base_url=self.settings.ollama_base_url,
            temperature=0,
            num_ctx=self.settings.agent_context_window,
            num_predict=768,
            keep_alive="10m",
            client_kwargs={"timeout": self.settings.agent_timeout_seconds},
        )
        # JSON-schema steering works with Gemma-family models without depending on
        # the model-specific native function-calling template.
        self.planner = self.model.with_structured_output(AgentDecision, method="json_schema")
        self.checkpointer = InMemorySaver()
        self.graph = self._build_graph()

    def _build_graph(self):
        catalog = json.dumps([tool.catalog_entry() for tool in TOOLS], ensure_ascii=False)
        system_message = SystemMessage(SYSTEM_PROMPT.format(tool_catalog=catalog))
        max_steps = max(2, min(self.settings.agent_max_steps, 20))

        def plan(state: AgentState) -> dict[str, Any]:
            scratchpad = "\n".join(state.get("scratchpad", [])) or "No tools used yet in this turn."
            prompt = HumanMessage(
                "Today: " + date.today().isoformat() + "\n\nConversation:\n" + _history(state["messages"]) +
                "\n\nTool observations from this turn:\n" + scratchpad + "\n\nSelect the next action now."
            )
            decision = self.planner.invoke([system_message, prompt])
            return {"decision": decision, "iterations": state.get("iterations", 0) + 1}

        def route(state: AgentState) -> str:
            decision = state.get("decision")
            if decision is None or decision.action == "finish" or state.get("iterations", 0) >= max_steps:
                return "finalize"
            return "tool"

        def call_tool(state: AgentState, runtime: Runtime[AgentContext]) -> dict[str, Any]:
            decision = state["decision"]
            if decision is None or decision.action == "finish":
                return {}
            tool = TOOLS_BY_NAME[decision.action]
            trace = {
                "tool": tool.name,
                "arguments": decision.arguments,
                "changes_data": tool.mutates_data,
                "status": "success",
            }
            duplicate = next(
                (
                    previous for previous in state.get("tool_trace", [])
                    if previous.get("tool") == tool.name
                    and previous.get("arguments") == decision.arguments
                    and previous.get("status") == "success"
                ),
                None,
            )
            if tool.mutates_data and duplicate:
                observation = f"{tool.name} was not repeated because the same write already succeeded in this turn."
                trace["status"] = "skipped"
                trace["result_preview"] = "Duplicate write prevented."
                return {
                    "scratchpad": [*state.get("scratchpad", []), observation],
                    "tool_trace": [*state.get("tool_trace", []), trace],
                }
            try:
                result = tool.run(decision.arguments, runtime.context.api)
                observation = f"{tool.name} returned: {_model_text(result)}"
                trace["result_preview"] = _model_text(result, 500)
            except (ValidationError, AgentAPIError, ValueError) as exc:
                observation = f"{tool.name} failed: {exc}"
                trace["status"] = "error"
                trace["result_preview"] = str(exc)[:500]
            return {
                "scratchpad": [*state.get("scratchpad", []), observation],
                "tool_trace": [*state.get("tool_trace", []), trace],
            }

        def finalize(state: AgentState) -> dict[str, Any]:
            decision = state.get("decision")
            if decision and decision.action == "finish" and decision.answer.strip():
                answer = decision.answer.strip()
            elif state.get("iterations", 0) >= max_steps:
                answer = "I could not safely complete that request within the agent step limit. Please make the request more specific and try again."
            else:
                answer = "I need a little more information to complete that request."
            return {"answer": answer, "messages": [AIMessage(content=answer)]}

        builder = StateGraph(AgentState, context_schema=AgentContext)
        builder.add_node("plan", plan)
        builder.add_node("tool", call_tool)
        builder.add_node("finalize", finalize)
        builder.add_edge(START, "plan")
        builder.add_conditional_edges("plan", route, {"tool": "tool", "finalize": "finalize"})
        builder.add_edge("tool", "plan")
        builder.add_edge("finalize", END)
        return builder.compile(checkpointer=self.checkpointer)

    def run(self, query: str, token: str, user_id: int, thread_id: str | None = None) -> AgentRunResult:
        public_thread_id = thread_id or uuid4().hex
        scoped_thread_id = f"user-{user_id}:{public_thread_id}"
        api = AgentAPIClient(
            base_url=self.settings.api_base_url,
            token=token,
            timeout=self.settings.agent_timeout_seconds,
        )
        initial: AgentState = {
            "messages": [HumanMessage(content=query)],
            "scratchpad": [],
            "decision": None,
            "iterations": 0,
            "answer": "",
            "tool_trace": [],
        }
        result = self.graph.invoke(
            initial,
            config={
                "configurable": {"thread_id": scoped_thread_id},
                "recursion_limit": max(8, self.settings.agent_max_steps * 2 + 4),
            },
            context=AgentContext(api=api),
        )
        return AgentRunResult(
            answer=result["answer"],
            thread_id=public_thread_id,
            model=self.settings.ollama_model,
            tool_calls=result.get("tool_trace", []),
        )

    def status(self) -> dict[str, Any]:
        try:
            response = httpx.get(f"{self.settings.ollama_base_url}/api/tags", timeout=2)
            response.raise_for_status()
            installed = [item.get("name", "") for item in response.json().get("models", [])]
            requested = self.settings.ollama_model if ":" in self.settings.ollama_model else f"{self.settings.ollama_model}:latest"
            return {
                "reachable": True,
                "model": self.settings.ollama_model,
                "model_installed": requested in installed,
                "installed_models": installed,
            }
        except (httpx.HTTPError, ValueError):
            return {"reachable": False, "model": self.settings.ollama_model, "model_installed": False, "installed_models": []}


@lru_cache
def get_agent_service() -> AgentService:
    return AgentService()
