# K-Global Opportunity Radar 사용 가이드

이 문서는 처음 실행하는 사용자와 백엔드·데이터 담당자가 설치부터 화면 실행,
공공데이터 수집, 점수 계산, 백엔드 동기화, 테스트까지 순서대로 따라 할 수 있도록
정리한 안내서입니다.

## 1. 프로그램과 데이터 상태

K-Global Opportunity Radar는 국가별 외교·개발협력 데이터를 비교하여 다음 정보를
제공합니다.

- 분야별 우선 협력 후보국
- 국가별 기회점수와 세부지표
- 추천 협력 모델과 주의 요인
- 분석 근거와 공공데이터 원문
- 국가별 PDF 협력 리포트

프로그램은 목적이 다른 두 SQLite 데이터베이스를 사용합니다.

| 구분 | 기본 경로 | 역할 |
|---|---|---|
| 데이터·알고리즘 DB | `data_algorithm/data/radar_real.db` | 원문, 정제 자료, 근거, 모델 결과 저장 |
| FastAPI 운영 DB | `data/k_global_radar.db` | Streamlit과 API에 제공할 국가, 점수, 근거 저장 |

처음 실행하면 FastAPI 운영 DB에 3개 시범국 데이터가 자동으로 준비됩니다. 실제 점수
스냅샷을 운영 DB에 동기화하면 API는 실제 점수를 우선 사용하고, 없는 국가·분야만
시범 산식으로 대체합니다. 대표 프로젝트 문구와 추천 협력 모델은 아직 시범 콘텐츠가
포함되어 있으므로 최종 의사결정 전에 원문과 현지 정보를 다시 확인해야 합니다.

## 2. 최초 설치

### 준비 사항

- Windows 10 또는 Windows 11
- PowerShell
- Python 3.12 이상
- 인터넷 연결

PowerShell에서 저장소 루트로 이동합니다.

```powershell
cd C:\Github\K-Global-Opportunity-Radar
```

PowerShell 스크립트 실행이 차단되면 현재 창에서만 실행을 허용합니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

개발 환경을 설치합니다.

```powershell
.\scripts\setup.ps1
```

Python을 자동으로 찾지 못하면 실행 파일 경로를 지정합니다.

```powershell
.\scripts\setup.ps1 -PythonExecutable "C:\Python312\python.exe"
```

## 3. 환경변수와 API 키 설정

공공데이터포털의 KF·MOFA·KOICA REST API를 사용하려면 루트 예시 파일을 복사합니다.

```powershell
Copy-Item .env.example .env
```

`.env`에 일반 인증키를 입력합니다.

```env
DATA_GO_KR_SERVICE_KEY=발급받은_일반인증키
```

기존 KOICA 전용 변수도 지원합니다.

```env
KOICA_SERVICE_KEY=발급받은_일반인증키
```

두 값이 모두 있으면 `DATA_GO_KR_SERVICE_KEY`가 우선합니다. 키 앞뒤에 따옴표를
붙이지 말고 `.env` 파일을 Git에 올리지 않습니다. 데이터 수집 스크립트는 저장소
루트의 `.env`를 자동으로 읽습니다.

FastAPI 연결 주소와 제한 시간을 현재 PowerShell 세션에서 바꾸려면 다음처럼
설정한 뒤 프로그램을 실행합니다.

```powershell
$env:K_GLOBAL_API_URL = "http://127.0.0.1:8000/api/v1"
$env:K_GLOBAL_API_TIMEOUT = "2.0"
$env:K_GLOBAL_API_FALLBACK = "true"
```

## 4. 프로그램 실행

### 화면과 백엔드 함께 실행

저장소 루트에서 다음 명령을 실행합니다.

```powershell
.\scripts\run.ps1
```

이 명령은 SQLite 운영 DB를 준비하고 FastAPI와 Streamlit을 실행합니다.

- 화면: `http://localhost:8501`
- API 상태: `http://localhost:8000/api/v1/health`
- API 문서: `http://localhost:8000/docs`

프로그램을 종료하려면 실행 중인 PowerShell 창에서 `Ctrl+C`를 누릅니다.

### 백엔드만 실행

```powershell
.\scripts\run_api.ps1
```

### 운영 DB를 처음부터 다시 준비

다음 명령은 기존 운영 DB의 시범 데이터를 초기 상태로 다시 적재합니다. 동기화한
점수도 삭제되므로 필요한 경우에만 사용합니다.

```powershell
.\.venv\Scripts\python.exe -m backend.database.init_db --reset
```

## 5. 화면 사용 방법

### 기회 탐색

1. `우선 협력 기회 리포트`까지 화면을 내립니다.
2. 교육, 보건, 디지털 등 `분석 분야`를 선택합니다.
3. 팀과 가까운 `사용자 유형`을 선택합니다.
4. 점수순으로 정렬된 국가 카드를 확인합니다.
5. `상세 인사이트 →`를 눌러 근거, 추천, 주의 요인을 확인합니다.
6. 상세 창에서 PDF 리포트를 내려받습니다.

### 핵심 신호

