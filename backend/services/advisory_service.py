"""Structured, offline crop advisory generation."""
from __future__ import annotations

import json
from copy import deepcopy

from backend.core.config import get_settings


class AdvisoryService:
    def __init__(self) -> None:
        root = get_settings().knowledge_dir
        self.diseases = json.loads((root / "crop_diseases.json").read_text(encoding="utf-8"))
        self.config = json.loads((root / "crop_advisories.json").read_text(encoding="utf-8"))

    @staticmethod
    def normalize_label(label: str) -> str:
        aliases = {
            "tomato early blight": "Tomato___Early_blight",
            "tomato_early_blight": "Tomato___Early_blight",
            "early_blight": "Tomato___Early_blight",
        }
        return aliases.get(label.strip().lower(), label)

    def build(self, predicted_class: str, confidence: float, crop_name: str = "", crop_stage: str = "", is_ood: bool = False) -> dict:
        # --- OOD advisory: image is not a recognized crop leaf ---
        if is_ood:
            return {
                "display_name": "Unrecognized Image",
                "condition": "Unrecognized Image",
                "confidence_label": "Unable to diagnose",
                "severity": "unknown",
                "description": (
                    "The uploaded image does not appear to be a plant leaf that our system "
                    "can analyze. Our model currently supports disease detection for: "
                    "Apple, Blueberry, Cherry, Corn, Grape, Orange, Peach, Pepper, "
                    "Potato, Raspberry, Soybean, Squash, Strawberry, and Tomato."
                ),
                "recommended_actions": [
                    "Please upload a clear, close-up photo of a single plant leaf.",
                    "Make sure the leaf fills most of the image frame.",
                    "Ensure good lighting and avoid blurry or dark images.",
                    "If your crop is not in the supported list, please consult a local agricultural expert.",
                ],
                "when_to_contact_expert": (
                    "Our system cannot diagnose this image. Please consult an agricultural "
                    "extension officer or plant pathologist for assistance."
                ),
                "crop_context": crop_name,
                "stage_context": crop_stage,
                "safety_note": self.config["safety_note"],
            }

        label = self.normalize_label(predicted_class)
        advice = deepcopy(self.diseases.get(label, self.diseases["default"]))
        high = self.config["confidence_thresholds"]["high"]
        moderate = self.config["confidence_thresholds"]["moderate"]
        if confidence >= high:
            confidence_label = "High confidence"
        elif confidence >= moderate:
            confidence_label = "Moderate confidence"
        else:
            confidence_label = "Low confidence — expert verification recommended"
            advice["recommended_actions"].insert(0, self.config["low_confidence_message"])
            advice["when_to_contact_expert"] = "Please ask an agricultural expert to verify this low-confidence result."
        advice.update({
            "condition": advice["display_name"],
            "confidence_label": confidence_label,
            "crop_context": crop_name,
            "stage_context": crop_stage,
            "safety_note": self.config["safety_note"],
        })
        return advice

