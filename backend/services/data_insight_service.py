# 0. 모듈 불러오기
from collections import defaultdict

from backend.models.data_insight import (
    CollectionStatusResponse,
    CountryDataQualityResponse,
    CountrySignalsResponse,
    RawSignalPoint,
    SourceDocumentItem,
)
from backend.repositories.data_insight_repository import data_insight_repository


# 1. 산식 버전과 자료종류별 협력 신호 가중치
FORMULA_VERSION = "mofa-raw-v1"
DATASET_WEIGHTS = {"mofadaily": 1.0, "mofapress": 1.5}
FORMULA_NOTICE = (
    "외교일지 1.0, 보도자료 1.5를 기본 가중치로 사용하고 선택 분야 일치 문서는 1.5배, "
    "외교 일반은 0.5배, 다른 분야는 0.25배를 적용한 검증 전 원시지표입니다. "
    "최종 기회점수에는 반영되지 않습니다."
)


# 2. 외교부 데이터의 최근 수집 결과와 현재 적재량 구성
def build_collection_status():
    record = data_insight_repository.get_collection_status("MOFA")
    return CollectionStatusResponse(
        source_code="MOFA",
        latest_collected_at=record.collected_at,
        latest_status=record.status,
        latest_record_count=record.record_count,
        latest_message=record.message,
        stored_documents=record.stored_documents,
        covered_countries=record.covered_countries,
        datasets=record.datasets,
    )


# 3. 누락률과 일반 분류 비중을 포함한 국가별 품질 보고서 구성
def build_country_quality(iso3: str):
    record = data_insight_repository.get_quality(iso3)
    total = record.total_documents
    date_completeness = _percentage(record.dated_documents, total)
    summary_completeness = _percentage(record.summarized_documents, total)
    general_count = record.fields.get("외교 일반", 0)
    warnings = []

    if total == 0:
        warnings.append("수집된 실제 문서가 없어 시범 데이터로 대체됩니다.")
    if total and date_completeness < 90:
        warnings.append("기준일이 없는 문서가 10%를 초과합니다.")
    if total and summary_completeness < 70:
        warnings.append("요약문이 없는 문서가 30%를 초과합니다.")
    if total and _percentage(general_count, total) >= 50:
        warnings.append("외교 일반 분류가 절반 이상이므로 분야 키워드 보완이 필요합니다.")
    if record.shared_documents:
        warnings.append("여러 국가에 함께 연결된 문서는 국가별 단독 협력으로 해석하면 안 됩니다.")

    return CountryDataQualityResponse(
        country_iso3=iso3,
        total_documents=total,
        dated_documents=record.dated_documents,
        summarized_documents=record.summarized_documents,
        shared_documents=record.shared_documents,
        date_completeness=date_completeness,
        summary_completeness=summary_completeness,
        datasets=record.datasets,
        fields=record.fields,
        warnings=warnings,
    )


# 4. 검토 화면에서 사용할 국가·분야별 최신 근거 문서 구성
def build_source_documents(iso3: str, field: str | None, limit: int):
    return [
        SourceDocumentItem(**vars(record))
        for record in data_insight_repository.list_documents(iso3, field, limit)
    ]


# 5. 수집 문서 빈도에서 연도별 협력 신호와 정책 정합성 원시지표 계산
def build_country_signals(iso3: str, field):
    yearly = defaultdict(list)
    for record in data_insight_repository.get_signal_aggregates(iso3):
        yearly[record.year].append(record)

    points = []
    for year, records in sorted(yearly.items()):
        document_count = sum(record.document_count for record in records)
        matched_count = sum(
            record.document_count for record in records if record.primary_field == field.value
        )
        base_weight = sum(
            DATASET_WEIGHTS.get(record.dataset_code, 1.0) * record.document_count
            for record in records
        )
        cooperation_signal = sum(
            DATASET_WEIGHTS.get(record.dataset_code, 1.0)
            * _relevance_weight(record.primary_field, field.value)
            * record.document_count
            for record in records
        )
        matched_weight = sum(
            DATASET_WEIGHTS.get(record.dataset_code, 1.0) * record.document_count
            for record in records
            if record.primary_field == field.value
        )
        points.append(
            RawSignalPoint(
                year=year,
                document_count=document_count,
                matched_document_count=matched_count,
                cooperation_signal=round(cooperation_signal, 2),
                policy_alignment=_percentage(matched_weight, base_weight),
            )
        )

    return CountrySignalsResponse(
        country_iso3=iso3,
        field=field,
        formula_version=FORMULA_VERSION,
        formula_notice=FORMULA_NOTICE,
        points=points,
    )


# 6. 비율과 분야 일치 가중치를 계산하는 보조 함수
def _percentage(numerator: float, denominator: float):
    return round(numerator / denominator * 100, 1) if denominator else 0.0


# 6.1. 문서 분야와 요청 분야의 관계에 따라 가중치 결정
def _relevance_weight(document_field: str, requested_field: str):
    if document_field == requested_field:
        return 1.5
    if document_field == "외교 일반":
        return 0.5
    return 0.25
