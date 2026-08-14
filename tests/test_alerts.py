from backend.models import Crop, CropDiagnosis, Farm, User
from backend.services.alert_service import create_crop_alerts


def test_high_severity_diagnosis_generates_alert(db_session):
    user = User(name="A", phone="100000", password_hash="hash")
    db_session.add(user)
    db_session.flush()
    farm = Farm(farmer_id=user.id, farm_name="Farm")
    db_session.add(farm)
    db_session.flush()
    crop = Crop(farm_id=farm.id, crop_name="Potato")
    db_session.add(crop)
    db_session.flush()
    diagnosis = CropDiagnosis(farmer_id=user.id, farm_id=farm.id, crop_id=crop.id, predicted_class="Potato___Late_blight", display_name="Potato Late Blight", confidence=.9, severity="high", advisory="{}")
    db_session.add(diagnosis)
    db_session.flush()
    alerts = create_crop_alerts(db_session, diagnosis)
    assert any(alert.severity == "critical" for alert in alerts)

