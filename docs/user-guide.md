# K-Global Opportunity Radar 사용 설명서

이 문서는 처음 프로그램을 실행하는 사용자도 그대로 따라 할 수 있도록
설치, 실행, 화면 사용, 실제 데이터 수집 순서로 설명합니다.

## 1. 프로그램에서 할 수 있는 일

K-Global Opportunity Radar는 국가별 외교·개발협력 데이터를 비교하여 다음
정보를 보여주는 의사결정 지원 프로그램입니다.

- 분야별 우선 협력 후보국
- 국가별 기회점수와 세부지표
- 추천 협력 모델과 주의 요인
- 분석에 사용한 근거와 공공데이터 출처
- 선택한 국가의 PDF 협력 리포트

현재 화면에 표시되는 국가 점수와 추천 문구는 기능 검증용 시범 데이터입니다.
외교부 LOD와 KF 글로벌 e-스쿨 실제 데이터는 별도 데이터베이스에 수집되며,
점수 재계산과 운영 DB 동기화 작업 후 화면에 반영됩니다.

## 2. 최초 설치

### 준비 사항

- Windows 10 또는 Windows 11
- PowerShell
- Python 3.12 이상
- 인터넷 연결

### 프로젝트 폴더 열기

PowerShell을 열고 프로젝트 폴더로 이동합니다.

```powershell
cd C:\Github\K-Global-Opportunity-Radar
```

### 실행 정책 임시 허용

PowerShell 스크립트 실행이 차단되는 경우 현재 창에서만 실행을 허용합니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

PowerShell 창을 닫으면 이 설정은 자동으로 해제됩니다.

### 개발 환경 설치

다음 명령을 한 번 실행합니다.

```powershell
.\scripts\setup.ps1
```

이 명령은 프로젝트 폴더에 `.venv` 가상환경을 만들고 필요한 Python 패키지를
설치합니다. 설치가 끝나면 `Streamlit environment is ready.`가 표시됩니다.

Python을 자동으로 찾지 못하면 실행 파일 경로를 직접 지정합니다.

```powershell
.\scripts\setup.ps1 -PythonExecutable "C:\Python312\python.exe"
```

## 3. 프로그램 실행

프로젝트 폴더에서 다음 명령을 실행합니다.

```powershell
.\scripts\run.ps1
```

이 명령 하나로 다음 작업이 자동 실행됩니다.

1. SQLite 데이터베이스 준비
2. FastAPI 백엔드 실행
3. Streamlit 화면 실행

브라우저가 자동으로 열리지 않으면 다음 주소를 직접 엽니다.

```text
http://localhost:8501
```

프로그램을 종료하려면 실행 중인 PowerShell 창에서 `Ctrl+C`를 누릅니다.

## 4. 화면 사용 방법

### 기회 탐색

프로그램을 실행하면 가장 먼저 표시되는 메인 화면입니다.

1. `우선 협력 기회 리포트`까지 화면을 내립니다.
2. `분석 분야`에서 교육, 보건, 디지털 등 원하는 분야를 선택합니다.
3. `사용자 유형`에서 자신의 팀과 가장 가까운 유형을 선택합니다.
4. 점수가 높은 순서로 정렬된 국가 카드를 확인합니다.
5. 원하는 국가의 `상세 인사이트 →` 버튼을 누릅니다.

상세 인사이트 창에서는 다음 내용을 확인할 수 있습니다.

- 종합 기회점수와 점수 수준
- 핵심 근거
- 추천 협력 모델
- 주의 요인
- PDF 리포트 다운로드

PDF가 필요하면 상세 창 아래의
`이 인사이트를 PDF 리포트로 저장 →` 버튼을 누릅니다.

상단의 `리포트 내보내기 →` 버튼은 PDF 다운로드 위치를 안내합니다. 실제
PDF 파일은 국가 카드의 상세 인사이트 창에서 생성합니다.

### 핵심 신호

같은 조건을 모든 후보국에 적용하여 비교하는 화면입니다.

1. 상단 메뉴에서 `핵심 신호`를 선택합니다.
2. `사용자 유형`을 선택합니다.
3. `분석 분야`를 선택합니다.
4. 상단 요약에서 최우선 후보국과 평균점수를 확인합니다.
5. 막대그래프에서 국가별 기회점수를 비교합니다.
6. 아래 표에서 수요성, 정책 정합성, 한국 연계기반, 실행 준비도,
   데이터 신뢰도와 주의지표를 비교합니다.

막대 길이만 보지 말고 데이터 신뢰도와 주의지표를 함께 확인하는 것이
중요합니다.

### 분석 방법

추천 결과의 생성 과정과 원문 출처를 확인하는 화면입니다.

