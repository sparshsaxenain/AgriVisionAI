"""AgriVision AI Streamlit application."""
from __future__ import annotations

import streamlit as st

from frontend.components.ui import api_error, apply_theme
from frontend.pages import alerts, assistant, crop_diagnosis, crop_history, dashboard, farm_records, livestock
from frontend.utils.api_client import APIClient
from frontend.utils.i18n import t

st.set_page_config(page_title="AgriVision AI", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")
apply_theme()

LANGUAGE_CODES = {"English": "en", "हिन्दी": "hi", "தமிழ்": "ta"}


def login_screen() -> None:
    left, center, right = st.columns([1, 1.15, 1])
    with center:
        current_language = st.session_state.get("language", "en")
        language_name = st.selectbox(
            "Language / भाषा / மொழி",
            list(LANGUAGE_CODES),
            index=list(LANGUAGE_CODES.values()).index(current_language) if current_language in LANGUAGE_CODES.values() else 0,
        )
        language = LANGUAGE_CODES[language_name]
        st.session_state.language = language
        st.markdown(
            "<div style='height:2vh'></div><div class='ag-card' style='padding:1.8rem'>"
            "<div style='font-size:3rem'>🌿</div><h1>AgriVision AI</h1>"
            f"<p class='ag-muted'>{t('One farmer, one application—complete crop and livestock health visibility.', language)}</p>",
            unsafe_allow_html=True,
        )
        login_tab, register_tab = st.tabs([t("Sign In", language), t("Create Account", language)])
        with login_tab:
            with st.form("login"):
                identifier = st.text_input(t("Email or phone", language), value="farmer@example.com")
                password = st.text_input(t("Password", language), type="password", value="demo123")
                submitted = st.form_submit_button(t("Sign In", language), width="stretch")
            if submitted:
                try:
                    result = APIClient().post("/auth/login", json={"identifier": identifier, "password": password})
                    st.session_state.token = result["access_token"]
                    st.session_state.user = result["user"]
                    st.rerun()
                except Exception as exc:
                    api_error(exc)
            st.caption(t("Demo account: farmer@example.com · password: demo123", language))
        with register_tab:
            with st.form("register"):
                name = st.text_input(t("Your name", language))
                phone = st.text_input(t("Phone", language))
                email = st.text_input(t("Email (optional)", language))
                password = st.text_input(t("Create password", language), type="password")
                village = st.text_input(t("Village", language))
                submitted = st.form_submit_button(t("Create Account", language), width="stretch")
            if submitted:
                try:
                    result = APIClient().post("/auth/register", json={"name": name, "phone": phone, "email": email or None, "password": password, "village": village, "preferred_language": language})
                    st.session_state.token = result["access_token"]
                    st.session_state.user = result["user"]
                    st.rerun()
                except Exception as exc:
                    api_error(exc)
        st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    if "token" not in st.session_state:
        login_screen()
        return
    user = st.session_state.user
    with st.sidebar:
        st.markdown("# 🌿 AgriVision AI")
        selected_language = st.session_state.get("language", user.get("preferred_language", "en"))
        language_name = st.selectbox("Language / भाषा / மொழி", list(LANGUAGE_CODES), index=list(LANGUAGE_CODES.values()).index(selected_language) if selected_language in LANGUAGE_CODES.values() else 0)
        language = LANGUAGE_CODES[language_name]
        previous_language = st.session_state.get("rendered_language")
        if previous_language and previous_language != language:
            for key in ("agent_messages", "agent_thread_id", "diagnosis_result", "diagnosis_context"):
                st.session_state.pop(key, None)
        st.session_state.language = language
        st.session_state.rendered_language = language
        st.caption(f"{t('welcome', language)}, {user['name']}")
        pages = {
            t("ai_assistant", language): "AI Assistant", t("dashboard", language): "Dashboard", t("check_crop", language): "Check Crop",
            t("diagnosis_history", language): "Diagnosis History", t("animals", language): "Animals & Health",
            t("farm_records", language): "Farm Records", t("alerts", language): "Alerts",
        }
        current = st.session_state.get("page", "Dashboard")
        display_current = next((label for label, value in pages.items() if value == current), next(iter(pages)))
        selection = st.radio(t("Navigation", language), list(pages), index=list(pages).index(display_current), label_visibility="collapsed")
        st.session_state.page = pages[selection]
        st.divider()
        st.caption(t("Local-first · Requires internet for NVIDIA NIM", language))
        if st.button(f"↩ {t('logout', language)}", width="stretch"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    client = APIClient(st.session_state.token)
    renderers = {"AI Assistant": assistant.render, "Dashboard": dashboard.render, "Check Crop": crop_diagnosis.render, "Diagnosis History": crop_history.render, "Animals & Health": livestock.render, "Farm Records": farm_records.render, "Alerts": alerts.render}
    renderers[st.session_state.page](client)


if __name__ == "__main__":
    main()
