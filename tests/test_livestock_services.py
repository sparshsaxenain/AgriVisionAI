from datetime import date, timedelta

from backend.services.livestock_health import LivestockHealthEngine
from backend.services.vaccination_service import due_text, vaccination_status


def test_scripted_high_risk_observation():
    risk = LivestockHealthEngine().evaluate({"temperature": 40.2, "appetite": "Low", "activity_level": "Low", "respiration": "Normal", "diarrhea": False, "visible_injury": False, "coughing": False, "nasal_discharge": False})
    assert risk["risk_score"] == 7
    assert risk["risk_level"] == "high"
    assert risk["triggered_rules"] == ["high_temperature", "reduced_appetite", "low_activity"]


def test_vaccination_status_windows():
    today = date(2026, 8, 13)
    assert vaccination_status(today - timedelta(days=2), today) == "Overdue"
    assert vaccination_status(today + timedelta(days=5), today) == "Due Soon"
    assert vaccination_status(today + timedelta(days=20), today) == "Upcoming"
    assert due_text(today - timedelta(days=2), today) == "Overdue by 2 days"

