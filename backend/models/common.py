# 0. 모듈 불러오기
from typing import Literal

from pydantic import BaseModel, ConfigDict


# 1. 모든 API 모델에 적용하는 공통 검증 설정
class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# 2. 서버 상태 확인 응답 모델
class HealthResponse(ApiModel):
    status: Literal["ok"]
    data_source: Literal["sqlite"]
    database_ready: bool


# 3. 화면 선택 항목 응답 모델
class OptionsResponse(ApiModel):
    personas: list[str]
    fields: list[str]
    regions: list[str]


# 4. 공공데이터 제공기관 응답 모델
class DataSourceItem(ApiModel):
    code: str
    name: str
    url: str
    description: str
