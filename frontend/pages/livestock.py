from __future__ import annotations

import json
from datetime import date, timedelta

import streamlit as st

from frontend.components.ui import api_error, card, page_title


def _add_animal(client, farms: list[dict]) -> None:
    with st.expander("＋ Add animal"):
        with st.form("add_animal", clear_on_submit=True):
            farm_map = {f["farm_name"]: f["id"] for f in farms}
            farm_name = st.selectbox("Farm", list(farm_map))
            c1, c2 = st.columns(2)
            animal_type = c1.selectbox("Animal type", ["Cow", "Buffalo", "Goat", "Sheep", "Poultry", "Other"])
            breed = c2.text_input("Breed")
            c3, c4 = st.columns(2)
            tag = c3.text_input("Tag ID")
            name = c4.text_input("Name")
            c5, c6 = st.columns(2)
            sex = c5.selectbox("Sex", ["Female", "Male", "Unknown"])
            weight = c6.number_input("Weight (kg)", min_value=0.0, step=1.0)
            born = st.date_input("Date of birth", value=date.today() - timedelta(days=365))
            if st.form_submit_button("Save Animal", width="stretch"):
                try:
                    client.post("/livestock", json={"farm_id": farm_map[farm_name], "animal_type": animal_type, "breed": breed, "tag_id": tag, "name": name, "sex": sex, "date_of_birth": born.isoformat(), "weight": weight, "status": "Healthy"})
                    st.success("Animal saved.")
                    st.rerun()
                except Exception as exc:
                    api_error(exc)


def _health_tab(client, animal: dict) -> None:
    st.caption("This tool provides preliminary guidance and does not replace a qualified veterinarian.")
    with st.form(f"health_{animal['id']}"):
        c1, c2, c3 = st.columns(3)
        temperature = c1.number_input("Temperature (°C)", min_value=30.0, max_value=45.0, value=38.5, step=.1)
        appetite = c2.selectbox("Appetite", ["Normal", "Low", "None"])
        activity = c3.selectbox("Activity", ["Normal", "Low", "Very low"])
        c4, c5 = st.columns(2)
        water = c4.selectbox("Water intake", ["Normal", "Low", "High"])
        respiration = c5.selectbox("Breathing", ["Normal", "Fast", "Labored"])
        s1, s2, s3, s4 = st.columns(4)
        injury = s1.checkbox("Visible injury")
        diarrhea = s2.checkbox("Diarrhea")
        coughing = s3.checkbox("Coughing")
        discharge = s4.checkbox("Nasal discharge")
        notes = st.text_area("Notes")
        if st.form_submit_button("Evaluate & Save Health Check", width="stretch"):
            try:
                result = client.post(f"/livestock/{animal['id']}/observation", json={"temperature": temperature, "appetite": appetite, "water_intake": water, "activity_level": activity, "respiration": respiration, "visible_injury": injury, "diarrhea": diarrhea, "coughing": coughing, "nasal_discharge": discharge, "notes": notes})
                st.session_state[f"risk_{animal['id']}"] = result
                st.success("Health check saved and alerts updated.")
            except Exception as exc:
                api_error(exc)
    result = st.session_state.get(f"risk_{animal['id']}")
    if result:
        level = result["risk_level"].title()
        message = "Possible fever, infection, injury, or respiratory indicators. Veterinary consultation recommended." if level == "High" else "Continue observation and consult a veterinarian if symptoms persist or worsen."
        if level == "High":
            st.error(f"**Health Risk: {level}** · Score {result['risk_score']}\n\n{message}")
        elif level == "Moderate":
            st.warning(f"**Health Risk: {level}** · Score {result['risk_score']}\n\n{message}")
        else:
            st.success(f"**Health Risk: {level}** · Score {result['risk_score']}\n\n{message}")
    try:
        history = client.get(f"/livestock/{animal['id']}/health-history")
        if history:
            st.markdown("#### Previous checks")
            st.dataframe([{"Date": x["created_at"][:10], "Temperature": x["temperature"], "Appetite": x["appetite"], "Risk": x["risk_level"].title()} for x in history], width="stretch", hide_index=True)
    except Exception as exc:
        api_error(exc)


def _records_tab(client, animal: dict) -> None:
    with st.form(f"medical_{animal['id']}", clear_on_submit=True):
        record_type = st.selectbox("Record type", ["Vaccination", "Medication", "Veterinary visit", "Illness", "Injury", "Pregnancy", "Deworming", "Other"])
        title = st.text_input("Title")
        description = st.text_area("Description")
        c1, c2 = st.columns(2)
        record_date = c1.date_input("Date", value=date.today())
        veterinarian = c2.text_input("Veterinarian (optional)")
        if st.form_submit_button("Save Medical Record", width="stretch"):
            try:
                client.post(f"/livestock/{animal['id']}/medical-record", json={"record_type": record_type, "title": title, "description": description, "date": record_date.isoformat(), "veterinarian": veterinarian})
                st.success("Medical record saved.")
                st.rerun()
            except Exception as exc:
                api_error(exc)
    try:
        records = client.get(f"/livestock/{animal['id']}/medical-records")
        for record in records:
            card(record["title"], f"{record['date']} · {record['record_type']} · {record['description']}", record["record_type"])
    except Exception as exc:
        api_error(exc)


