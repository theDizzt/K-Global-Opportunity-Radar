# K-Global Opportunity Radar API 계약

## 기본 원칙

- 기본 경로는 `/api/v1`입니다.
- 국가 식별자는 ISO 3166-1 alpha-3 대문자를 사용합니다.
- 날짜는 `YYYY-MM-DD` 형식을 사용합니다.
- 점수 범위는 0~100입니다.
- `data_status.is_demo`로 시범 데이터와 실제 데이터를 구분합니다.
- 근거 항목은 출처, 기준일, 원문 URL을 항상 포함합니다.
- API 조회 데이터는 SQLite 저장소에서 제공됩니다.

## 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/v1/health` | 서버 상태 확인 |
| GET | `/api/v1/options` | 사용자 유형·분야·권역 목록 |
| GET | `/api/v1/sources` | 공공데이터 출처와 원문 URL 목록 |
| GET | `/api/v1/countries` | 분석 대상 국가 목록 |
| GET | `/api/v1/countries/{iso3}` | 국가 원시 지표와 기본정보 |
| POST | `/api/v1/analysis` | 국가·사용자·분야별 분석 결과 |

## 데이터베이스 초기화

```powershell
.\.venv\Scripts\python.exe -m backend.database.init_db
```

CSV와 현재 시범 상수를 다시 적재하려면 `--reset`을 사용합니다.

```powershell
.\.venv\Scripts\python.exe -m backend.database.init_db --reset
```

`GET /api/v1/countries`는 `region` 쿼리 매개변수로 권역을 필터링할 수 있습니다.

## 분석 요청

```json
{
  "country_iso3": "VNM",
  "persona": "대학생 팀",
  "field": "교육",
  "capabilities": ["데이터 분석", "에듀테크"]
}
```

## 분석 응답 구조

```json
{
  "country": {
    "iso3": "VNM",
    "name": "베트남",
    "english_name": "Vietnam",
    "region": "아세안",
    "flag": "🇻🇳",
    "data_completeness": 94,
    "reference_date": "2026-07-08"
  },
  "analysis": {
    "persona": "대학생 팀",
    "field": "교육",
    "score": 90.9,
    "score_level": "매우 높음"
  },
  "project_title": "교원 디지털 역량 강화",
  "interpretation": "디지털 교육 수요와 한국 연계기반이 모두 높아 단기 협력사업 발굴 가능성이 큽니다.",
  "partner_types": "교육부·대학·에듀테크 기업",
  "sdgs": "SDG 4·SDG 17",
  "metrics": [
    {"code": "demand", "name": "수요성", "score": 92}
  ],
  "trend": [
    {"year": 2022, "score": 48}
  ],
  "evidence": [
    {
      "title": "교육·디지털 분야 협력사업 흐름",
      "category": "개발협력 수요",
      "source": "KOICA",
      "reference_date": "2026-07-08",
      "source_url": "https://www.koica.go.kr/koica_kr/index.do",
      "is_demo": true
    }
  ],
  "recommendations": ["교원 디지털 역량 강화"],
  "risks": [],
  "gap_opportunity": "직업 연계형 디지털 교육 콘텐츠가 부족",
  "capabilities": ["데이터 분석", "에듀테크"],
  "data_status": {
    "completeness": 94,
    "reference_date": "2026-07-08",
    "is_demo": true,
    "notice": "시범 데이터 안내"
  }
}
```

전체 요청·응답 스키마는 서버 실행 후 `/docs`의 OpenAPI 화면에서도 확인할 수 있습니다.
