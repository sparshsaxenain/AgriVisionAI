from __future__ import annotations

import streamlit as st
from PIL import Image

from frontend.components.ui import api_error, page_title
from frontend.utils.crop_catalog import is_model_supported
from frontend.utils.i18n import current_language, t


def _results(result: dict, client) -> None:
    localized = result.get("localized") or {}
    advisory = localized.get("advisory") or result["advisory"]
    display_name = localized.get("display_name", result["display_name"])
    confidence_label = localized.get("confidence_label", t(result["confidence_label"]))
    top_prediction_names = localized.get("top_prediction_names", [])
    if current_language() == "hi" and not localized:
        st.warning(t("Hindi advisory translation is unavailable. Check the NVIDIA NIM configuration."))
    st.markdown(f"### {t('AI Analysis')}")
    st.markdown(f"<div class='ag-card'><div class='ag-eyebrow'>{t('Detected condition')}</div><h2 style='margin:.35rem 0'>{display_name}</h2><b>{result['confidence']:.1%}</b> · {confidence_label}<br><br><span class='ag-chip {'critical' if result['severity'].lower() == 'high' else 'warning'}'>{t(result['severity'].title())} {t('severity')}</span></div>", unsafe_allow_html=True)
    st.progress(float(result["confidence"]), text=f"{t('Confidence')} {result['confidence']:.1%}")
    if result["confidence"] < .6:
        st.warning(t("This result is uncertain. Take another clear photo and ask an agricultural expert to verify it."))
    st.markdown(f"#### {t('What this means')}")
    st.write(advisory["description"])
    with st.expander(t("Top predictions")):
        for index, item in enumerate(result["top_predictions"]):
            prediction_name = top_prediction_names[index] if index < len(top_prediction_names) else item["display_name"]
            st.write(f"{prediction_name} — {item['confidence']:.1%}")
    st.markdown(f"#### {t('Immediate Actions')}")
    for action in advisory["recommended_actions"]:
        st.markdown(f"- {action}")
    st.markdown(f"#### {t('Prevention')}")
    for action in advisory["preventive_measures"]:
        st.markdown(f"- {action}")
    st.info(f"**{t('When to seek help:')}** {advisory['when_to_contact_expert']}\n\n**{t('Urgency:')}** {advisory['urgency']}")
    st.caption(advisory["safety_note"])
    if st.button(f"💾 {t('Save Diagnosis')}", type="primary", width="stretch"):
        payload = {
            "farm_id": st.session_state.diagnosis_context["farm_id"],
            "crop_id": st.session_state.diagnosis_context["crop_id"],
            "image_token": result["image_token"], "predicted_class": result["predicted_class"],
            "display_name": result["display_name"], "confidence": result["confidence"],
            "severity": result["severity"], "advisory": dict(result["advisory"]), "model_version": result["model_version"],
        }
        if localized:
            payload["advisory"]["_localizations"] = {current_language(): localized["advisory"]}
            payload["advisory"]["_display_names"] = {current_language(): localized["display_name"]}
        try:
            saved = client.post("/diagnosis/save", json=payload)
            st.success(t("Diagnosis #{id} saved. It is now in Diagnosis History.", id=saved["id"]))
            st.session_state.pop("diagnosis_result", None)
        except Exception as exc:
            api_error(exc)


def render(client) -> None:
    page_title("Check Crop", "Take or upload a clear photo of the affected leaf")
    try:
        farms = client.get("/farms")
        crops = client.get("/crops")
        supported_types = client.get("/diagnosis/supported-crops")
    except Exception as exc:
        api_error(exc)
        return
    if not farms or not crops:
        st.info(t("Add a farm and active crop before checking a plant."))
        return
    left, right = st.columns([1, 1.05], gap="large")
    with left:
        st.markdown(f"### {t('Upload Crop Image')}")
        st.caption(t("Image model crop types: {types}", types=", ".join(supported_types)))
        farm_map = {farm["farm_name"]: farm for farm in farms}
        selected_farm_name = st.selectbox(t("Farm"), list(farm_map))
        farm = farm_map[selected_farm_name]
        farm_crops = [
            crop for crop in crops
            if crop["farm_id"] == farm["id"]
            and crop["status"] == "Active"
            and is_model_supported(crop["crop_name"], supported_types)
        ]
        crop_map = {f"{crop['crop_name']} · {crop['crop_stage']}": crop for crop in farm_crops}
        if not crop_map:
            st.warning(t("This farm has no active crop matching the image model's supported crop list."))
            return
        selected_crop_name = st.selectbox(t("Crop"), list(crop_map))
        crop = crop_map[selected_crop_name]
        uploaded = st.file_uploader(t("Leaf or crop photo"), type=["jpg", "jpeg", "png"], help=t("Maximum 8 MB. A close, well-lit image works best."))
        if uploaded:
            try:
                preview = Image.open(uploaded)
                st.image(preview, caption=t("Image preview"), width="stretch")
                uploaded.seek(0)
            except Exception:
                st.error(t("This image could not be previewed. Please choose another file."))
        if st.button(f"🔎 {t('Analyze Crop')}", type="primary", disabled=uploaded is None, width="stretch"):
            try:
                with st.spinner(t("Checking the crop image…")):
                    result = client.post(
                        "/diagnosis/predict", data={"farm_id": farm["id"], "crop_id": crop["id"], "language": current_language()},
                        files={"image": (uploaded.name, uploaded.getvalue(), uploaded.type)},
                    )
                st.session_state.diagnosis_result = result
                st.session_state.diagnosis_context = {"farm_id": farm["id"], "crop_id": crop["id"]}
            except Exception as exc:
                api_error(exc)
    with right:
        result = st.session_state.get("diagnosis_result")
        if result:
            _results(result, client)
        else:
            st.markdown(f"### {t('AI Analysis')}")
            st.markdown(f"<div class='ag-card' style='min-height:260px;display:flex;align-items:center;justify-content:center;text-align:center'><div><div style='font-size:3rem'>🌱</div><h3>{t('Your crop result appears here')}</h3><div class='ag-muted'>{t('Choose a crop, add a clear image, and tap Analyze Crop.')}</div></div></div>", unsafe_allow_html=True)
