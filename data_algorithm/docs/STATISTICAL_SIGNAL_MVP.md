# 협력신호 통계 MVP

## 분석 질문

분석 단위는 `국가 × 공통 분야 × 기준연도`다. 기준연도 말까지 관측된
외교·협력 사건과 기존 사업 이력을 사용해 향후 2년 안에 신규 한국 연계
공공·ODA 사업이 발생하는지를 검증한다.

현재 구현의 정답 데이터는 다음 순서로 `project_master`에 합쳐진다.

1. KOICA `project` 테이블의 사업
2. KF 공공외교 사업정보의 고유 사업
3. `import_oda_activities.py`로 적재한 OECD CRS 활동자료

현재 로컬 검증 DB에는 OECD CRS 2019~2024 활동자료가 들어 있으며, KOICA
직접 API가 정상화되면 동일 프로젝트 테이블에 추가해 CRS와 교차검증한다.

## 데이터 누출 방지

- 기준연도 `t`의 특징은 `t`년 말까지 공개된 사건과 사업만 사용한다.
- 정답은 `t+1`년부터 `t+2`년 사이 최초로 시작한 사업이다.
- KF 사업·실적의 `joint_project` 사건은 이미 발생한 사업이므로 선행 신호에서 제외한다.
- 현재 선행 신호 후보는 LOD와 MOFA의 사건만 사용한다.
- 무작위 분할 대신 과거 연도로 학습하고 미래 연도로 검증한다.

## 특징량

| 분류 | 특징 |
|---|---|
| 외교 신호 | 최근 1년·3년 사건 수, 시간감쇠 가중합, 최근 증가 추세 |
| 구체성 | Tier A/B 사건 수 |
| 다양성 | 출처 수, 참여기관 수 |
| 기존 기반 | 최근 3년·5년 사업 수, 마지막 사업 이후 경과연수 |
| 품질 | 가용 출처 기준 데이터 충족률 |

Tier A는 승인·조달·시행약정, Tier B는 MOU·타당성조사·실무협의,
Tier C는 회담·대사관 활동·보도 언급으로 정의한다. 현재 원문에는 대부분
Tier C만 존재하므로 Tier A/B의 통계적 효과는 아직 검증할 수 없다.

## 비교 모형

1. 국가·분야별 과거 발생률
2. 기존 사업 수·최근성만 사용한 구조 모형
3. 구조 모형에 외교 신호를 추가한 신호 모형

국가·분야별 과거 발생률이 전체 평균보다 충분히 우수하면
`structural_only`로 판정한다. 외교 신호의 유효성은 3번이 2번보다 미래
테스트 구간의 Brier score와 Average Precision에서 안정적으로 개선되는지로
판정한다. 두 지표가 일관되게 개선되지 않으면 외교 신호 확률은 서비스에
노출하지 않는다.

## 2026-07-26 실제 데이터 결과

입력 데이터:

- OECD CRS 한국 공여 활동 수원국 137개국
- OECD CRS 2019~2024 고유 활동 19,804건
- KF 고유 사업 396건
- 2019~2022 국가·분야·연도 패널 4,384행
- 향후 2년 신규 사업이 있는 양성 관측 2,335행
- LOD·MOFA 선행 사건 후보 454건
- 사업 결과로 분리한 KF `joint_project` 사건 771건
- KOICA 직접 API 사업 0건: 공식 API의 504 응답으로 OECD CRS가 현재 대체 라벨

2019년 이후를 시간순 테스트로 분리한 결과:

| 지표 | 결과 |
|---|---:|
| 전체 평균 Brier score | 0.2486 |
| 국가·분야 과거 재발률 Brier score | 0.1750 |
| 과거 재발률의 Brier 개선 | 29.6% |
| 전체 평균 Average Precision | 0.5392 |
| 국가·분야 과거 재발률 Average Precision | 0.8441 |
| 기존 사업 수·최근성 구조모형 Brier score | 0.134074 |
| 구조모형의 전체 평균 대비 Brier 개선 | 46.1% |
| 외교 신호 추가 모형 Brier score | 0.134051 |
| 구조모형 Average Precision | 0.909543 |
| 외교 신호 추가 모형 Average Precision | 0.909557 |

현재 판정은 `structural_only`다. 객관적으로 확인된 협력신호는 “해당 국가·분야에
한국 사업이 반복적으로 발생했는가”, “최근 3년 사업 수가 얼마인가”, “마지막
사업 이후 얼마나 지났는가”다. 과거 재발률만으로도 전체 평균 대비 Brier score가
29.6% 개선됐고, 최근 사업 수와 경과기간을 함께 사용하면 약 46.1% 개선됐다.
현재 후보의 `recommended_probability`는 이 `project_momentum` 구조모형에서
계산한다.

반면 LOD·MOFA 사건을 추가해도 구조모형보다 성능이 개선되지 않았다. 외교 사건은
3개국에만 수집되어 있어 137개국의 “사건 없음”과 “수집하지 않음”을 구분할 수
없고, 현재 자료도 Tier C 보도 언급에 편중돼 있다. 따라서 외교문서 신호는
`not_supported`로 유지한다.

과거 재발률은 신규 파트너 발굴보다 기존 협력관계의 연속성을 잘 찾는 신호다.
따라서 최종 서비스에서는 이를 `협력 연속성`으로 표시하고, 수요가 높지만 기존
사업이 적은 `미개척 기회`와 분리해야 한다.

## 실행

```powershell
$env:PYTHONPATH = "src"
python scripts\run_statistical_signals.py `
  --db data\statistical_signals_full.db `
  --horizon 2 `
  --start-year 2019 `
  --outcome-cutoff-year 2024 `
  --test-start-year 2021 `
  --candidate-country VNM `
  --candidate-country IDN `
  --candidate-country MNG `
  --output outputs\statistical_validation_full.json
```

OECD CRS 활동 파일 적재:

```powershell
$env:PYTHONPATH = "src"
python scripts\import_oda_activities.py ".\data\oecd\CRS 2024 data.zip" `
  --db data\statistical_signals_full.db `
  --source-url "https://webfs-dcd.oecd.org/files/dotStat/DSD_CRS/CRS%202024%20data.zip"
```

수입기는 CSV, `|` 구분 텍스트, 원문을 담은 ZIP을 지원하며 압축을 풀지 않고
스트리밍한다. 공여국이 한국인 활동만 기본적으로 적재한다. OECD CRS의
`DERecipientcode`를 ISO3로 사용하며, 다른 원본에 ISO3가 없으면 `raw_code`,
`raw_name`, `iso3` 열을 가진 매핑 파일을 제공한다.

## 다음 검증 조건

- KOICA 직접 API가 정상화되면 OECD CRS와 프로젝트 ID·예산·기간 교차검증
- OECD CRS 2010~2018 파일 추가로 더 긴 rolling backtest 구성
- LOD·MOFA를 검증 대상 국가 전체에 수집해 미수집과 사건 없음 구분
- MOU·타당성조사·공동위원회 등 Tier B 사건을 수작업 표본 라벨링
- LLM 사건 추출 정밀도 0.85 이상 확인
- 12개월·24개월·36개월 시간창 반복
- 국가 제외, 출처 제외, 위약 날짜 검정
- 외교 신호 추가 모형이 구조 모형보다 Brier와 Average Precision을 함께 개선

이 조건을 통과하기 전에는 “사업 발생 확률” 대신 “기존 협력 기반”과
“검증되지 않은 외교 관심 신호”를 분리해 표시한다.
