from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from frontend.components.ui import api_error, card, page_title


def render(client) -> None:
    page_title("Farm Records", "Manage farms and crop cycles")
    try:
        farms = client.get("/farms")
        crops = client.get("/crops")
    except Exception as exc:
        api_error(exc)
        return
    farm_tab, crop_tab = st.tabs(["🏡 Farms", "🌾 Crop Cycles"])
    with farm_tab:
        for farm in farms:
            card(farm["farm_name"], f"{farm['village']}, {farm['district']} · {farm['total_area']:g} {farm['area_unit']} · {farm['soil_type']}", farm["irrigation_type"])
        if farms:
            with st.expander("✏️ Edit farm"):
                selected = st.selectbox("Choose farm", farms, format_func=lambda item: item["farm_name"], key="edit_farm_choice")
                with st.form("edit_farm"):
                    name = st.text_input("Farm name", value=selected["farm_name"])
                    village = st.text_input("Village", value=selected["village"])
                    c1, c2 = st.columns(2)
                    district = c1.text_input("District", value=selected["district"])
                    state = c2.text_input("State", value=selected["state"])
                    c3, c4 = st.columns(2)
                    area = c3.number_input("Total area", min_value=0.0, value=float(selected["total_area"]), step=.25)
                    unit_options = ["acres", "hectares"]
                    unit = c4.selectbox("Area unit", unit_options, index=unit_options.index(selected["area_unit"]) if selected["area_unit"] in unit_options else 0)
                    soil = st.text_input("Soil type", value=selected["soil_type"])
                    irrigation = st.text_input("Irrigation", value=selected["irrigation_type"])
                    if st.form_submit_button("Update Farm", width="stretch"):
                        try:
                            client.put(f"/farms/{selected['id']}", json={"farm_name": name, "village": village, "district": district, "state": state, "latitude": selected["latitude"], "longitude": selected["longitude"], "total_area": area, "area_unit": unit, "soil_type": soil, "irrigation_type": irrigation})
                            st.success("Farm updated.")
                            st.rerun()
                        except Exception as exc:
                            api_error(exc)
        with st.expander("＋ Add farm"):
            with st.form("add_farm", clear_on_submit=True):
                name = st.text_input("Farm name")
                village = st.text_input("Village")
                c1, c2 = st.columns(2)
                district = c1.text_input("District")
                state = c2.text_input("State")
                c3, c4 = st.columns(2)
                area = c3.number_input("Total area", min_value=0.0, step=.25)
                unit = c4.selectbox("Area unit", ["acres", "hectares"])
                c5, c6 = st.columns(2)
                soil = c5.selectbox("Soil type", ["Red loam", "Black", "Alluvial", "Sandy", "Clay", "Unknown"])
                irrigation = c6.selectbox("Irrigation", ["Rainfed", "Drip", "Canal", "Borewell", "Sprinkler", "Other"])
                if st.form_submit_button("Save Farm", width="stretch"):
                    try:
                        client.post("/farms", json={"farm_name": name, "village": village, "district": district, "state": state, "total_area": area, "area_unit": unit, "soil_type": soil, "irrigation_type": irrigation})
                        st.success("Farm saved.")
                        st.rerun()
                    except Exception as exc:
                        api_error(exc)
    with crop_tab:
        farm_names = {farm["id"]: farm["farm_name"] for farm in farms}
        for crop in crops:
            card(crop["crop_name"], f"{farm_names.get(crop['farm_id'], '—')} · {crop['variety']} · {crop['area']:g} acres", crop["crop_stage"])
        if farms:
            with st.expander("＋ Add crop cycle"):
                with st.form("add_crop", clear_on_submit=True):
                    farm_map = {farm["farm_name"]: farm["id"] for farm in farms}
                    farm_name = st.selectbox("Farm", list(farm_map))
                    c1, c2 = st.columns(2)
                    crop_name = c1.text_input("Crop name")
                    variety = c2.text_input("Variety")
                    c3, c4 = st.columns(2)
                    sowing = c3.date_input("Sowing date", value=date.today())
                    harvest = c4.date_input("Expected harvest", value=date.today() + timedelta(days=90))
                    c5, c6 = st.columns(2)
                    area = c5.number_input("Area", min_value=0.0, step=.25)
                    stage = c6.selectbox("Stage", ["Seedling", "Vegetative", "Flowering", "Fruiting", "Harvesting", "Completed"])
                    notes = st.text_area("Notes")
                    if st.form_submit_button("Save Crop", width="stretch"):
                        try:
                            client.post("/crops", json={"farm_id": farm_map[farm_name], "crop_name": crop_name, "variety": variety, "sowing_date": sowing.isoformat(), "expected_harvest_date": harvest.isoformat(), "area": area, "crop_stage": stage, "status": "Completed" if stage == "Completed" else "Active", "notes": notes})
                            st.success("Crop cycle saved.")
                            st.rerun()
                        except Exception as exc:
                            api_error(exc)
