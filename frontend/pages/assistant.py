"""Natural-language interface for the local LangGraph agent."""
from __future__ import annotations

from uuid import uuid4

import streamlit as st

from frontend.components.ui import api_error, page_title
from frontend.utils.api_client import APIClient


def _render_tool_calls(tool_calls: list[dict]) -> None:
    if not tool_calls:
        return
    with st.expander("Actions taken"):
        for call in tool_calls:
            marker = "OK" if call.get("status") == "success" else call.get("status", "Error").title()
            st.caption(f"{marker} - {call.get('tool', 'tool')}")


def render(client: APIClient) -> None:
    page_title("AI Assistant", "Ask in plain language. The local agent can inspect records and complete farm tasks for you.")
    try:
        status = client.get("/agent/status")
        if not status.get("reachable"):
            st.warning("Ollama is not reachable. Start Ollama before sending a query.")
        elif not status.get("model_installed"):
            st.warning(f"The local model is not installed yet. Run: ollama pull {status['model']}")
        else:
            st.caption(f"Local model: {status['model']}")
    except Exception as exc:
        api_error(exc)

    if "agent_thread_id" not in st.session_state:
        st.session_state.agent_thread_id = uuid4().hex
    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = []

    for item in st.session_state.agent_messages:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
            _render_tool_calls(item.get("tool_calls", []))

    prompt = st.chat_input("For example: Which vaccinations are due, or add a new tomato crop to Green Valley Farm")
    if not prompt:
        return
    st.session_state.agent_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Working with your farm records..."):
            try:
                response = client.post(
                    "/agent/query",
                    json={"query": prompt, "thread_id": st.session_state.agent_thread_id},
                    timeout=600,
                )
                st.markdown(response["answer"])
                calls = response.get("tool_calls", [])
                _render_tool_calls(calls)
                st.session_state.agent_messages.append({"role": "assistant", "content": response["answer"], "tool_calls": calls})
            except Exception as exc:
                api_error(exc)
