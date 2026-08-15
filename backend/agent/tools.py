"""Typed tools that map natural-language intentions to AgriVision REST calls."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.agent.api_client import AgentAPIClient
from backend.services.crop_catalog import canonical_crop_type, supported_crop_types


SUPPORTED_CROP_NAMES = ", ".join(supported_crop_types())


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
    status: str = "Active"


class UpdateFarmArgs(ToolArgs):
    farm_id: int
    farm_name: str | None = None
    village: str | None = None
    district: str | None = None
    state: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    total_area: float | None = Field(default=None, ge=0)
    area_unit: str | None = None
    soil_type: str | None = None
    irrigation_type: str | None = None
    status: str | None = None


class DeleteFarmArgs(ToolArgs):
    farm_id: int
    confirm_name: str = Field(description="Exact current farm name returned by list_farms.")


class CreateCropArgs(ToolArgs):
    farm_id: int
    crop_name: str = Field(description=f"A crop type from the disease catalog: {SUPPORTED_CROP_NAMES}.")
    variety: str = ""
    sowing_date: date | None = None
    expected_harvest_date: date | None = None
    area: float = Field(default=0, ge=0)
    crop_stage: str = "Seedling"
    status: str = "Active"
    notes: str = ""

    @field_validator("crop_name")
    @classmethod
    def crop_must_be_supported(cls, value: str) -> str:
        canonical = canonical_crop_type(value)
        if canonical is None:
            raise ValueError(f"Unsupported crop type. Choose one of: {SUPPORTED_CROP_NAMES}.")
        return canonical


class UpdateCropArgs(ToolArgs):
    crop_id: int
    farm_id: int | None = None
    crop_name: str | None = Field(default=None, description=f"A crop type from the disease catalog: {SUPPORTED_CROP_NAMES}.")
    variety: str | None = None
    sowing_date: date | None = None
    expected_harvest_date: date | None = None
    area: float | None = Field(default=None, ge=0)
    crop_stage: str | None = None
    status: str | None = None
    notes: str | None = None

    @field_validator("crop_name")
    @classmethod
    def crop_must_be_supported(cls, value: str | None) -> str | None:
        if value is None:
            return None
        canonical = canonical_crop_type(value)
        if canonical is None:
            raise ValueError(f"Unsupported crop type. Choose one of: {SUPPORTED_CROP_NAMES}.")
        return canonical


class DeleteCropArgs(ToolArgs):
    crop_id: int
    confirm_name: str = Field(description="Exact current crop name returned by list_crops.")


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


class UpdateAnimalArgs(ToolArgs):
    animal_id: int
    farm_id: int | None = None
    animal_type: str | None = None
    breed: str | None = None
    tag_id: str | None = None
    name: str | None = None
    sex: str | None = None
    date_of_birth: date | None = None
    weight: float | None = Field(default=None, ge=0)
    status: str | None = None
    notes: str | None = None


class DeleteAnimalArgs(ToolArgs):
    animal_id: int
    confirm_tag_id: str = Field(description="Exact current tag ID returned by list_animals.")


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


def _payload(
    args: ToolArgs,
    *,
    exclude: set[str] | None = None,
    exclude_unset: bool = False,
) -> dict[str, Any]:
    return args.model_dump(
        mode="json",
        exclude=exclude or set(),
        exclude_none=not exclude_unset,
        exclude_unset=exclude_unset,
    )


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


def _update_farm(api: AgentAPIClient, args: ToolArgs) -> Any:
    values = UpdateFarmArgs.model_validate(args)
    return api.patch(f"/farms/{values.farm_id}", _payload(values, exclude={"farm_id"}, exclude_unset=True))


def _delete_farm(api: AgentAPIClient, args: ToolArgs) -> Any:
    values = DeleteFarmArgs.model_validate(args)
    api.delete(f"/farms/{values.farm_id}", params={"confirm_name": values.confirm_name})
    return {"deleted": True, "farm_id": values.farm_id, "farm_name": values.confirm_name}


def _update_crop(api: AgentAPIClient, args: ToolArgs) -> Any:
    values = UpdateCropArgs.model_validate(args)
    return api.patch(f"/crops/{values.crop_id}", _payload(values, exclude={"crop_id"}, exclude_unset=True))


def _delete_crop(api: AgentAPIClient, args: ToolArgs) -> Any:
    values = DeleteCropArgs.model_validate(args)
    api.delete(f"/crops/{values.crop_id}", params={"confirm_name": values.confirm_name})
    return {"deleted": True, "crop_id": values.crop_id, "crop_name": values.confirm_name}


def _update_animal(api: AgentAPIClient, args: ToolArgs) -> Any:
    values = UpdateAnimalArgs.model_validate(args)
    return api.patch(f"/livestock/{values.animal_id}", _payload(values, exclude={"animal_id"}, exclude_unset=True))


def _delete_animal(api: AgentAPIClient, args: ToolArgs) -> Any:
    values = DeleteAnimalArgs.model_validate(args)
    api.delete(f"/livestock/{values.animal_id}", params={"confirm_tag_id": values.confirm_tag_id})
    return {"deleted": True, "animal_id": values.animal_id, "tag_id": values.confirm_tag_id}


TOOLS: tuple[AgentTool, ...] = (
    AgentTool("get_dashboard", "Get KPI totals, recent diagnoses, vaccinations, and active alerts.", NoArgs, _no_args_get("/dashboard/summary")),
    AgentTool("list_farms", "List the signed-in farmer's farms and their numeric IDs.", NoArgs, _no_args_get("/farms")),
    AgentTool("list_crops", "List crops, optionally for one farm. Use this to resolve crop IDs and current stages.", ListCropsArgs, _list_crops),
    AgentTool("list_supported_crop_types", "List the only crop types that may be used when creating or renaming a crop cycle. This list comes from crop_diseases.json.", NoArgs, _no_args_get("/diagnosis/supported-crops")),
    AgentTool("list_animals", "List livestock with names, tags, status, farm, and numeric animal IDs.", NoArgs, _no_args_get("/livestock")),
    AgentTool("get_health_history", "Get saved health observations and risk scores for one animal.", AnimalIdArgs, _animal_get("health-history")),
    AgentTool("get_medical_records", "Get the medical timeline for one animal.", AnimalIdArgs, _animal_get("medical-records")),
    AgentTool("get_vaccinations", "Get vaccination history, due dates, and current status for one animal.", AnimalIdArgs, _animal_get("vaccinations")),
    AgentTool("list_due_vaccinations", "List every pending vaccination across all of the farmer's animals. Use this for broad questions such as 'what vaccinations are due?' without asking for an animal.", NoArgs, _no_args_get("/livestock/vaccinations/due")),
    AgentTool("list_alerts", "List active alerts; optionally include alerts already marked read.", ListAlertsArgs, _list_alerts),
    AgentTool("get_diagnosis_history", "List the farmer's saved crop-disease screening history.", NoArgs, _no_args_get("/diagnosis/history")),
    AgentTool("create_farm", "Create a farm only when the user clearly asks to add one and supplied its name.", CreateFarmArgs, _create("/farms"), True),
    AgentTool("update_farm", "Change only specified farm properties, including name, location, area, soil, irrigation, or status. Resolve the farm ID first.", UpdateFarmArgs, _update_farm, True),
    AgentTool("delete_farm", "Permanently delete a farm and its dependent crop/livestock records only when explicitly requested. Resolve the ID and exact current name first.", DeleteFarmArgs, _delete_farm, True),
    AgentTool("create_crop", "Add a crop cycle to an existing farm using only a crop type from list_supported_crop_types. Resolve the farm ID first.", CreateCropArgs, _create("/crops"), True),
    AgentTool("update_crop", "Change only specified crop-cycle properties. Resolve the crop ID first; crop names must come from list_supported_crop_types.", UpdateCropArgs, _update_crop, True),
    AgentTool("delete_crop", "Permanently delete one crop cycle and its diagnoses/alerts only when explicitly requested. Resolve its ID and exact current crop name first.", DeleteCropArgs, _delete_crop, True),
    AgentTool("register_animal", "Register livestock on an existing farm. A unique tag ID is required.", RegisterAnimalArgs, _create("/livestock"), True),
    AgentTool("update_animal", "Change only specified livestock properties. Resolve the animal ID first.", UpdateAnimalArgs, _update_animal, True),
    AgentTool("delete_animal", "Permanently delete one animal and its dependent health records only when explicitly requested. Resolve its ID and exact tag first.", DeleteAnimalArgs, _delete_animal, True),
    AgentTool("record_health_observation", "Save animal symptoms/vitals and run the API's explainable health-risk rules.", ObservationArgs, _animal_post("observation"), True),
    AgentTool("add_medical_record", "Add a dated treatment, checkup, illness, or other medical record for an animal.", MedicalRecordArgs, _animal_post("medical-record"), True),
    AgentTool("add_vaccination", "Record a completed or scheduled vaccination for an animal.", VaccinationArgs, _animal_post("vaccination"), True),
    AgentTool("mark_alert_read", "Mark one alert as read when the user clearly requests it.", MarkAlertArgs, _mark_alert, True),
)

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
ActionName = Literal[
    "get_dashboard", "list_farms", "list_crops", "list_supported_crop_types", "list_animals", "get_health_history",
    "get_medical_records", "get_vaccinations", "list_due_vaccinations", "list_alerts", "get_diagnosis_history",
    "create_farm", "update_farm", "delete_farm", "create_crop", "update_crop", "delete_crop", "register_animal",
    "update_animal", "delete_animal", "record_health_observation",
    "add_medical_record", "add_vaccination", "mark_alert_read", "finish",
]
