import streamlit as st

from frontend.components.ui import api_error, card, page_title


def render(client) -> None:
    page_title("Alerts", "Crop, animal health, and vaccination reminders")
    include_read = st.toggle("Show resolved alerts", value=False)
    try:
        alerts = client.get(f"/alerts?include_read={'true' if include_read else 'false'}")
    except Exception as exc:
        api_error(exc)
        return
    if not alerts:
        st.success("All clear — no alerts to show.")
        return
    for item in alerts:
        left, right = st.columns([5, 1])
        with left:
            card(item["title"], item["message"], ("RESOLVED" if item["is_read"] else item["severity"].upper()), item["severity"])
        with right:
            if not item["is_read"] and st.button("Mark read", key=f"read_{item['id']}"):
                try:
                    client.patch(f"/alerts/{item['id']}/read")
                    st.rerun()
                except Exception as exc:
                    api_error(exc)

