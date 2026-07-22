from typing import Literal

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiModel):
    status: Literal["ok"]
    data_source: Literal["sqlite"]
    database_ready: bool


class OptionsResponse(ApiModel):
    personas: list[str]
    fields: list[str]
    regions: list[str]


class DataSourceItem(ApiModel):
    code: str
    name: str
    url: str
    description: str
