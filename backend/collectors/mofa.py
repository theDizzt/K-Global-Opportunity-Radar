# 0. 모듈 불러오기
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from backend.repositories.collection_repository import (
    CollectionRepository,
    CountryAlias,
    SourceDocument,
)
from backend.repositories.country_repository import CountryRepository
from config.settings import DATABASE_PATH, MOFA_COLLECTION_LIMIT, MOFA_SPARQL_TIMEOUT


# 1. 외교부 LOD 데이터셋별 엔드포인트와 속성 설정
DATASETS = {
    "mofadaily": {
        "endpoint": "https://opendata.mofa.go.kr/mofadaily/sparql",
        "relation": "http://opendata.mofa.go.kr/mofadaily/relatedDaily",
        "date": "http://opendata.mofa.go.kr/mofadaily/startDate",
    },
    "mofapress": {
        "endpoint": "https://opendata.mofa.go.kr/mofapress/sparql",
        "relation": "http://opendata.mofa.go.kr/mofapress/relatedPress",
        "date": "http://opendata.mofa.go.kr/mofabrief/postingDate",
    },
}

FIELD_KEYWORDS = {
    "교육": ("교육", "대학", "학교", "교원", "직업훈련", "인재양성", "장학"),
    "보건": ("보건", "의료", "건강", "감염병", "백신", "병원", "방역"),
    "디지털": ("디지털", "ICT", "정보통신", "전자정부", "인공지능", "AI", "스마트시티"),
    "기후·환경": ("기후", "환경", "탄소", "녹색", "산림", "대기오염", "재생에너지"),
    "문화·한류": ("문화", "한류", "한국어", "콘텐츠", "예술", "관광"),
    "청년취업": ("청년", "고용", "취업", "창업", "일자리", "직업교육"),
}


# 2. 한 번의 수집 실행 결과
@dataclass(frozen=True)
class CollectionResult:
    countries: int
    documents: int
    datasets: tuple[str, ...]
    collected_at: str


