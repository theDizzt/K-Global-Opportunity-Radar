# KOICA · KF · MOFA · 외교부 LOD 수집기

## 실행

프로젝트 루트에서 PowerShell로 실행합니다.

```powershell
$env:PYTHONPATH = "src"
python scripts\collect_public_sources.py --db data\radar_real.db
```

소스와 호출량을 제한할 수도 있습니다.

```powershell
python scripts\collect_public_sources.py --db data\radar_real.db --sources kf mofa
python scripts\collect_public_sources.py --db data\radar_real.db --sources lod --page-size 100 --max-pages 10
```

`--max-pages`를 생략하지 않으면 기본값은 소스·국가별 10페이지입니다. 전체 이력을
처음부터 모두 모아야 할 때는 데이터 규모와 트래픽 한도를 확인한 뒤 값을 늘립니다.

KOICA 사업 목록은 다음처럼 수집합니다.

```powershell
python scripts\collect_koica.py `
  --db data\statistical_signals_full.db `
  --from-year 2019 `
  --to-year 2024 `
  --page-size 100 `
  --min-request-interval 5 `
  --list-only
```

`--list-only`는 목록 API의 사업번호, 사업명, 기간, 사업유형, 국가코드, 분야를
저장하고 상세 API는 호출하지 않습니다. 2026-07-26 확인 기준
`getBsnsInfoDetail`은 공식 가이드의 예제 사업번호에도 HTTP 200과 함께
`RESULT_CODE=99`를 반환하므로, 제공기관 측 상세 API가 정상화되기 전까지 이 모드를
사용합니다. 목록 API의 `NATION_NM`이 비어 있는 응답은 KOICA 국가코드
`1775=VNM`, `1385=IDN`, `1514=MNG`로 표준화합니다.

## 환경변수

`.env`의 기존 `KOICA_SERVICE_KEY`를 그대로 재사용할 수 있습니다. 디코딩 키와
인코딩 키를 모두 받을 수 있으며, 내부에서 한 번 디코딩한 뒤 요청 쿼리에 한 번만
URL 인코딩합니다. `.env`는 현재 실행 폴더와 상위 폴더에서 자동 탐색하므로
저장소의 상위 작업 폴더에 둬도 됩니다.

범용 이름을 쓰려면 같은 키를 `DATA_GO_KR_SERVICE_KEY`에 넣습니다. 둘 다 있으면
범용 이름이 우선입니다. LOD SPARQL은 별도 키가 필요하지 않습니다.

## 수집 범위

- KF 공공외교 사업 정보: 공공데이터포털 15099202
- KF 공공외교 수혜·참여기관: 공공데이터포털 15099204
- KF 공공외교 사업별 실적: 공공데이터포털 15112896
- MOFA 국가별 우리나라와의 관계: 공공데이터포털 15099539
- MOFA 국가별 경제현황: 공공데이터포털 15099538
- MOFA 국가별 여행경보: 공공데이터포털 15000827
- 외교부 LOD: `mofapress`, `mofabrief`, `mofapub` SPARQL 데이터셋

대상 국가는 현재 베트남(VNM), 인도네시아(IDN), 몽골(MNG)입니다.

## 적재 구조

- `source_record`: 정규화된 KF/MOFA/LOD 원문 메타데이터
- `evidence`: 분야 분류에 성공한 협력 근거
- `kf_partner_org`: KF 수혜·참여기관과 실적 수
- `country_profile`: MOFA 관계·경제 프로필과 수치형 경제지표
- `safety_notice`: MOFA 여행경보 단계
- `raw_api_response`: 요청별 원본 응답
- `ingestion_run`: 실행 상태, 파라미터, 처리 건수, 오류
- `source_coverage`: 국가·소스별 최신 수집 커버리지

수집은 안정 ID와 upsert를 사용하므로 같은 범위를 다시 실행해도 정규화 테이블에 같은
레코드가 중복 생성되지 않습니다. LOD 원문 URI는 보존하며, 한 문서가 여러 국가를 다루면
각 국가의 근거 레코드로 별도 연결합니다.

## World Bank 수요지표

교육·디지털·보건 수요모델은 API 키가 필요 없는 World Bank Indicators API를
사용합니다. 긴 다국가 JSON 요청은 게이트웨이 오류가 반복될 수 있으므로 기본값은
지표별 ZIP CSV bulk 다운로드입니다. 9개 지표를 1.5초 간격으로 9회 요청한 뒤
2015년 이후의 선택 국가 관측만 `development_indicator_observation`에 upsert합니다.

```powershell
$env:PYTHONPATH = "src"
python scripts\run_opportunity_models.py `
  --db data\statistical_signals_full.db `
  --fetch-world-bank `
  --world-bank-scope crs `
  --world-bank-transport bulk `
  --request-interval 1.5 `
  --output outputs\opportunity_models_full.json
```

각 지표 다운로드가 끝날 때마다 커밋하므로 일부 지표에서 오류가 나도 이미 받은
지표는 유지됩니다. `batch`와 `all` JSON transport는 진단용 대체 경로로 남겨
두었지만 운영 기본값으로 사용하지 않습니다.

## 정책 근거 검수

LOD·MOFA 일반 문서에서 Tier A/B 실행 문구가 발견돼도 자동 정책점수로 사용하지
않습니다. 국가와 분야가 같은 문장 안에서 확인된 후보만 `review_required`로
저장하며 다음 명령으로 원문을 검토합니다.

```powershell
$env:PYTHONPATH = "src"
python scripts\review_policy_evidence.py `
  --db data\statistical_signals_full.db
```

검토자는 `evidence_id`, 제목, 본문, 원문 URL을 확인한 다음 자신의 식별자와
`--approve ID` 또는 `--reject ID`를 지정합니다. 서로 다른 두 검토자의 결론이
같아야 승인 또는 거절이 확정되며, 다르면 `needs_adjudication`으로 분리됩니다.

```powershell
python scripts\review_policy_evidence.py `
  --db data\statistical_signals_full.db `
  --reviewer analyst-a `
  --approve 123

python scripts\review_policy_evidence.py `
  --db data\statistical_signals_full.db `
  --reviewer analyst-b `
  --approve 123

python scripts\review_policy_evidence.py `
  --db data\statistical_signals_full.db `
  --reviewer analyst-a `
  --compare-reviewer analyst-b `
  --include-decided
```

검증자가 국가·분야·사건유형을 외교부 원문에서 직접 확인한 공식 근거 묶음은
별도 파일로 적재할 수 있습니다. 허용된 공식 도메인, ISO 날짜, Tier A/B 유형,
국가와 분야 코드를 엄격히 검사하며 같은 파일을 반복 실행해도 중복되지 않습니다.

```powershell
python scripts\import_official_policy_evidence.py `
  --db data\statistical_signals_full.db `
  --input data\policy\official_policy_evidence.json
```

이 절차는 지역·다자 문서가 특정 국가 근거로 잘못 연결되는 것을 정책점수에서
차단하기 위한 필수 검수 단계입니다.
