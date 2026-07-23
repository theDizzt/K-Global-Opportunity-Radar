# 외교부 LOD 수집 구조

## 수집 범위

현재 수집기는 외교부 LOD에서 다음 데이터를 가져옵니다.

- 국가 URI, ISO2, ISO3, 국가명
- 외교일지 제목, 요약, 시작일, 관련 국가
- 보도자료 제목, 요약, 게시일, 원문 URL, 관련 국가

공식 데이터셋 페이지:

- 외교일지: <https://opendata.mofa.go.kr/lod/detailDataset.do?graph=http%3A%2F%2Fopendata.mofa.go.kr%2Fmofadaily>
- 외교부 보도자료: <https://opendata.mofa.go.kr/mofapress/detailDataset.do?graph=http%3A%2F%2Fopendata.mofa.go.kr%2Fmofapress>

## 실행 방법

기본 시범국가의 외교일지와 보도자료를 수집합니다.

```powershell
.\scripts\collect_mofa.ps1
```

국가와 데이터셋, 국가별 최대 문서 수를 지정할 수 있습니다.

```powershell
.\scripts\collect_mofa.ps1 --countries VNM,IDN,MNG --datasets mofadaily,mofapress --limit 100
```

## 저장 구조

- `raw_source_payloads`: SPARQL 원본 JSON과 요청문
- `country_aliases`: 외교부 국가 URI와 내부 ISO3 연결
- `source_documents`: 정제된 외교일지·보도자료
- `document_countries`: 문서와 관련 국가의 다대다 연결
- `collection_logs`: 수집 성공·실패와 적재 건수

## 분석 API 연결

선택 국가와 분야에 맞는 실제 외교부 문서가 있으면 분석 API의 `evidence`에 최신 문서 3건을 반환합니다. 실제 문서가 없거나 수집에 실패하면 기존 시범 근거를 유지합니다.

현재 기회점수와 최근 5년 추세는 아직 시범 산식입니다. 외교부 문서 건수를 점수로 단순 치환하지 않고, 데이터 분포와 분야 분류 정확도를 검증한 뒤 별도 산식 버전으로 연결해야 합니다.

## 이용 조건

외교일지와 보도자료 데이터셋 페이지는 저작자표시 조건의 자유이용을 안내합니다. 화면과 PDF에는 외교부 Open Data 명칭과 개별 원문 URL을 함께 표시해야 합니다.