1. 상단 메뉴에서 `분석 방법`을 선택합니다.
2. 신호 수집, 관계 분석, 근거 검토의 처리 과정을 확인합니다.
3. `연결된 공공데이터`에서 기관명을 선택합니다.
4. 새 창에서 해당 기관의 공식 원문 제공 페이지를 확인합니다.

### 다크 모드

상단 오른쪽의 `◐` 버튼을 누르면 밝은 화면과 어두운 화면을 전환할 수
있습니다. 선택 상태는 현재 프로그램 세션 동안 유지됩니다.

## 5. 실제 공공데이터 수집

실제 데이터 수집은 화면 실행과 별도로 수행합니다. 프로젝트 폴더에서 다음
명령을 실행합니다.

```powershell
.\scripts\collect_real_data.ps1
```

인증키가 없어도 다음 공식 자료는 수집됩니다.

- 외교부 LOD
- KF 글로벌 e-스쿨

특정 출처만 수집하려면 출처 이름을 지정합니다.

```powershell
.\scripts\collect_real_data.ps1 --sources lod
.\scripts\collect_real_data.ps1 --sources kf_eschool
.\scripts\collect_real_data.ps1 --sources lod kf_eschool
```

수집 결과는 다음 위치에 저장됩니다.

```text
실제 데이터 DB
data_algorithm/data/radar_real.db

최근 실행 보고서
data_algorithm/outputs/collection_report.json
```

### 수집 결과 확인

다음 명령으로 출처별 건수, KF 강좌 기간과 중복 여부를 확인합니다.

```powershell
.\.venv\Scripts\python.exe .\data_algorithm\scripts\inspect_collected_data.py
```

`duplicate_kf_eschool_ids`가 `0`이면 KF 강좌 ID 중복이 없다는 의미입니다.

## 6. 공공데이터포털 인증키 설정

KF·MOFA·KOICA의 인증형 REST API를 수집하려면 공공데이터포털 일반 인증키가
필요합니다.

### 환경설정 파일 만들기

프로젝트 폴더에서 예시 파일을 복사합니다.

```powershell
Copy-Item .env.example .env
```

생성된 `.env` 파일을 열고 다음 값을 입력합니다.

```env
DATA_GO_KR_SERVICE_KEY=발급받은_일반인증키
```

인증키 앞뒤에 따옴표를 붙이지 않습니다. `.env`는 Git에서 제외되어 있으므로
저장소에 올리지 않아야 합니다.

설정 후 통합 수집 명령을 다시 실행합니다.

```powershell
.\scripts\collect_real_data.ps1
```

인증키나 원본 파일이 없는 출처는 실행 보고서에 `skipped`로 표시됩니다.
나머지 출처의 수집은 계속 진행됩니다.

## 7. 백엔드만 실행하는 방법

화면 없이 FastAPI만 개발하거나 점검하려면 다음 명령을 사용합니다.

```powershell
.\scripts\run_api.ps1
```

실행 후 다음 주소를 사용할 수 있습니다.

- API 상태 확인: `http://localhost:8000/api/v1/health`
- API 문서: `http://localhost:8000/docs`

## 8. 자주 발생하는 문제

### 스크립트를 실행할 수 없다는 메시지가 표시될 때

현재 PowerShell 창에서 실행 정책을 임시 허용한 후 다시 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### `.venv was not found`가 표시될 때

환경 설치 명령을 먼저 실행합니다.

```powershell
.\scripts\setup.ps1
```

### 8501 포트를 사용할 수 없을 때

기존 Streamlit 실행 창을 찾아 `Ctrl+C`로 종료한 후 다시 실행합니다.

### 8000 포트를 사용할 수 없을 때

기존 FastAPI 또는 Uvicorn 실행 창을 종료한 후 `run.ps1`을 다시 실행합니다.

### 화면은 열리지만 API 연결 오류가 발생할 때

기본 설정에서는 API 연결 실패 시 같은 SQLite 데이터를 직접 읽는 안전 모드로
전환됩니다. 계속 오류가 표시되면 다음 주소에서 API 상태를 확인합니다.

```text
http://localhost:8000/api/v1/health
```

### 데이터 수집 결과가 `skipped`일 때

오류가 아니라 해당 출처에 필요한 인증키 또는 공식 원본 파일이 없다는
의미입니다. `collection_report.json`의 `reason` 항목을 확인합니다.

## 9. 가장 간단한 실행 순서

처음 한 번:

```powershell
cd C:\Github\K-Global-Opportunity-Radar
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

평소 프로그램 실행:

```powershell
cd C:\Github\K-Global-Opportunity-Radar
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\run.ps1
```

실제 데이터 갱신:

```powershell
.\scripts\collect_real_data.ps1
```
