from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.components.ui import api_error, page_title
from frontend.utils.i18n import current_language, t


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
        st.info(t("No saved diagnoses yet."))
        return
    crop_names = {item["id"]: item["crop_name"] for item in crops}
    farm_names = {item["id"]: item["farm_name"] for item in farms}
    advisories = {item["id"]: json.loads(item["advisory"]) for item in rows}

    def display_name(item: dict) -> str:
        advisory = advisories[item["id"]]
        return advisory.get("_display_names", {}).get(current_language(), item["display_name"])

    frame = pd.DataFrame([{
        t("Date"): item["created_at"][:10], t("Crop"): crop_names.get(item["crop_id"], "—"),
        t("Farm"): farm_names.get(item["farm_id"], "—"), t("Disease"): display_name(item),
        t("Confidence"): item["confidence"], t("Severity"): t(item["severity"].title()), "id": item["id"],
    } for item in rows])
    c1, c2 = st.columns(2)
    with c1:
        counts = frame.groupby(t("Disease"), as_index=False).size()
        fig = px.bar(counts, x=t("Disease"), y="size", title=t("Cases by condition"), color_discrete_sequence=["#247a45"])
        st.plotly_chart(fig, width="stretch")
    with c2:
        severity = frame.groupby(t("Severity"), as_index=False).size()
        fig = px.pie(severity, names=t("Severity"), values="size", title=t("Severity distribution"), hole=.5, color_discrete_sequence=["#79a96b", "#d1a85b", "#a84c3f"])
        st.plotly_chart(fig, width="stretch")
    display = frame.copy()
    display[t("Confidence")] = display[t("Confidence")].map(lambda value: f"{value:.1%}")
    st.dataframe(display.drop(columns=["id"]), width="stretch", hide_index=True)
    selected = st.selectbox(t("Open a saved diagnosis"), options=rows, format_func=lambda item: f"{item['created_at'][:10]} · {display_name(item)}")
    if selected:
        stored_advisory = advisories[selected["id"]]
        advisory = stored_advisory.get("_localizations", {}).get(current_language(), stored_advisory)
        with st.expander(f"{display_name(selected)} · {selected['confidence']:.1%}", expanded=False):
            st.write(advisory.get("description", ""))
            st.markdown(f"**{t('Recommended actions')}**")
            for action in advisory.get("recommended_actions", []):
                st.markdown(f"- {action}")