# 3. 외교부 SPARQL 데이터를 조회하고 SQLite에 적재하는 수집기
class MofaCollector:
    # 3.1. HTTP 클라이언트와 저장소 준비
    def __init__(self, database_path=DATABASE_PATH, client=None):
        self.repository = CollectionRepository(database_path)
        self.country_repository = CountryRepository(database_path)
        self.client = client or httpx.Client(
            timeout=MOFA_SPARQL_TIMEOUT,
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )
        self._owns_client = client is None

    # 3.1.1. 수집기가 직접 생성한 HTTP 클라이언트 종료
    def close(self):
        if self._owns_client:
            self.client.close()

    # 3.1.2. with 문 진입 시 현재 수집기 반환
    def __enter__(self):
        return self

    # 3.1.3. with 문 종료 시 HTTP 자원 정리
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    # 3.2. 국가 마스터와 선택한 외교 자료를 순서대로 수집
    def collect(self, iso3_codes=None, datasets=("mofadaily", "mofapress"), limit=None):
        selected_datasets = tuple(datasets)
        unknown = set(selected_datasets) - set(DATASETS)
        if unknown:
            raise ValueError(f"지원하지 않는 외교부 데이터셋: {', '.join(sorted(unknown))}")

        limit = limit or MOFA_COLLECTION_LIMIT
        collected_at = datetime.now(timezone.utc).isoformat()
        target_iso3 = {
            code.upper()
            for code in (
                iso3_codes or [country.iso3 for country in self.country_repository.list_all()]
            )
        }

        try:
            aliases = self._collect_country_aliases(target_iso3, collected_at)
            documents = []
            for dataset_code in selected_datasets:
                # 국가마다 동일한 최대 건수를 적용해 특정 국가가 결과를 독점하지 않게 합니다.
                for alias in aliases:
                    documents.extend(
                        self._collect_documents(dataset_code, [alias], collected_at, limit)
                    )
            self.repository.log_collection(
                "MOFA",
                collected_at,
                "success",
                len(documents),
                f"외교부 LOD 수집 완료: {', '.join(selected_datasets)}",
            )
            return CollectionResult(
                countries=len(aliases),
                documents=len(documents),
                datasets=selected_datasets,
                collected_at=collected_at,
            )
        except Exception as error:
            self.repository.log_collection(
                "MOFA",
                collected_at,
                "failed",
                0,
                f"{type(error).__name__}: {error}",
            )
            raise

    # 3.3. 외교부 국가 URI·ISO2·ISO3 매핑 수집
    def _collect_country_aliases(self, target_iso3, collected_at):
        query = """
        SELECT ?country ?iso3 ?iso2 ?label WHERE {
          ?country <http://opendata.mofa.go.kr/core/hasISO_3CD> ?iso3 .
          ?country <http://opendata.mofa.go.kr/core/hasISO_2CD> ?iso2 .
          ?country <http://www.w3.org/2000/01/rdf-schema#label> ?label .
        }
        """
        payload, raw_id = self._request("mofadaily", "core", query, collected_at)
        aliases = []
        for binding in _bindings(payload):
            iso3 = _value(binding, "iso3").upper()
            if iso3 not in target_iso3:
                continue
            aliases.append(
                CountryAlias(
                    iso3=iso3,
                    source_uri=_value(binding, "country"),
                    source_code=_value(binding, "iso2"),
                    label=_value(binding, "label"),
                )
            )
        if target_iso3 - {alias.iso3 for alias in aliases}:
            missing = ", ".join(sorted(target_iso3 - {alias.iso3 for alias in aliases}))
            raise LookupError(f"외교부 국가 매핑을 찾지 못했습니다: {missing}")
        self.repository.upsert_country_aliases("MOFA", aliases, collected_at)
        return aliases

    # 3.4. 국가별 외교일지 또는 보도자료 수집
    def _collect_documents(self, dataset_code, aliases, collected_at, limit):
        config = DATASETS[dataset_code]
        country_values = " ".join(f"<{alias.source_uri}>" for alias in aliases)
        query = f"""
        SELECT DISTINCT ?country ?document ?title ?summary ?date ?year ?dataURL WHERE {{
          VALUES ?country {{ {country_values} }}
          ?country <{config['relation']}> ?document .
          ?document <http://www.w3.org/2000/01/rdf-schema#label> ?title .
          OPTIONAL {{ ?document <http://purl.org/ontology/bibo/abstract> ?summary . }}
          OPTIONAL {{ ?document <{config['date']}> ?date . }}
          OPTIONAL {{ ?document <http://opendata.mofa.go.kr/core/yearOfData> ?year . }}
          OPTIONAL {{ ?document <http://opendata.mofa.go.kr/mofapub/dataURL> ?dataURL . }}
        }}
        ORDER BY DESC(?date) DESC(?year)
        LIMIT {int(limit)}
        """
        payload, raw_id = self._request(dataset_code, dataset_code, query, collected_at)
        alias_by_uri = {alias.source_uri: alias for alias in aliases}
        documents = []
        for binding in _bindings(payload):
            country_uri = _value(binding, "country")
            alias = alias_by_uri.get(country_uri)
            if alias is None:
                continue
            title = _clean_literal(_value(binding, "title"))
            summary = _clean_literal(_value(binding, "summary"))
            document_uri = _value(binding, "document")
            data_url = _clean_literal(_value(binding, "dataURL"))
            published_date = _normalize_date(
                _clean_literal(_value(binding, "date")),
                _clean_literal(_value(binding, "year")),
            )
            documents.append(
                SourceDocument(
                    uri=document_uri,
                    dataset_code=dataset_code,
                    title=title,
                    summary=summary,
                    published_date=published_date,
                    source_url=data_url if data_url.startswith("http") else document_uri,
                    primary_field=classify_field(f"{title} {summary}"),
                    country_iso3=alias.iso3,
                )
            )
        self.repository.upsert_documents("MOFA", documents, collected_at, raw_id)
        return documents

    # 3.5. SPARQL GET 요청과 원본 JSON 저장
    def _request(self, endpoint_dataset, stored_dataset, query, requested_at):
        endpoint = DATASETS[endpoint_dataset]["endpoint"]
        # 외교부 엔드포인트는 GET 요청과 application/json 형식을 사용합니다.
        query = query.strip()
        response = self.client.get(endpoint, params={"query": query})
        response.raise_for_status()
        payload = response.json()
        raw_id = self.repository.save_raw_payload(
            "MOFA",
            stored_dataset,
            requested_at,
            endpoint,
            query,
            response.status_code,
            json.dumps(payload, ensure_ascii=False),
        )
        return payload, raw_id


# 4. SPARQL JSON과 비표준 리터럴 값을 정규화하는 보조 함수
# 4.1. SPARQL 응답에서 결과 행 목록 추출
def _bindings(payload):
    return payload.get("results", {}).get("bindings", [])


# 4.2. SPARQL 결과 행에서 지정한 속성값 추출
def _value(binding, key):
    return binding.get(key, {}).get("value", "")


# 4.3. null 문자열과 비표준 타입 리터럴 제거
def _clean_literal(value):
    value = value.strip()
    if value.lower() == "null":
        return ""
    typed_literal = re.fullmatch(r'"(.*)"\^\^[^\s]+', value, flags=re.DOTALL)
    return typed_literal.group(1) if typed_literal else value


# 4.4. 날짜 또는 연도 값을 YYYY-MM-DD 형식으로 통일
def _normalize_date(date_value, year_value):
    digits = re.sub(r"\D", "", date_value)
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    year_digits = re.sub(r"\D", "", year_value)
    if len(year_digits) >= 4:
        return f"{year_digits[:4]}-01-01"
    return None


# 4.5. 제목과 요약의 키워드 빈도로 대표 협력 분야 분류
def classify_field(text):
    normalized = text.casefold()
    scores = {
        field: sum(normalized.count(keyword.casefold()) for keyword in keywords)
        for field, keywords in FIELD_KEYWORDS.items()
    }
    best_field, best_score = max(scores.items(), key=lambda item: item[1])
    return best_field if best_score > 0 else "외교 일반"
