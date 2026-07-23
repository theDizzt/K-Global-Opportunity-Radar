-- 1. 공공데이터 제공기관의 코드·이름·원문 주소 관리
CREATE TABLE IF NOT EXISTS data_sources (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT NOT NULL
);

-- 2. 분석 대상 국가의 기본정보와 데이터 상태 관리
CREATE TABLE IF NOT EXISTS countries (
    iso3 TEXT PRIMARY KEY CHECK(length(iso3) = 3),
    name TEXT NOT NULL,
    english_name TEXT NOT NULL,
    region TEXT NOT NULL,
    flag TEXT NOT NULL,
    completeness INTEGER NOT NULL CHECK(completeness BETWEEN 0 AND 100),
    risk_level TEXT NOT NULL,
    risk_score INTEGER NOT NULL CHECK(risk_score BETWEEN 0 AND 100),
    reference_date TEXT NOT NULL,
    focus_fields TEXT NOT NULL,
    gap_opportunity TEXT NOT NULL,
    summary TEXT NOT NULL
);

-- 3. 국가별 기회점수 계산에 사용하는 원천 평가지표 관리
CREATE TABLE IF NOT EXISTS country_indicators (
    country_iso3 TEXT NOT NULL REFERENCES countries(iso3) ON DELETE CASCADE,
    code TEXT NOT NULL,
    value INTEGER NOT NULL CHECK(value BETWEEN 0 AND 100),
    PRIMARY KEY (country_iso3, code)
);

-- 4. 화면에 표시하는 국가별 연도 단위 협력 신호 관리
CREATE TABLE IF NOT EXISTS signal_history (
    country_iso3 TEXT NOT NULL REFERENCES countries(iso3) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
    PRIMARY KEY (country_iso3, year)
);

-- 5. 국가별 대표 프로젝트와 협력 대상·SDGs 정보 관리
CREATE TABLE IF NOT EXISTS projects (
    country_iso3 TEXT PRIMARY KEY REFERENCES countries(iso3) ON DELETE CASCADE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    partners TEXT NOT NULL,
    sdgs TEXT NOT NULL
);

-- 6. 국가별 우선순위가 있는 추천 협력 모델 관리
CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_iso3 TEXT NOT NULL REFERENCES countries(iso3) ON DELETE CASCADE,
    priority INTEGER NOT NULL,
    title TEXT NOT NULL,
    UNIQUE(country_iso3, priority)
);

-- 7. 분석 결과를 설명하는 시범 또는 실제 근거 관리
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_iso3 TEXT NOT NULL REFERENCES countries(iso3) ON DELETE CASCADE,
    source_code TEXT NOT NULL REFERENCES data_sources(code),
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    reference_date TEXT NOT NULL,
    is_demo INTEGER NOT NULL DEFAULT 1 CHECK(is_demo IN (0, 1))
);

-- 8. 국가별 주의 요인과 안전정보 출처 관리
CREATE TABLE IF NOT EXISTS risk_factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_iso3 TEXT NOT NULL REFERENCES countries(iso3) ON DELETE CASCADE,
    source_code TEXT NOT NULL REFERENCES data_sources(code),
    title TEXT NOT NULL,
    level TEXT NOT NULL,
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100)
);

-- 9. 기관별 데이터 수집 성공·실패 이력 관리
CREATE TABLE IF NOT EXISTS collection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code TEXT NOT NULL REFERENCES data_sources(code),
    collected_at TEXT NOT NULL,
    status TEXT NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0,
    message TEXT
);

-- 10. 재현과 감사에 사용할 SPARQL 원본 응답 보관
CREATE TABLE IF NOT EXISTS raw_source_payloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code TEXT NOT NULL REFERENCES data_sources(code),
    dataset_code TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    query_text TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);

-- 11. 외부 국가 URI와 내부 ISO3 국가 코드 연결
CREATE TABLE IF NOT EXISTS country_aliases (
    source_code TEXT NOT NULL REFERENCES data_sources(code),
    country_iso3 TEXT NOT NULL REFERENCES countries(iso3) ON DELETE CASCADE,
    source_country_uri TEXT NOT NULL,
    source_country_code TEXT,
    source_label TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source_code, country_iso3),
    UNIQUE (source_code, source_country_uri)
);

-- 12. 외부 자료에서 정제한 제목·요약·날짜·분야 정보 관리
CREATE TABLE IF NOT EXISTS source_documents (
    document_uri TEXT PRIMARY KEY,
    source_code TEXT NOT NULL REFERENCES data_sources(code),
    dataset_code TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    published_date TEXT,
    source_url TEXT NOT NULL,
    primary_field TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    raw_payload_id INTEGER REFERENCES raw_source_payloads(id) ON DELETE SET NULL
);

-- 13. 한 문서와 하나 이상의 관련 국가를 다대다로 연결
CREATE TABLE IF NOT EXISTS document_countries (
    document_uri TEXT NOT NULL REFERENCES source_documents(document_uri) ON DELETE CASCADE,
    country_iso3 TEXT NOT NULL REFERENCES countries(iso3) ON DELETE CASCADE,
    PRIMARY KEY (document_uri, country_iso3)
);

-- 14. 국가·근거·문서 조회 성능을 높이는 검색 인덱스
CREATE INDEX IF NOT EXISTS idx_countries_region ON countries(region);
CREATE INDEX IF NOT EXISTS idx_evidence_country ON evidence(country_iso3);
CREATE INDEX IF NOT EXISTS idx_risks_country ON risk_factors(country_iso3);
CREATE INDEX IF NOT EXISTS idx_documents_date ON source_documents(published_date);
CREATE INDEX IF NOT EXISTS idx_documents_field ON source_documents(primary_field);
CREATE INDEX IF NOT EXISTS idx_document_countries_country ON document_countries(country_iso3);
