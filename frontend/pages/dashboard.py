from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.components.ui import api_error, card, page_title


def render(client) -> None:
    page_title("Farm Dashboard", "Crop and animal health at a glance")
    try:
        data = client.get("/dashboard/summary")
    except Exception as exc:
        api_error(exc)
        return
    k = data["kpis"]
    cols = st.columns(5)
    for col, label, value in zip(cols, ["Farms", "Active Crops", "Livestock", "Diagnoses", "Active Alerts"], [k["farms"], k["active_crops"], k["livestock"], k["diagnoses"], k["active_alerts"]]):
        col.metric(label, value)

    st.subheader("Quick Actions")
    actions = st.columns(4)
    for column, label, target in zip(actions, ["🌿 Check Crop", "🌾 Add Crop", "🐄 Add Livestock", "🩺 Record Animal Health"], ["Check Crop", "Farm Records", "Animals & Health", "Animals & Health"]):
        if column.button(label, width="stretch"):
            st.session_state.page = target
            st.rerun()

    left, right = st.columns([1.35, 1])
    with left:
        st.subheader("Recent Crop Checks")
        if data["recent_diagnoses"]:
            for item in data["recent_diagnoses"][:4]:
                card(item["condition"], f"{item['crop']} · {item['farm']} · {item['confidence']:.0%} confidence", item["severity"].title(), "critical" if item["severity"].lower() == "high" else "warning")
        else:
            st.info("No crop checks yet. Use Check Crop to begin.")
    with right:
        st.subheader("Upcoming Livestock Tasks")
        if data["upcoming_vaccinations"]:
            for item in data["upcoming_vaccinations"][:4]:
                card(item["task"], f"{item['animal']} · #{item['tag_id']} · {item['due_text']}", item["status"], "critical" if item["status"] == "Overdue" else "warning")
        else:
            st.success("No vaccinations currently due.")

    st.subheader("Farm Overview")
    c1, c2, c3 = st.columns(3)
    charts = [
        (c1, data["crop_distribution"], "Active crops", "name"),
        (c2, data["livestock_distribution"], "Livestock", "name"),
        (c3, data["health_risk_distribution"], "Health checks by risk", "name"),
    ]
    for column, rows, title, names in charts:
        with column:
            if rows:
                frame = pd.DataFrame(rows)
                fig = px.pie(frame, names="name", values="count", title=title, hole=.55, color_discrete_sequence=["#247a45", "#79a96b", "#d1a85b", "#a84c3f"])
                fig.update_layout(margin=dict(l=5, r=5, t=45, b=5), height=285, showlegend=True)
                st.plotly_chart(fig, width="stretch")
            else:
                st.caption(f"{title}: no data yet")

    st.subheader("Important Alerts")
    if data["alerts"]:
        for item in data["alerts"][:4]:
            card(item["title"], item["message"], item["severity"].upper(), item["severity"])
    else:
        st.success("All clear — no active alerts.")