1. 상단에서 `핵심 신호`를 선택합니다.
2. 사용자 유형과 분석 분야를 선택합니다.
3. 최우선 후보국과 평균점수를 확인합니다.
4. 국가별 막대그래프와 세부지표 표를 비교합니다.
5. 점수와 함께 데이터 신뢰도 및 주의지표를 확인합니다.

### 분석 방법

1. 상단에서 `분석 방법`을 선택합니다.
2. 신호 수집, 관계 분석, 근거 검토 절차를 확인합니다.
3. `연결된 공공데이터`에서 기관을 선택해 공식 원문 페이지를 확인합니다.

상단의 `◐` 버튼으로 밝은 화면과 어두운 화면을 전환할 수 있습니다.

## 6. 실제 공공데이터 수집

화면 실행과 별도의 PowerShell에서 저장소 루트를 기준으로 실행합니다.

```powershell
.\scripts\collect_real_data.ps1
```

인증키가 없어도 외교부 LOD와 KF 글로벌 e-스쿨 공개 자료를 수집합니다. 인증키가
있으면 KF·MOFA·KOICA REST 출처도 함께 시도합니다. 키 또는 공식 원본 파일이 없는
출처는 `skipped`로 기록되고 나머지 수집은 계속됩니다.

특정 출처만 수집할 수 있습니다.

```powershell
.\scripts\collect_real_data.ps1 --sources lod
.\scripts\collect_real_data.ps1 --sources kf_eschool
.\scripts\collect_real_data.ps1 --sources lod kf_eschool
```

수집 결과는 다음 위치에 저장됩니다.

```text
data_algorithm/data/radar_real.db
data_algorithm/outputs/collection_report.json
```

결과를 확인합니다.

```powershell
.\.venv\Scripts\python.exe .\data_algorithm\scripts\inspect_collected_data.py
```

`duplicate_kf_eschool_ids`가 `0`이면 KF 강좌 ID 중복이 없다는 의미입니다.

## 7. 자동 수집 예약

자동 수집 작업은 다음 순서를 한 번에 수행합니다.

1. 선택한 공공데이터 수집
2. 기존 기회점수 재계산
3. FastAPI 운영 DB 준비
4. 점수와 근거 동기화
5. 실행 보고서와 로그 저장

기본 계획을 실제 요청 없이 확인합니다.

```powershell
.\scripts\run_auto_collection.ps1 -DryRun
```

기본 자동 수집 대상은 인증키가 필요 없는 외교부 LOD와 KF 글로벌 e-스쿨입니다.
수동으로 한 번 실행하려면 다음 명령을 사용합니다.

```powershell
.\scripts\run_auto_collection.ps1
```

인증형 KF·MOFA도 포함하려면 다음 옵션을 사용합니다.

```powershell
.\scripts\run_auto_collection.ps1 -IncludeAuthenticatedSources
```

기본 출처 목록을 직접 바꾸려면 쉼표로 구분합니다.

```powershell
.\scripts\run_auto_collection.ps1 -Sources "lod,kf_eschool,kf,mofa"
```

KOICA 최근 3개 연도 목록까지 포함하려면 다음처럼 실행합니다.

```powershell
.\scripts\run_auto_collection.ps1 `
  -IncludeAuthenticatedSources `
  -IncludeKoica
```

Windows 작업 스케줄러에 매일 오전 3시 작업을 등록합니다.

```powershell
.\scripts\register_auto_collection_task.ps1 `
  -Frequency Daily `
  -At "03:00"
```

인증형 출처와 KOICA를 포함한 주간 작업은 다음과 같이 등록할 수 있습니다.

```powershell
.\scripts\register_auto_collection_task.ps1 `
  -Frequency Weekly `
  -DayOfWeek Sunday `
  -At "03:00" `
  -IncludeAuthenticatedSources `
  -IncludeKoica
```

등록 스크립트는 같은 이름의 기존 작업을 갱신합니다. 예약 작업은 현재 Windows
사용자가 로그인한 상태에서 실행되며, 이전 작업이 아직 실행 중이면 새 작업을
중복 실행하지 않습니다.

최근 실행 결과와 로그는 다음 위치에서 확인합니다.

```text
data_algorithm/outputs/automation/latest_run.json
data_algorithm/outputs/automation/latest_collection.json
data_algorithm/outputs/automation/logs/
```

예약 작업을 제거합니다.

```powershell
.\scripts\unregister_auto_collection_task.ps1
```

출처별 권장 수집 주기와 자동 반영 조건은
[자동 수집 권장 데이터](recommended-data.md)를 참고합니다.

## 8. KOICA 목록 전용 수집

KOICA 상세조회 API가 `RESULT_CODE=99`를 반환하면 목록 자료만 먼저 저장합니다.
저장소 루트에서 다음 명령을 실행합니다.

```powershell
$env:PYTHONPATH = ".\data_algorithm\src"
.\.venv\Scripts\python.exe .\data_algorithm\scripts\collect_koica.py `
  --db .\data_algorithm\data\radar_real.db `
  --from-year 2019 `
  --to-year 2024 `
  --page-size 100 `
  --min-request-interval 5 `
  --list-only
