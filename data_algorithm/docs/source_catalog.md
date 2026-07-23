# 데이터 출처 목록 및 사용 판단

확인 기준일: 2026-07-21

| 코드 | 제공기관 | 데이터 | 제공 방식 | 사용 판단 | 이용·품질 메모 |
|---|---|---|---|---|---|
| KOICA_PROJECT | 한국국제협력단 | 사업정보조회 | 공공데이터포털 REST API | 사용 | 승인키 사용, 상세조회 원문 보존 |
| KF_BUSINESS | 한국국제교류재단 | 공공외교 사업 정보 | 공공데이터포털 REST API | 사용 | 15099202 |
| KF_ORG | 한국국제교류재단 | 공공외교 수혜·참여기관 | 공공데이터포털 REST API | 사용 | 15099204 |
| KF_RESULTS | 한국국제교류재단 | 공공외교 사업별 실적 | 공공데이터포털 REST API | 사용 | 15112896 |
| KF_STUDIES | 한국국제교류재단 | 해외대학 한국학 현황 | 공식 Excel 다운로드 | 수동·배치 반입 | KF 출처 명시 필수, 2016~17 전수조사 기반 및 수시 갱신으로 시차 주의 |
| KF_ESCHOOL | 한국국제교류재단 | 글로벌 e-스쿨 현황 | 공식 Excel 다운로드 | 수동·배치 반입 후보 | 연도·수신국·수강생 수 활용 가능 |
| KF_HALLYU | 한국국제교류재단 | 지구촌 한류현황 | 공식 통계·다운로드 | 수동·배치 반입 후보 | 공개 연도 범위와 최신성 표시 |
| MOFA_RELATION | 외교부 | 국가별 우리나라와의 관계 | 공공데이터포털 REST API | 사용 | 15099539 |
| MOFA_ECONOMY | 외교부 | 국가별 경제현황 | 공공데이터포털 REST API | 사용 | 15099538 |
| MOFA_WARNING | 외교부 | 국가별 여행경보 | 공공데이터포털 REST API | 사용 | 15000827 |
| MOFA_LOD | 외교부 | 발간물·보도자료·브리핑 LOD | 공개 SPARQL | 사용 | 공공데이터법에 따라 LOD로 개방, 원문 URI 보존 |
| MOFA_INSIGHT | 외교부 | 공관 활동·분석 화면 | 웹사이트 | 참조 전용 | 별도 공개 API·재이용 약관 확인 전 화면 크롤링 금지; 원천 LOD·공공 API 우선 |

## 판단 원칙

- 공식 API, SPARQL, 공식 다운로드 기능만 자동·배치 입력으로 사용한다.
- MOFA 인사이트 화면 자체는 공개 API가 확인되기 전까지 링크·기능 조사에만 사용한다.
- MOFA 인사이트와 외교부 LOD에서 중복되는 분석 자료는 LOD URI를 대표 출처로 사용한다.
- KF 한국학 통계는 조사 기준의 시차를 `reference_date`와 데이터 신뢰도에 반영한다.
- 모든 데이터는 원문 URL, 제공기관, 수집일, 자료 기준일을 분리해 기록한다.

## 공식 확인 링크

- 외교부 LOD 소개: https://opendata.mofa.go.kr/lod/introduce.do
- 외교부 LOD SPARQL: https://opendata.mofa.go.kr/lod/sparqlEndpoint.do
- MOFA 인사이트: https://insight.mofa.go.kr/
- KF 해외대학 한국학 현황: https://www.kf.or.kr/koreanstudies/koreaStudiesList.do
- KF 글로벌 e-스쿨 현황: https://www.kf.or.kr/koreanstudies/globalESchoolList.do
