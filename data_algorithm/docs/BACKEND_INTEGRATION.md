# FastAPI 백엔드 연동

데이터·알고리즘 파이프라인과 애플리케이션 백엔드는 서로 다른 SQLite 데이터베이스를
사용한다. 두 스키마에 이름이 같은 테이블이 있으므로 하나의 DB 파일에 직접 합치지 않고,
계산 완료 후 점수와 근거만 백엔드 DB로 동기화한다.

## 처리 흐름

1. 데이터·알고리즘 DB에 원본과 정제 데이터를 적재한다.
2. `score_snapshot`에 국가·분야별 점수를 계산한다.
3. 백엔드 DB를 초기화한다.
4. 동기화 명령으로 `opportunity_scores`와 `source_documents`를 갱신한다.
5. `/api/v1/analysis`는 실제 점수가 있으면 우선 사용하고, 없으면 시범 산식으로 폴백한다.

## 실행

저장소 루트에서 백엔드 DB를 먼저 준비한다.

```powershell
.\.venv\Scripts\python.exe -m backend.database.init_db
```

`data_algorithm` 디렉터리에서 점수와 근거를 동기화한다.

```powershell
$env:PYTHONPATH = "src"
python scripts/sync_backend.py `
  --algorithm-db data/radar.db `
  --backend-db ../data/k_global_radar.db
```

특정 기준일 점수만 보낼 때는 `--as-of YYYY-MM-DD`를 추가한다. 같은 데이터를 반복 실행해도
기본키 기준으로 갱신되므로 중복 행이 생기지 않는다.

데모 번들에서 만든 점수를 동기화할 때는 반드시 `--demo`를 추가한다. 이 값은 API의
`data_status.is_demo`까지 전달된다.

## 분야 매핑

현재 백엔드 API 계약과 화면이 지원하는 여섯 분야를 다음과 같이 연결한다.

| 알고리즘 분야 | 백엔드 분야 |
|---|---|
| `education` | 교육 |
| `health` | 보건 |
| `digital` | 디지털 |
| `climate_environment` | 기후·환경 |
| `culture_content` | 문화·한류 |
| `vocational` | 청년취업 |

알고리즘의 `agriculture`, `korean_studies` 점수는 현재 백엔드 요청 모델에 대응 분야가 없어
점수 동기화에서 제외한다. 백엔드와 화면이 두 분야를 지원하게 되면 매핑만 확장할 수 있다.

## API 동작

- 실제 점수가 존재하면 수요성·정책 정합성·실행 준비도·한국 연계기반을 그대로 사용한다.
- 사용자 유형별 가중치를 네 차원에 적용해 응답용 종합점수를 다시 계산한다.
- 데이터 완전성은 알고리즘의 `data_confidence`를 사용한다.
- 실제 점수 스냅샷이 없으면 기존 시범 상수와 시범 추세를 사용한다.
- 대표 프로젝트와 협력모델 문구는 아직 시범 콘텐츠이므로 응답 안내문에 이를 명시한다.
