import streamlit as st

from frontend.components.ui import api_error, card, page_title
from frontend.utils.i18n import t


def render(client) -> None:
    page_title("Alerts", "Crop, animal health, and vaccination reminders")
    include_read = st.toggle(t("Show resolved alerts"), value=False)
    try:
        alerts = client.get(f"/alerts?include_read={'true' if include_read else 'false'}")
    except Exception as exc:
        api_error(exc)
        return
    if not alerts:
        st.success(t("All clear — no alerts to show."))
        return
    for item in alerts:
        left, right = st.columns([5, 1])
        with left:
            card(item["title"], item["message"], (t("RESOLVED") if item["is_read"] else t(item["severity"].title()).upper()), item["severity"])
        with right:
            if not item["is_read"] and st.button(t("Mark read"), key=f"read_{item['id']}"):
                try:
                    client.patch(f"/alerts/{item['id']}/read")
                    st.rerun()
                except Exception as exc:
                    api_error(exc)
