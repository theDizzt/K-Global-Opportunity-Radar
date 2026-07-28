# K-Global Opportunity Radar MVP

외교부 LOD·MOFA 인사이트·KOICA·KF 데이터를 국가/분야 단위로 표준화하고, 재현 가능한 산식으로 우선 검토 후보국을 추천하는 데이터 파이프라인입니다.

현재 구현 범위:

- SQLite 원천/표준/근거/점수 계층
- 교육, 직업훈련, 보건, 농업, 기후·환경, 디지털, 문화·콘텐츠, 한국학 8개 분야
- KOICA 프로젝트 기반 수요·수행기반 산출
- LOD/MOFA 이벤트의 시간감쇠 기반 외교 정합성 산출
- KF 한국학·한류 기반 산출
- 데이터 신뢰도, 안전 주의지표, 가중치 민감도
- 출처만 사용하는 설명 컨텍스트와 선택적 LLM 호출
- 텍스트 추론 Tier A/B 이중검수·Cohen's kappa와 검증된 공식 정책근거 적재
- 수행이력·안전·경제·수집상태를 분리한 실행 가능성 게이트
- API 키 없이 실행되는 3개국 데모 데이터

> `data/demo_bundle.json`의 수치는 파이프라인 검증을 위한 합성 데이터이며 실제 통계가 아닙니다.

## 바로 실행

PowerShell에서:

```powershell
$env:PYTHONPATH = "src"
python -m opportunity_radar --db data/radar.db run-demo --sector education
```

단계별 실행:

```powershell
$env:PYTHONPATH = "src"
python -m opportunity_radar --db data/radar.db init-db
python -m opportunity_radar --db data/radar.db load-demo
python -m opportunity_radar --db data/radar.db score --as-of 2026-07-16
python -m opportunity_radar --db data/radar.db recommend --sector education --explain
```

테스트:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## 점수 정의

```text
기회점수 = wD×관측수요 + wA×외교정합성 + wR×수행기반 + wK×한국·문화기반
```

분야마다 가중치가 다릅니다. 안전 위험은 점수에서 차감하지 않고 별도 표시하며, 데이터 신뢰도가 60 미만인 결과는 순위보다 참고 후보로 취급합니다.

정규화는 현재 비교군의 10~90백분위를 기준으로 합니다. 실서비스에서는 화면에 3개국만 표시하더라도 KOICA 전체 수원국 또는 권역 전체를 정규화 모집단으로 적재해야 합니다.

## 실제 데이터 수집

프로젝트 루트에서 통합 수집기를 실행합니다.

```powershell
.\scripts\collect_real_data.ps1
```

인증키 없이 외교부 LOD와 KF 글로벌 e-스쿨 공식 공개 표를 수집합니다.
수집 결과는 `data/radar_real.db`, 실행 상태는
`outputs/collection_report.json`에 저장됩니다. 동일 자료를 다시 실행해도
안정 해시와 고유키를 사용하므로 원천 및 구조화 레코드가 중복되지 않습니다.

2026-07-27 검증 결과:

- 외교부 LOD: 베트남 209건, 인도네시아 217건, 몽골 75건
- KF 글로벌 e-스쿨: 베트남 265건, 인도네시아 123건, 몽골 62건

### 공공데이터포털 인증 출처

루트 `.env`의 `DATA_GO_KR_SERVICE_KEY`에 일반 인증키를 입력하면 KF·MOFA·KOICA
REST API도 같은 명령에서 수집합니다. 인증키가 없으면 해당 출처만 건너뜁니다.

### KOICA

연도와 사업유형별 오류를 격리하는 `ResilientKoicaCollector`가 공식 API의 목록과
상세 자료를 `project` 데이터 계약으로 적재합니다.

공공데이터포털의 `한국국제협력단_사업정보조회(15158394)`를 사용합니다. Base
URL은 `https://apis.data.go.kr/B260003/BsnsService`이며, 디코딩 키를
`DATA_GO_KR_SERVICE_KEY` 또는 `KOICA_SERVICE_KEY`에 저장하면 됩니다. 실제 XML 목록 응답은 `project`와
`source_record`에 매핑되며 원문도 `raw_api_response`에 보존됩니다.

현재 상세조회 API는 정상 목록의 사업번호와 공식 가이드의 예제 사업번호 모두에
`RESULT_CODE=99`를 반환합니다. 이때는 `scripts\collect_koica.py --list-only`로
목록 수준 사업을 먼저 적재하고 상세 누락을 명시적으로 유지합니다. OECD CRS가 함께
적재된 통계 DB에서는 동일 ODA 사업의 이중 집계를 막기 위해 OECD를 결과 라벨로
사용하고 KOICA는 근거·메타데이터 보강 자료로 사용합니다.

### KF

KF 글로벌 e-스쿨 자료는 공식 공개 표에서 자동 수집합니다. 해외대학 한국학
현황 엑셀은 공식 파일을 `data/raw/kf_korean_studies.xlsx`에 둔 경우 추가
적재합니다.

### 외교부 LOD / MOFA

LOD SPARQL 결과와 MOFA 공개자료를 `source_record`에 저장한 다음, 분야·이벤트 유형·기관·근거문장을 `evidence`로 구조화합니다. 공식 제공 방식이 확인되지 않은 MOFA 화면은 무단 크롤링하지 않고 수동 CSV 또는 허가된 배치 자료를 사용합니다.

## LLM 설명 연결

기본값은 결정론적 템플릿 설명입니다. OpenAI 호환 Chat Completions 엔드포인트를 사용하는 경우 다음 값을 설정합니다.

```powershell
$env:LLM_API_URL = "https://provider.example/v1/chat/completions"
$env:LLM_API_KEY = "..."
$env:LLM_MODEL = "..."
```

LLM에는 이미 계산된 점수와 조회된 근거만 전달합니다. LLM은 점수를 계산하거나 변경하지 않습니다. 반환된 `evidence_ids`는 실제 조회된 근거 ID만 남도록 후검증합니다.

## 다음 실데이터 작업

1. 공공데이터포털 일반 인증키를 발급하고 KF·MOFA·KOICA REST 자료 수집
2. KOICA 상세조회 API `RESULT_CODE=99` 정상화 여부 재점검
3. OECD CRS와 KOICA 사업의 교차출처 레코드 연결
4. KF 해외대학 한국학·한류 공식 원자료 범위 확대
5. LOD·MOFA 수집 국가와 정규화 기준 모집단을 최소 10개국 이상으로 확대
6. World Bank 비교국의 다중지표 수요점수에 전문가 타당성 평가 연결
7. 실제 원천 자료로 분석 뷰와 점수 스냅샷 재생성
8. 검증된 점수와 협력 연속성·미충족 수요·공여국 포화도 모델을 백엔드 및 추천 화면에 연결

협력 기회 모델의 산식, 실제 적재 결과와 한계는
[`docs/OPPORTUNITY_MODELS.md`](docs/OPPORTUNITY_MODELS.md)에 정리되어 있습니다.
