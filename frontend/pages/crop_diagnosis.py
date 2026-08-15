from __future__ import annotations

import streamlit as st
from PIL import Image

from frontend.components.ui import api_error, page_title
from frontend.utils.crop_catalog import is_model_supported


def _results(result: dict, client) -> None:
    advisory = result["advisory"]
    st.markdown("### AI Analysis")
    st.markdown(f"<div class='ag-card'><div class='ag-eyebrow'>Detected condition</div><h2 style='margin:.35rem 0'>{result['display_name']}</h2><b>{result['confidence']:.1%}</b> · {result['confidence_label']}<br><br><span class='ag-chip {'critical' if result['severity'].lower() == 'high' else 'warning'}'>{result['severity'].title()} severity</span></div>", unsafe_allow_html=True)
    st.progress(float(result["confidence"]), text=f"Confidence {result['confidence']:.1%}")
    if result["confidence"] < .6:
        st.warning("This result is uncertain. Take another clear photo and ask an agricultural expert to verify it.")
    st.markdown("#### What this means")
    st.write(advisory["description"])
    with st.expander("Top predictions"):
        for item in result["top_predictions"]:
            st.write(f"{item['display_name']} — {item['confidence']:.1%}")
    st.markdown("#### Immediate Actions")
    for action in advisory["recommended_actions"]:
        st.markdown(f"- {action}")
    st.markdown("#### Prevention")
    for action in advisory["preventive_measures"]:
        st.markdown(f"- {action}")
    st.info(f"**When to seek help:** {advisory['when_to_contact_expert']}\n\n**Urgency:** {advisory['urgency']}")
    st.caption(advisory["safety_note"])
    if st.button("💾 Save Diagnosis", type="primary", width="stretch"):
        payload = {
            "farm_id": st.session_state.diagnosis_context["farm_id"],
            "crop_id": st.session_state.diagnosis_context["crop_id"],
            "image_token": result["image_token"], "predicted_class": result["predicted_class"],
            "display_name": result["display_name"], "confidence": result["confidence"],
            "severity": result["severity"], "advisory": advisory, "model_version": result["model_version"],
        }
        try:
            saved = client.post("/diagnosis/save", json=payload)
            st.success(f"Diagnosis #{saved['id']} saved. It is now in Diagnosis History.")
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
        st.info("Add a farm and active crop before checking a plant.")
        return
    left, right = st.columns([1, 1.05], gap="large")
    with left:
        st.markdown("### Upload Crop Image")
        st.caption("Image model crop types: " + ", ".join(supported_types))
        farm_map = {farm["farm_name"]: farm for farm in farms}
        selected_farm_name = st.selectbox("Farm", list(farm_map))
        farm = farm_map[selected_farm_name]
        farm_crops = [
            crop for crop in crops
            if crop["farm_id"] == farm["id"]
            and crop["status"] == "Active"
            and is_model_supported(crop["crop_name"], supported_types)
        ]
        crop_map = {f"{crop['crop_name']} · {crop['crop_stage']}": crop for crop in farm_crops}
        if not crop_map:
            st.warning("This farm has no active crop matching the image model's supported crop list.")
            return
        selected_crop_name = st.selectbox("Crop", list(crop_map))
        crop = crop_map[selected_crop_name]
        uploaded = st.file_uploader("Leaf or crop photo", type=["jpg", "jpeg", "png"], help="Maximum 8 MB. A close, well-lit image works best.")
        if uploaded:
            try:
                preview = Image.open(uploaded)
                st.image(preview, caption="Image preview", width="stretch")
                uploaded.seek(0)
            except Exception:
                st.error("This image could not be previewed. Please choose another file.")
        if st.button("🔎 Analyze Crop", type="primary", disabled=uploaded is None, width="stretch"):
            try:
                with st.spinner("Checking the crop image…"):
                    result = client.post(
                        "/diagnosis/predict", data={"farm_id": farm["id"], "crop_id": crop["id"]},
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
            st.markdown("### AI Analysis")
            st.markdown("<div class='ag-card' style='min-height:260px;display:flex;align-items:center;justify-content:center;text-align:center'><div><div style='font-size:3rem'>🌱</div><h3>Your crop result appears here</h3><div class='ag-muted'>Choose a crop, add a clear image, and tap Analyze Crop.</div></div></div>", unsafe_allow_html=True)
