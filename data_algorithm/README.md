# K-Global Opportunity Radar MVP

외교부 LOD·MOFA 인사이트·KOICA·KF 데이터를 국가/분야 단위로 표준화하고, 재현 가능한 산식으로 우선 검토 후보국을 추천하는 데이터 파이프라인입니다.

현재 구현 범위:

- SQLite 원천/표준/근거/점수 계층
- 교육, 직업훈련, 보건, 농업·기후, 한국학·문화 5개 분야
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

## 실제 데이터 연결

### KOICA

공공데이터포털의 `한국국제협력단_사업정보조회(15158394)`를 사용합니다. Base
URL은 `https://apis.data.go.kr/B260003/BsnsService`이며, 디코딩 키를
`KOICA_SERVICE_KEY`에 저장하면 됩니다. 실제 XML 목록 응답은 `project`와
`source_record`에 매핑되며 원문도 `raw_api_response`에 보존됩니다.

현재 상세조회 API는 정상 목록의 사업번호와 공식 가이드의 예제 사업번호 모두에
`RESULT_CODE=99`를 반환합니다. 이때는 `scripts\collect_koica.py --list-only`로
목록 수준 사업을 먼저 적재하고 상세 누락을 명시적으로 유지합니다. OECD CRS가 함께
적재된 통계 DB에서는 동일 ODA 사업의 이중 집계를 막기 위해 OECD를 결과 라벨로
사용하고 KOICA는 근거·메타데이터 보강 자료로 사용합니다.

### KF

KF 해외대학 한국학 과정 CSV는 `load_kf_academic_csv()`로 적재할 수 있습니다. 국가명→ISO3 매핑을 명시적으로 넘겨야 합니다.

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

1. KOICA 상세조회 API `RESULT_CODE=99` 정상화 여부 재점검
2. OECD CRS와 KOICA 사업의 교차출처 레코드 연결
3. KF 한국학·한류 원자료 범위 확대
4. LOD·MOFA 수집 국가를 검증 모집단 전체로 확대
5. World Bank 136개 비교국의 다중지표 수요점수에 전문가 타당성 평가 연결
6. 협력 연속성·미충족 수요·전체 공여국 포화도를 분리한 추천 화면 연결

협력 기회 모델의 산식, 실제 적재 결과와 한계는
[`docs/OPPORTUNITY_MODELS.md`](docs/OPPORTUNITY_MODELS.md)에 정리되어 있습니다.
