from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.components.ui import api_error, page_title


def render(client) -> None:
    page_title("Diagnosis History", "Saved crop checks and trends")
    try:
        rows = client.get("/diagnosis/history")
        crops = client.get("/crops")
        farms = client.get("/farms")
    except Exception as exc:
        api_error(exc)
        return
    if not rows:
        st.info("No saved diagnoses yet.")
        return
    crop_names = {item["id"]: item["crop_name"] for item in crops}
    farm_names = {item["id"]: item["farm_name"] for item in farms}
    frame = pd.DataFrame([{
        "Date": item["created_at"][:10], "Crop": crop_names.get(item["crop_id"], "—"),
        "Farm": farm_names.get(item["farm_id"], "—"), "Disease": item["display_name"],
        "Confidence": item["confidence"], "Severity": item["severity"].title(), "id": item["id"],
    } for item in rows])
    c1, c2 = st.columns(2)
    with c1:
        counts = frame.groupby("Disease", as_index=False).size()
        fig = px.bar(counts, x="Disease", y="size", title="Cases by condition", color_discrete_sequence=["#247a45"])
        st.plotly_chart(fig, width="stretch")
    with c2:
        severity = frame.groupby("Severity", as_index=False).size()
        fig = px.pie(severity, names="Severity", values="size", title="Severity distribution", hole=.5, color_discrete_sequence=["#79a96b", "#d1a85b", "#a84c3f"])
        st.plotly_chart(fig, width="stretch")
    display = frame.copy()
    display["Confidence"] = display["Confidence"].map(lambda value: f"{value:.1%}")
    st.dataframe(display.drop(columns=["id"]), width="stretch", hide_index=True)
    selected = st.selectbox("Open a saved diagnosis", options=rows, format_func=lambda item: f"{item['created_at'][:10]} · {item['display_name']}")
    if selected:
        advisory = json.loads(selected["advisory"])
        with st.expander(f"{selected['display_name']} · {selected['confidence']:.1%}", expanded=False):
            st.write(advisory.get("description", ""))
            st.markdown("**Recommended actions**")
            for action in advisory.get("recommended_actions", []):
                st.markdown(f"- {action}")