```

`--list-only`는 사업번호, 사업명, 기간, 사업유형, 국가와 분야를 저장하고 불안정한
상세조회는 호출하지 않습니다. 옵션을 제거하면 상세조회 실패를 개별 기록하면서
수집 가능한 목록 자료는 계속 보존합니다.

## 9. 점수 계산과 FastAPI 동기화

실제 자료는 수집만으로 화면 점수에 바로 반영되지 않습니다. 기존 기회점수 파이프라인을
계산한 뒤 운영 DB에 동기화해야 합니다.

먼저 운영 DB를 준비합니다.

```powershell
cd C:\Github\K-Global-Opportunity-Radar
.\.venv\Scripts\python.exe -m backend.database.init_db
```

데이터·알고리즘 디렉터리에서 점수를 계산합니다.

```powershell
cd .\data_algorithm
$env:PYTHONPATH = "src"
$AsOf = Get-Date -Format "yyyy-MM-dd"
..\.venv\Scripts\python.exe -m opportunity_radar `
  --db data\radar_real.db `
  score `
  --as-of $AsOf
```

계산한 점수와 근거를 FastAPI 운영 DB로 보냅니다.

```powershell
..\.venv\Scripts\python.exe .\scripts\sync_backend.py `
  --algorithm-db data\radar_real.db `
  --backend-db ..\data\k_global_radar.db `
  --as-of $AsOf
```

합성 데모 번들에서 만든 점수를 동기화할 때만 `--demo`를 추가합니다. 실제 수집
자료에 `--demo`를 붙이면 API에서 시범 데이터로 표시됩니다.

동기화 후 프로그램을 다시 실행하고 API 응답의 다음 값을 확인합니다.

```text
data_status.is_demo
data_status.reference_date
data_status.completeness
```

## 10. 신규 다중 모델 실행

협력 연속성, 미충족 수요, 한국 공급 강도, 전체 공여국 포화도와 정책 실행 근거는
기존 종합점수와 분리된 모델입니다.

```powershell
cd C:\Github\K-Global-Opportunity-Radar\data_algorithm
$env:PYTHONPATH = "src"
..\.venv\Scripts\python.exe .\scripts\run_opportunity_models.py `
  --db data\statistical_signals_full.db `
  --fetch-world-bank `
  --world-bank-scope crs `
  --world-bank-transport bulk `
  --output outputs\opportunity_models_full.json
```

신규 모델 결과는 `opportunity_model_score`와
`opportunity_candidate_profile`에 저장됩니다. 현재 `sync_backend.py`는 기존
`score_snapshot`만 동기화하므로 신규 다중 모델은 아직 Streamlit 화면에 직접
표시되지 않습니다.

필요한 OECD CRS 적재와 정책근거 검수 절차는 다음 문서를 참고합니다.

- [수집기 안내](../data_algorithm/docs/COLLECTORS.md)
- [통계 신호 모델](../data_algorithm/docs/STATISTICAL_SIGNAL_MVP.md)
- [협력 기회 다중 모델](../data_algorithm/docs/OPPORTUNITY_MODELS.md)
- [백엔드 연동](../data_algorithm/docs/BACKEND_INTEGRATION.md)

## 11. 자동 테스트

FastAPI·프론트 연결 테스트는 저장소 루트에서 실행합니다.

```powershell
cd C:\Github\K-Global-Opportunity-Radar
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

데이터·알고리즘 테스트는 상대경로 자료를 사용하므로 해당 디렉터리에서 실행합니다.

```powershell
cd C:\Github\K-Global-Opportunity-Radar\data_algorithm
$env:PYTHONPATH = "src"
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 12. 자주 발생하는 문제

### `.venv was not found`

```powershell
.\scripts\setup.ps1
```

### 8000 또는 8501 포트를 사용할 수 없음

해당 포트를 사용하는 기존 FastAPI·Streamlit 실행 창을 `Ctrl+C`로 종료한 뒤 다시
실행합니다.

### 화면은 열리지만 API 연결 오류가 표시됨

`http://localhost:8000/api/v1/health`를 확인합니다. 기본 설정에서는 API 연결에
실패하면 같은 SQLite 운영 DB를 직접 읽는 안전 모드로 전환합니다.

### 수집 결과가 `skipped`

해당 출처의 인증키 또는 공식 원본 파일이 없다는 뜻입니다.
`data_algorithm/outputs/collection_report.json`의 `reason`을 확인합니다.

### KOICA 상세조회가 `RESULT_CODE=99`

`--list-only` 옵션으로 목록 수준 자료를 먼저 적재합니다. 제공기관 상세 API가
정상화되기 전까지 상세 누락은 데이터 품질 이슈로 유지합니다.

## 13. 가장 간단한 실행 순서

처음 한 번:

```powershell
cd C:\Github\K-Global-Opportunity-Radar
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
Copy-Item .env.example .env
```

평소 프로그램 실행:

```powershell
.\scripts\run.ps1
```

실제 데이터 갱신:

```powershell
.\scripts\collect_real_data.ps1
```

수집 자료를 화면 점수에 반영하려면 9장의 점수 계산과 FastAPI 동기화 절차까지
완료해야 합니다.