def _vaccination_tab(client, animal: dict) -> None:
    with st.form(f"vaccine_{animal['id']}", clear_on_submit=True):
        name = st.text_input("Vaccination or preventive task")
        due = st.date_input("Due date", value=date.today() + timedelta(days=30))
        notes = st.text_input("Notes")
        if st.form_submit_button("Add Reminder", width="stretch"):
            try:
                client.post(f"/livestock/{animal['id']}/vaccination", json={"vaccine_name": name, "due_date": due.isoformat(), "notes": notes})
                st.success("Vaccination reminder saved.")
                st.rerun()
            except Exception as exc:
                api_error(exc)
    try:
        records = client.get(f"/livestock/{animal['id']}/vaccinations")
        for item in records:
            card(item["vaccine_name"], f"Due {item['due_date']} · {item['notes']}", item["status"], "critical" if item["status"] == "Overdue" else "warning")
    except Exception as exc:
        api_error(exc)


def render(client) -> None:
    page_title("Animals & Health", "Animal records, preliminary health screening, and care reminders")
    try:
        animals = client.get("/livestock")
        farms = client.get("/farms")
    except Exception as exc:
        api_error(exc)
        return
    if farms:
        _add_animal(client, farms)
    if not animals:
        st.info("No animals recorded yet.")
        return
    st.markdown("### Your Animals")
    cols = st.columns(3)
    for index, animal in enumerate(animals):
        with cols[index % 3]:
            card(animal["name"] or animal["tag_id"], f"{animal['animal_type']} · Tag {animal['tag_id']} · {animal['breed']}", animal["status"], "warning" if animal["status"] != "Healthy" else "")
    animal = st.selectbox("View animal", animals, format_func=lambda item: f"{item['name'] or item['tag_id']} · {item['animal_type']} · {item['tag_id']}")
    if not animal:
        return
    st.markdown(f"## {animal['name'] or animal['tag_id']}")
    st.caption(f"{animal['animal_type']} · {animal['breed']} · Tag {animal['tag_id']} · {animal['weight'] or '—'} kg")
    overview, health, records, vaccines = st.tabs(["Overview", "Health Observations", "Medical Records", "Vaccinations"])
    with overview:
        st.markdown(f"**Status:** {animal['status']}  \n**Sex:** {animal['sex']}  \n**Born:** {animal['date_of_birth'] or 'Not recorded'}  \n**Notes:** {animal['notes'] or '—'}")
        with st.expander("✏️ Edit animal"):
            with st.form(f"edit_animal_{animal['id']}"):
                farm_ids = [farm["id"] for farm in farms]
                selected_farm_id = st.selectbox(
                    "Farm",
                    farm_ids,
                    index=farm_ids.index(animal["farm_id"]) if animal["farm_id"] in farm_ids else 0,
                    format_func=lambda farm_id: next(farm["farm_name"] for farm in farms if farm["id"] == farm_id),
                )
                c1, c2 = st.columns(2)
                name = c1.text_input("Name", value=animal["name"])
                breed = c2.text_input("Breed", value=animal["breed"])
                c3, c4 = st.columns(2)
                weight = c3.number_input("Weight (kg)", min_value=0.0, value=float(animal["weight"] or 0), step=1.0)
                status = c4.selectbox("Status", ["Healthy", "Needs attention", "Under treatment", "Sold", "Deceased"], index=["Healthy", "Needs attention", "Under treatment", "Sold", "Deceased"].index(animal["status"]) if animal["status"] in ["Healthy", "Needs attention", "Under treatment", "Sold", "Deceased"] else 0)
                c5, c6 = st.columns(2)
                animal_types = ["Cow", "Buffalo", "Goat", "Sheep", "Poultry", "Other"]
                animal_type = c5.selectbox("Animal type", animal_types, index=animal_types.index(animal["animal_type"]) if animal["animal_type"] in animal_types else len(animal_types) - 1)
                tag_id = c6.text_input("Tag ID", value=animal["tag_id"])
                c7, c8 = st.columns(2)
                sexes = ["Female", "Male", "Unknown"]
                sex = c7.selectbox("Sex", sexes, index=sexes.index(animal["sex"]) if animal["sex"] in sexes else 2)
                born_value = date.fromisoformat(animal["date_of_birth"]) if animal["date_of_birth"] else date.today()
                born = c8.date_input("Date of birth", value=born_value)
                notes = st.text_area("Notes", value=animal["notes"])
                if st.form_submit_button("Update Animal", width="stretch"):
                    try:
                        client.patch(f"/livestock/{animal['id']}", json={"farm_id": selected_farm_id, "animal_type": animal_type, "breed": breed, "tag_id": tag_id, "name": name, "sex": sex, "date_of_birth": born.isoformat(), "weight": weight, "status": status, "notes": notes})
                        st.success("Animal updated.")
                        st.rerun()
                    except Exception as exc:
                        api_error(exc)
        with st.expander("Delete animal"):
            st.warning("This permanently removes the animal, health observations, medical records, vaccinations, and related alerts.")
            with st.form(f"delete_animal_{animal['id']}"):
                confirmation = st.text_input(f"Type tag {animal['tag_id']} to confirm")
                if st.form_submit_button("Delete Animal", width="stretch", disabled=confirmation != animal["tag_id"]):
                    try:
                        client.delete(f"/livestock/{animal['id']}", params={"confirm_tag_id": confirmation})
                        st.success("Animal and dependent records deleted.")
                        st.rerun()
                    except Exception as exc:
                        api_error(exc)
    with health:
        _health_tab(client, animal)
    with records:
        _records_tab(client, animal)
    with vaccines:
        _vaccination_tab(client, animal)
