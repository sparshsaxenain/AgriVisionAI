from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from frontend.components.ui import api_error, card, page_title


def render(client) -> None:
    page_title("Farm Records", "Manage farms and crop cycles")
    try:
        farms = client.get("/farms")
        crops = client.get("/crops")
        supported_crop_types = client.get("/diagnosis/supported-crops")
    except Exception as exc:
        api_error(exc)
        return
    farm_tab, crop_tab = st.tabs(["🏡 Farms", "🌾 Crop Cycles"])
    with farm_tab:
        for farm in farms:
            card(farm["farm_name"], f"{farm['village']}, {farm['district']} · {farm['total_area']:g} {farm['area_unit']} · {farm['soil_type']}", farm["status"])
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
                    c5, c6, c7 = st.columns(3)
                    farm_status = c5.text_input("Status", value=selected["status"])
                    latitude = c6.number_input("Latitude", value=selected["latitude"], format="%.6f", placeholder="Not set")
                    longitude = c7.number_input("Longitude", value=selected["longitude"], format="%.6f", placeholder="Not set")
                    if st.form_submit_button("Update Farm", width="stretch"):
                        try:
                            client.patch(f"/farms/{selected['id']}", json={"farm_name": name, "village": village, "district": district, "state": state, "latitude": latitude, "longitude": longitude, "total_area": area, "area_unit": unit, "soil_type": soil, "irrigation_type": irrigation, "status": farm_status})
                            st.success("Farm updated.")
                            st.rerun()
                        except Exception as exc:
                            api_error(exc)
            with st.expander("Delete farm"):
                selected_delete = st.selectbox("Farm to delete", farms, format_func=lambda item: item["farm_name"], key="delete_farm_choice")
                st.warning("Deleting a farm permanently removes its crop cycles, diagnoses, livestock, health records, and related alerts.")
                with st.form("delete_farm"):
                    confirmation = st.text_input(f"Type {selected_delete['farm_name']} to confirm")
                    if st.form_submit_button("Delete Farm", width="stretch", disabled=confirmation != selected_delete["farm_name"]):
                        try:
                            client.delete(f"/farms/{selected_delete['id']}", params={"confirm_name": confirmation})
                            st.success("Farm and dependent records deleted.")
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
        if not supported_crop_types:
            st.error("No crop types are available in knowledge/crop_diseases.json.")
        if crops and supported_crop_types:
            with st.expander("Edit crop cycle"):
                selected_crop = st.selectbox(
                    "Crop cycle",
                    crops,
                    format_func=lambda item: f"{item['crop_name']} · {farm_names.get(item['farm_id'], 'Unknown farm')} · #{item['id']}",
                    key="edit_crop_choice",
                )
                if selected_crop["crop_name"] not in supported_crop_types:
                    st.warning("This older record uses an unsupported crop type. Select a catalog crop before updating it.")
                farm_index = next(
                    (index for index, farm in enumerate(farms) if farm["id"] == selected_crop["farm_id"]),
                    0,
                )
                crop_index = (
                    supported_crop_types.index(selected_crop["crop_name"])
                    if selected_crop["crop_name"] in supported_crop_types
                    else 0
                )
                with st.form("edit_crop"):
                    edit_farm = st.selectbox(
                        "Farm",
                        farms,
                        index=farm_index,
                        format_func=lambda item: item["farm_name"],
                    )
                    c1, c2 = st.columns(2)
                    edit_crop_name = c1.selectbox("Crop type", supported_crop_types, index=crop_index)
                    edit_variety = c2.text_input("Variety", value=selected_crop["variety"])
                    c3, c4 = st.columns(2)
                    edit_sowing = c3.date_input(
                        "Sowing date",
                        value=date.fromisoformat(selected_crop["sowing_date"]) if selected_crop["sowing_date"] else None,
                    )
                    edit_harvest = c4.date_input(
                        "Expected harvest",
                        value=date.fromisoformat(selected_crop["expected_harvest_date"])
                        if selected_crop["expected_harvest_date"]
                        else None,
                    )
                    c5, c6, c7 = st.columns(3)
                    edit_area = c5.number_input(
                        "Area", min_value=0.0, value=float(selected_crop["area"]), step=.25
                    )
                    stages = ["Seedling", "Vegetative", "Flowering", "Fruiting", "Harvesting", "Completed"]
                    if selected_crop["crop_stage"] not in stages:
                        stages.append(selected_crop["crop_stage"])
                    edit_stage = c6.selectbox("Stage", stages, index=stages.index(selected_crop["crop_stage"]))
                    statuses = ["Active", "Completed", "Inactive"]
                    if selected_crop["status"] not in statuses:
                        statuses.append(selected_crop["status"])
                    edit_status = c7.selectbox("Status", statuses, index=statuses.index(selected_crop["status"]))
                    edit_notes = st.text_area("Notes", value=selected_crop["notes"])
                    if st.form_submit_button("Update Crop Cycle", width="stretch"):
                        try:
                            client.patch(
                                f"/crops/{selected_crop['id']}",
                                json={
                                    "farm_id": edit_farm["id"],
                                    "crop_name": edit_crop_name,
                                    "variety": edit_variety,
                                    "sowing_date": edit_sowing.isoformat() if edit_sowing else None,
                                    "expected_harvest_date": edit_harvest.isoformat() if edit_harvest else None,
                                    "area": edit_area,
                                    "crop_stage": edit_stage,
                                    "status": edit_status,
                                    "notes": edit_notes,
                                },
                            )
                            st.success("Crop cycle updated.")
                            st.rerun()
                        except Exception as exc:
                            api_error(exc)
        if crops:
            with st.expander("Delete crop cycle"):
                selected_delete_crop = st.selectbox(
                    "Crop cycle to delete",
                    crops,
                    format_func=lambda item: f"{item['crop_name']} · {farm_names.get(item['farm_id'], 'Unknown farm')} · #{item['id']}",
                    key="delete_crop_choice",
                )
                st.warning("Deleting a crop cycle permanently removes its saved diagnoses, retained images, and related alerts.")
                with st.form("delete_crop"):
                    crop_confirmation = st.text_input(f"Type {selected_delete_crop['crop_name']} to confirm")
                    if st.form_submit_button(
                        "Delete Crop Cycle",
                        width="stretch",
                        disabled=crop_confirmation != selected_delete_crop["crop_name"],
                    ):
                        try:
                            client.delete(
                                f"/crops/{selected_delete_crop['id']}",
                                params={"confirm_name": crop_confirmation},
                            )
                            st.success("Crop cycle and dependent records deleted.")
                            st.rerun()
                        except Exception as exc:
                            api_error(exc)
        if farms and supported_crop_types:
            with st.expander("＋ Add crop cycle"):
                with st.form("add_crop", clear_on_submit=True):
                    farm_map = {farm["farm_name"]: farm["id"] for farm in farms}
                    farm_name = st.selectbox("Farm", list(farm_map))
                    c1, c2 = st.columns(2)
                    crop_name = c1.selectbox("Crop type", supported_crop_types)
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
