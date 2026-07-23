# KF · MOFA · 외교부 LOD 수집기

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

## 환경변수

`.env`의 기존 `KOICA_SERVICE_KEY`를 그대로 재사용할 수 있습니다. 범용 이름을 쓰려면
같은 디코딩 키를 `DATA_GO_KR_SERVICE_KEY`에 넣습니다. 둘 다 있으면 범용 이름이 우선입니다.
LOD SPARQL은 별도 키가 필요하지 않습니다.

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
