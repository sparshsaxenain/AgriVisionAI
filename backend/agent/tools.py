"""Typed tools that map natural-language intentions to AgriVision REST calls."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.agent.api_client import AgentAPIClient


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(ToolArgs):
    pass


class ListCropsArgs(ToolArgs):
    farm_id: int | None = Field(default=None, description="Farm ID to filter by; omit to list every crop.")


class ListAlertsArgs(ToolArgs):
    include_read: bool = Field(default=False, description="Whether already-read alerts should also be returned.")


class AnimalIdArgs(ToolArgs):
    animal_id: int = Field(description="The numeric livestock ID returned by list_animals.")


class CreateFarmArgs(ToolArgs):
    farm_name: str
    village: str = ""
    district: str = ""
    state: str = ""
    latitude: float | None = None
    longitude: float | None = None
    total_area: float = Field(default=0, ge=0)
    area_unit: str = "acres"
    soil_type: str = "Unknown"
    irrigation_type: str = "Rainfed"


class CreateCropArgs(ToolArgs):
    farm_id: int
    crop_name: str
    variety: str = ""
    sowing_date: date | None = None
    expected_harvest_date: date | None = None
    area: float = Field(default=0, ge=0)
    crop_stage: str = "Seedling"
    status: str = "Active"
    notes: str = ""


class RegisterAnimalArgs(ToolArgs):
    farm_id: int
    animal_type: str
    tag_id: str
    breed: str = ""
    name: str = ""
    sex: str = "Unknown"
    date_of_birth: date | None = None
    weight: float | None = Field(default=None, ge=0)
    status: str = "Healthy"
    notes: str = ""


class ObservationArgs(ToolArgs):
    animal_id: int
    temperature: float | None = Field(default=None, ge=30, le=45)
    appetite: str = "Normal"
    water_intake: str = "Normal"
    activity_level: str = "Normal"
    milk_production: float | None = Field(default=None, ge=0)
    respiration: str = "Normal"
    weight: float | None = Field(default=None, ge=0)
    visible_injury: bool = False
    diarrhea: bool = False
    coughing: bool = False
    nasal_discharge: bool = False
    pregnancy_status: str = "Not applicable"
    notes: str = ""


class MedicalRecordArgs(ToolArgs):
    animal_id: int
    record_type: str
    title: str
    description: str = ""
    date: date
    next_due_date: date | None = None
    veterinarian: str = ""
    notes: str = ""


class VaccinationArgs(ToolArgs):
    animal_id: int
    vaccine_name: str
    due_date: date
    administered_date: date | None = None
    status: str = "Upcoming"
    veterinarian: str = ""
    notes: str = ""


class MarkAlertArgs(ToolArgs):
    alert_id: int


ToolHandler = Callable[[AgentAPIClient, ToolArgs], Any]


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    args_schema: type[ToolArgs]
    handler: ToolHandler
    mutates_data: bool = False

    def run(self, arguments: dict[str, Any], api: AgentAPIClient) -> Any:
        validated = self.args_schema.model_validate(arguments)
        return self.handler(api, validated)

    def catalog_entry(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments_schema": self.args_schema.model_json_schema(),
            "changes_data": self.mutates_data,
        }


def _payload(args: ToolArgs, *, exclude: set[str] | None = None) -> dict[str, Any]:
    return args.model_dump(mode="json", exclude=exclude or set(), exclude_none=True)


def _no_args_get(path: str) -> ToolHandler:
    def call(api: AgentAPIClient, _: ToolArgs) -> Any:
        return api.get(path)

    return call


def _list_crops(api: AgentAPIClient, args: ToolArgs) -> Any:
    values = ListCropsArgs.model_validate(args)
    params = {"farm_id": values.farm_id} if values.farm_id is not None else None
    return api.get("/crops", params=params)


def _list_alerts(api: AgentAPIClient, args: ToolArgs) -> Any:
    values = ListAlertsArgs.model_validate(args)
    return api.get("/alerts", params={"include_read": values.include_read})


def _animal_get(suffix: str) -> ToolHandler:
    def call(api: AgentAPIClient, args: ToolArgs) -> Any:
        values = AnimalIdArgs.model_validate(args)
        return api.get(f"/livestock/{values.animal_id}/{suffix}")

    return call


def _create(path: str, excluded: set[str] | None = None) -> ToolHandler:
    def call(api: AgentAPIClient, args: ToolArgs) -> Any:
        return api.post(path, _payload(args, exclude=excluded))

    return call


def _animal_post(suffix: str) -> ToolHandler:
    def call(api: AgentAPIClient, args: ToolArgs) -> Any:
        animal_id = getattr(args, "animal_id")
        return api.post(f"/livestock/{animal_id}/{suffix}", _payload(args, exclude={"animal_id"}))

    return call


def _mark_alert(api: AgentAPIClient, args: ToolArgs) -> Any:
    values = MarkAlertArgs.model_validate(args)
    return api.patch(f"/alerts/{values.alert_id}/read")


TOOLS: tuple[AgentTool, ...] = (
    AgentTool("get_dashboard", "Get KPI totals, recent diagnoses, vaccinations, and active alerts.", NoArgs, _no_args_get("/dashboard/summary")),
    AgentTool("list_farms", "List the signed-in farmer's farms and their numeric IDs.", NoArgs, _no_args_get("/farms")),
    AgentTool("list_crops", "List crops, optionally for one farm. Use this to resolve crop IDs and current stages.", ListCropsArgs, _list_crops),
    AgentTool("list_animals", "List livestock with names, tags, status, farm, and numeric animal IDs.", NoArgs, _no_args_get("/livestock")),
    AgentTool("get_health_history", "Get saved health observations and risk scores for one animal.", AnimalIdArgs, _animal_get("health-history")),
    AgentTool("get_medical_records", "Get the medical timeline for one animal.", AnimalIdArgs, _animal_get("medical-records")),
    AgentTool("get_vaccinations", "Get vaccination history, due dates, and current status for one animal.", AnimalIdArgs, _animal_get("vaccinations")),
    AgentTool("list_alerts", "List active alerts; optionally include alerts already marked read.", ListAlertsArgs, _list_alerts),
    AgentTool("get_diagnosis_history", "List the farmer's saved crop-disease screening history.", NoArgs, _no_args_get("/diagnosis/history")),
    AgentTool("create_farm", "Create a farm only when the user clearly asks to add one and supplied its name.", CreateFarmArgs, _create("/farms"), True),
    AgentTool("create_crop", "Add a crop cycle to an existing farm. Resolve the farm ID first.", CreateCropArgs, _create("/crops"), True),
    AgentTool("register_animal", "Register livestock on an existing farm. A unique tag ID is required.", RegisterAnimalArgs, _create("/livestock"), True),
    AgentTool("record_health_observation", "Save animal symptoms/vitals and run the API's explainable health-risk rules.", ObservationArgs, _animal_post("observation"), True),
    AgentTool("add_medical_record", "Add a dated treatment, checkup, illness, or other medical record for an animal.", MedicalRecordArgs, _animal_post("medical-record"), True),
    AgentTool("add_vaccination", "Record a completed or scheduled vaccination for an animal.", VaccinationArgs, _animal_post("vaccination"), True),
    AgentTool("mark_alert_read", "Mark one alert as read when the user clearly requests it.", MarkAlertArgs, _mark_alert, True),
)

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
ActionName = Literal[
    "get_dashboard", "list_farms", "list_crops", "list_animals", "get_health_history",
    "get_medical_records", "get_vaccinations", "list_alerts", "get_diagnosis_history",
    "create_farm", "create_crop", "register_animal", "record_health_observation",
    "add_medical_record", "add_vaccination", "mark_alert_read", "finish",
]
