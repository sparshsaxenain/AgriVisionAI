"""AgriVision AI Streamlit application."""
from __future__ import annotations

import streamlit as st

from frontend.components.ui import api_error, apply_theme
from frontend.pages import alerts, crop_diagnosis, crop_history, dashboard, farm_records, livestock
from frontend.utils.api_client import APIClient
from frontend.utils.i18n import t

st.set_page_config(page_title="AgriVision AI", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")
apply_theme()


def login_screen() -> None:
    left, center, right = st.columns([1, 1.15, 1])
    with center:
        st.markdown("<div style='height:8vh'></div><div class='ag-card' style='padding:1.8rem'><div style='font-size:3rem'>🌿</div><h1>AgriVision AI</h1><p class='ag-muted'>One farmer, one application—complete crop and livestock health visibility.</p>", unsafe_allow_html=True)
        login_tab, register_tab = st.tabs(["Sign In", "Create Account"])
        with login_tab:
            with st.form("login"):
                identifier = st.text_input("Email or phone", value="farmer@example.com")
                password = st.text_input("Password", type="password", value="demo123")
                submitted = st.form_submit_button("Sign In", width="stretch")
            if submitted:
                try:
                    result = APIClient().post("/auth/login", json={"identifier": identifier, "password": password})
                    st.session_state.token = result["access_token"]
                    st.session_state.user = result["user"]
                    st.rerun()
                except Exception as exc:
                    api_error(exc)
            st.caption("Demo account: farmer@example.com · password: demo123")
        with register_tab:
            with st.form("register"):
                name = st.text_input("Your name")
                phone = st.text_input("Phone")
                email = st.text_input("Email (optional)")
                password = st.text_input("Create password", type="password")
                village = st.text_input("Village")
                submitted = st.form_submit_button("Create Account", width="stretch")
            if submitted:
                try:
                    result = APIClient().post("/auth/register", json={"name": name, "phone": phone, "email": email or None, "password": password, "village": village})
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
    language_codes = {"English": "en", "हिन्दी": "hi", "தமிழ்": "ta"}
    with st.sidebar:
        st.markdown("# 🌿 AgriVision AI")
        st.caption(f"{t('welcome', user.get('preferred_language', 'en'))}, {user['name']}")
        language_name = st.selectbox("Language / भाषा / மொழி", list(language_codes), index=list(language_codes.values()).index(st.session_state.get("language", user.get("preferred_language", "en"))) if st.session_state.get("language", user.get("preferred_language", "en")) in language_codes.values() else 0)
        language = language_codes[language_name]
        st.session_state.language = language
        pages = {
            t("dashboard", language): "Dashboard", t("check_crop", language): "Check Crop",
            t("diagnosis_history", language): "Diagnosis History", t("animals", language): "Animals & Health",
            t("farm_records", language): "Farm Records", t("alerts", language): "Alerts",
        }
        current = st.session_state.get("page", "Dashboard")
        display_current = next((label for label, value in pages.items() if value == current), next(iter(pages)))
        selection = st.radio("Navigation", list(pages), index=list(pages).index(display_current), label_visibility="collapsed")
        st.session_state.page = pages[selection]
        st.divider()
        st.caption("Local-first · Works without internet")
        if st.button(f"↩ {t('logout', language)}", width="stretch"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    client = APIClient(st.session_state.token)
    renderers = {"Dashboard": dashboard.render, "Check Crop": crop_diagnosis.render, "Diagnosis History": crop_history.render, "Animals & Health": livestock.render, "Farm Records": farm_records.render, "Alerts": alerts.render}
    renderers[st.session_state.page](client)


if __name__ == "__main__":
    main()
