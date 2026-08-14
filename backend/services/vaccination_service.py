"""Data-driven vaccination status and reminder calculations."""
import json
from datetime import date
from functools import lru_cache

from backend.core.config import get_settings


@lru_cache
def _due_soon_days() -> int:
    path = get_settings().knowledge_dir / "vaccination_rules.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    return int(config["status_windows"]["due_soon_days"])


def vaccination_status(due_date: date, today: date | None = None) -> str:
    today = today or date.today()
    days = (due_date - today).days
    if days < 0:
        return "Overdue"
    if days <= _due_soon_days():
        return "Due Soon"
    return "Upcoming"


def due_text(due_date: date, today: date | None = None) -> str:
    today = today or date.today()
    days = (due_date - today).days
    if days < 0:
        return f"Overdue by {abs(days)} day{'s' if abs(days) != 1 else ''}"
    if days == 0:
        return "Due today"
    return f"Due in {days} day{'s' if days != 1 else ''}"
