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


def _render_image_analysis(result: dict) -> None:
    advisory = result["advisory"]
    severity = result["severity"].title()
    st.markdown(f"**Crop image:** {result['display_name']} - {result['confidence']:.1%} confidence - {severity} severity")
    st.progress(float(result["confidence"]), text=f"Confidence {result['confidence']:.1%}")
    st.write(advisory["description"])
    with st.expander("Image-model recommendations"):
        st.markdown("**Immediate actions**")
        for action in advisory["recommended_actions"]:
            st.markdown(f"- {action}")
        st.markdown("**Prevention**")
        for action in advisory["preventive_measures"]:
            st.markdown(f"- {action}")
        st.caption(advisory["safety_note"])


def render(client: APIClient) -> None:
    page_title("AI Assistant", "Ask in plain language and attach a crop image directly in the query bar when needed.")
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
            if item.get("attachment_name"):
                st.caption(f"Attached: {item['attachment_name']}")
            if item.get("image_analysis"):
                _render_image_analysis(item["image_analysis"])
            if item.get("saved_diagnosis_id"):
                st.success(f"Diagnosis #{item['saved_diagnosis_id']} was added to crop records.")
            elif item.get("image_analysis"):
                st.caption("Quick analysis only — this result was not added to crop records.")
            _render_tool_calls(item.get("tool_calls", []))

    entry = st.chat_input(
        "For example: What vaccinations are due? Or attach a leaf and ask: Analyze this crop",
        accept_file=True,
        file_type=["jpg", "jpeg", "png"],
        max_upload_size=8,
    )
    if not entry:
        return

    if isinstance(entry, str):
        prompt = entry.strip()
        uploaded = None
    else:
        prompt = entry.text.strip()
        uploaded = entry.files[0] if entry.files else None
    if uploaded is not None and not prompt:
        prompt = "Analyze this crop image."
    if not prompt:
        return

    user_item = {
        "role": "user",
        "content": prompt,
        "attachment_name": uploaded.name if uploaded is not None else None,
    }
    st.session_state.agent_messages.append(user_item)
    with st.chat_message("user"):
        st.markdown(prompt)
        if uploaded is not None:
            st.caption(f"Attached: {uploaded.name}")
    with st.chat_message("assistant"):
        with st.spinner("Working with your farm records..."):
            try:
                if uploaded is not None:
                    response = client.post(
                        "/agent/query-with-image",
                        data={"query": prompt, "thread_id": st.session_state.agent_thread_id},
                        files={"image": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")},
                        timeout=600,
                    )
                else:
                    response = client.post(
                        "/agent/query",
                        json={"query": prompt, "thread_id": st.session_state.agent_thread_id},
                        timeout=600,
                    )
                st.markdown(response["answer"])
                analysis = response.get("image_analysis")
                if analysis:
                    _render_image_analysis(analysis)
                saved_diagnosis_id = response.get("saved_diagnosis_id")
                if saved_diagnosis_id:
                    st.success(f"Diagnosis #{saved_diagnosis_id} was added to crop records.")
                elif analysis:
                    st.caption("Quick analysis only — this result was not added to crop records.")
                calls = response.get("tool_calls", [])
                _render_tool_calls(calls)
                st.session_state.agent_messages.append(
                    {
                        "role": "assistant",
                        "content": response["answer"],
                        "tool_calls": calls,
                        "image_analysis": analysis,
                        "saved_diagnosis_id": saved_diagnosis_id,
                    }
                )
            except Exception as exc:
                api_error(exc)
