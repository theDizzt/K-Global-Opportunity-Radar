# 데이터 사전 초안

## 계층

| 계층 | 테이블 | 설명 |
|---|---|---|
| 원본 | `raw_api_response` | API·SPARQL 요청별 원문 응답과 요청 지문 |
| 실행 | `ingestion_run` | 수집 파라미터, 시작·종료 시각, 성공·실패, 처리 건수 |
| 표준 | `country`, `country_alias`, `sector`, `sector_mapping` | 국가와 8개 분야 표준 사전 |
| 정제 | `source_record`, `project`, `country_profile`, `kf_partner_org` | 검색·분석 가능한 정제 레코드 |
| 다중분야 | `record_sector` | 하나의 원문에 연결되는 기본·보조 분야 태그 |
| 근거 | `evidence`, `safety_notice` | 추천 설명과 위험 표시에 사용하는 근거 |
| 품질·계보 | `record_lineage`, `data_quality_issue`, `source_coverage` | 원본 추적, 오류, 출처별 충족률 |
| 점수 | `score_snapshot`, `score_component` | 버전·기준일별 국가×분야 점수와 기여도 |

## 공통 필수 필드

| 필드 | 정의 |
|---|---|
| `source_type` | KOICA, KF, MOFA, LOD 중 제공 출처 구분 |
| `external_id` | 출처 내부 ID 또는 안정 해시 |
| `country_iso3` | ISO 3166-1 alpha-3 표준 국가코드 |
| `sector_code` | 8개 공통 분야 코드 |
| `published_at` | 원문 게시·발표일. 없으면 NULL |
| `collected_at` | 시스템 수집 시각 |
| `reference_date` | 통계·현황이 설명하는 자료 기준일 |
| `date_precision` | day, month, year, unknown |
| `source_url` | 사용자가 확인할 수 있는 원문·공식 명세 URL |
| `quality_status` | unreviewed, accepted, corrected, excluded |
