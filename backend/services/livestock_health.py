"""Data-driven, explainable preliminary livestock health screening."""
from __future__ import annotations

import json
from typing import Any

from backend.core.config import get_settings


class LivestockHealthEngine:
    def __init__(self) -> None:
        path = get_settings().knowledge_dir / "livestock_rules.json"
        self.config = json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _matches(actual: Any, operator: str, expected: Any) -> bool:
        if actual is None:
            return False
        return {
            ">=": lambda: actual >= expected,
            ">": lambda: actual > expected,
            "<=": lambda: actual <= expected,
            "==": lambda: actual == expected,
            "!=": lambda: actual != expected,
            "in": lambda: actual in expected,
        }[operator]()

    def evaluate(self, observation: dict[str, Any]) -> dict[str, Any]:
        triggered = []
        score = 0
        explanations = []
        for rule in self.config["rules"]:
            if self._matches(observation.get(rule["field"]), rule["operator"], rule["value"]):
                triggered.append(rule["id"])
                score += int(rule["score"])
                explanations.append(rule["message"])
        levels = self.config["risk_levels"]
        level = "low" if score <= levels["low_max"] else "moderate" if score <= levels["moderate_max"] else "high"
        return {
            "risk_score": score,
            "risk_level": level,
            "triggered_rules": triggered,
            "explanations": explanations,
            "recommendations": self.config["recommendations"][level],
            "disclaimer": "This tool provides preliminary guidance and does not replace a qualified veterinarian.",
        }

