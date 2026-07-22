# K-Global Opportunity Radar

외교부·KOICA·KF 공공데이터를 국가 단위로 연결해 협력 후보국과 프로젝트 초안을 제안하는 Streamlit MVP입니다.

## 개발 환경 구축

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

프로젝트 전용 Python 가상환경은 `.venv`에 생성됩니다. Python 명령이 등록되어 있지 않다면 실행 파일 경로를 직접 지정할 수 있습니다.

```powershell
.\scripts\setup.ps1 -PythonExecutable "C:\Python312\python.exe"
```

## 실행

```powershell
.\scripts\run.ps1
```

또는 직접 실행할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

브라우저에서 `http://localhost:8501`을 열면 됩니다.

`run.ps1`은 SQLite를 준비하고 FastAPI(8000)와 Streamlit(8501)을 함께 실행합니다. 이미 API가 실행 중이면 기존 프로세스를 그대로 사용합니다. API에 일시적으로 연결할 수 없는 경우 화면은 같은 SQLite 저장소를 직접 읽는 데모 안전 모드로 동작합니다.

## 백엔드 API 실행

```powershell
.\scripts\run_api.ps1
```

- API 문서: `http://localhost:8000/docs`
- 상태 확인: `http://localhost:8000/api/v1/health`
- API 계약: [docs/api-contract.md](docs/api-contract.md)

API는 `data/k_global_radar.db` SQLite 데이터베이스를 사용합니다. 데이터베이스가 없으면 실행 시 시범 CSV와 설정 데이터를 자동으로 적재합니다.

데이터베이스를 처음부터 다시 구성하려면 다음 명령을 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m backend.database.init_db --reset
```

SQLite 파일은 실행 데이터이므로 Git에 포함하지 않습니다. 스키마는 `backend/database/schema.sql`에서 관리합니다.

## 구현 범위

- 상단 메뉴: 기회 분석 / 국가 비교 / 근거 데이터
- 참고 레이아웃 기반 단일 화면 분석 대시보드
- 국가·관심 분야·사용자 유형 기반 기회 분석
- 기회점수, 데이터 충족률, 안전 주의지표 분리 표시
- Plotly 점수 게이지·협력 신호·국가 비교 차트
- 공백 기회 기반 프로젝트 제안
- 한글 1페이지 전략 검토안 PDF 다운로드

현재 국가 수치와 프로젝트 문구는 UI·추천 흐름 검증을 위한 시범 데이터입니다. 운영 단계에서는 데이터 API와 출처 기반 RAG 결과로 교체해야 합니다.

## 코드 구조

```text
app.py                  # Streamlit 시작점과 메뉴 라우팅
components/             # 헤더, 분석 패널, 공통 스타일 로더
config/                 # 경로, 페이지 설정, 가중치와 고정 데이터
services/               # 데이터 로딩, 점수, 차트, PDF 생성
backend/                # FastAPI, API 모델, 저장소, 백엔드 서비스
frontend_services/      # Streamlit용 API 클라이언트와 SQLite 안전 모드
backend/database/       # SQLite 스키마, 연결, 초기 적재
docs/                   # API 계약과 개발 문서
styles/dashboard.css    # 대시보드 전용 CSS
views/                  # 기회 분석, 국가 비교, 근거 데이터 화면
data/                   # 시범 국가 데이터
scripts/                # 환경 구축 및 실행 스크립트
tests/                  # API와 서비스 자동 테스트
```

## 라이선스

프로젝트 자체 소스 코드는 [MIT License](LICENSE)로 공개합니다.

Python 패키지, 웹폰트 및 향후 연결할 공공데이터에는 각 제공자의 별도 이용 조건이 적용됩니다. 현재 사용 중인 외부 구성요소와 출처는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에서 확인할 수 있습니다.
