"""Central alert creation helpers."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Alert, CropDiagnosis, Livestock


def create_crop_alerts(db: Session, diagnosis: CropDiagnosis) -> list[Alert]:
    alerts: list[Alert] = []
    if diagnosis.severity.lower() == "high":
        alerts.append(Alert(farmer_id=diagnosis.farmer_id, type="crop", severity="critical", title=f"High-severity {diagnosis.display_name}", message="Inspect the affected crop and seek local agricultural guidance promptly.", related_entity="diagnosis", related_entity_id=diagnosis.id))
    elif diagnosis.confidence >= 0.8 and diagnosis.severity.lower() != "low":
        alerts.append(Alert(farmer_id=diagnosis.farmer_id, type="crop", severity="warning", title=f"{diagnosis.display_name} detected", message=f"Detected with {diagnosis.confidence:.0%} confidence. Review recommended actions.", related_entity="diagnosis", related_entity_id=diagnosis.id))
    if diagnosis.confidence < 0.6:
        alerts.append(Alert(farmer_id=diagnosis.farmer_id, type="crop", severity="warning", title="Crop result needs verification", message="The image result had low confidence. Please consult an agricultural expert.", related_entity="diagnosis", related_entity_id=diagnosis.id))
    previous = db.scalar(select(CropDiagnosis).where(CropDiagnosis.crop_id == diagnosis.crop_id, CropDiagnosis.predicted_class == diagnosis.predicted_class, CropDiagnosis.id != diagnosis.id).limit(1))
    if previous:
        alerts.append(Alert(farmer_id=diagnosis.farmer_id, type="crop", severity="warning", title="Repeated crop issue", message=f"{diagnosis.display_name} has been recorded more than once for this crop cycle.", related_entity="crop", related_entity_id=diagnosis.crop_id))
    db.add_all(alerts)
    return alerts


def create_health_alert(db: Session, animal: Livestock, risk: dict) -> Alert | None:
    if risk["risk_level"] not in {"moderate", "high"}:
        return None
    severity = "critical" if risk["risk_level"] == "high" else "warning"
    alert = Alert(farmer_id=animal.farmer_id, type="livestock", severity=severity, title=f"{animal.name or animal.tag_id} needs attention", message=f"{animal.animal_type} #{animal.tag_id} shows {risk['risk_level']}-risk health indicators.", related_entity="livestock", related_entity_id=animal.id)
    db.add(alert)
    return alert

