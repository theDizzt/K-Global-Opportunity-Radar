# Third-Party Notices

이 저장소의 자체 소스 코드는 루트의 [`LICENSE`](LICENSE)에 따라 MIT License로 배포됩니다.
아래 구성요소는 각 권리자의 별도 라이선스가 적용되며 프로젝트의 MIT License로 재허가되지 않습니다.

## Python 직접 의존성

| 구성요소 | 이 프로젝트의 버전 범위 | 라이선스 | 공식 라이선스·프로젝트 |
| --- | --- | --- | --- |
| Streamlit | `>=1.50,<2` | Apache License 2.0 | [streamlit/streamlit](https://github.com/streamlit/streamlit/blob/develop/LICENSE) |
| pandas | `>=2.1,<3` | BSD 3-Clause License | [pandas-dev/pandas](https://github.com/pandas-dev/pandas/blob/main/LICENSE) |
| Plotly.py | `>=5.20,<7` | MIT License | [plotly/plotly.py](https://github.com/plotly/plotly.py/blob/main/LICENSE.txt) |
| ReportLab | `>=4.1,<5` | BSD License | [ReportLab 라이선스 안내](https://docs.reportlab.com/developerfaqs/#licensing) |

위 패키지는 이 저장소에 소스나 바이너리로 포함하지 않고 `requirements.txt`를 통해 설치합니다.
각 패키지가 설치하는 전이 의존성에도 해당 패키지의 개별 라이선스가 적용됩니다.

## 웹폰트

`styles/dashboard.css`는 다음 폰트를 저장소에 포함하지 않고 jsDelivr CDN에서
실행 시점에 불러옵니다.

### Pretendard

- 저작권: Pretendard 프로젝트 및 해당 라이선스 파일에 기재된 원저작자
- 라이선스: SIL Open Font License 1.1
- 공식 프로젝트와 라이선스: [orioncactus/pretendard](https://github.com/orioncactus/pretendard/blob/main/LICENSE)
- 런타임 배포 미러: [projectnoonnu/pretendard](https://github.com/projectnoonnu/pretendard)
- 사용 굵기: Thin(100), Regular(400), Medium(500), Bold(700), ExtraBold(800)

폰트 파일을 저장소에 직접 포함하거나 수정본을 재배포할 때에는 각 폰트의 최신 원문 조건과 고지 의무를 다시 확인해야 합니다.

## 외부 데이터와 상표

- 외교부·KOICA·KF 등 외부 제공기관의 데이터는 이 프로젝트의 MIT License 대상이 아닙니다. 실제 데이터를 추가할 때에는 각 데이터셋의 이용허락 조건과 출처 표시 기준을 따라야 합니다.
- 외교부 LOD의 외교일지·보도자료 데이터셋 페이지는 저작자표시 조건의 자유이용을 안내합니다. 이 프로젝트는 수집 문서마다 `외교부 Open Data`와 개별 원문 URL을 보존합니다.
- 기관명, 로고 및 상표에 대한 권리는 각 권리자에게 있으며, 이 저장소의 라이선스는 상표 사용 권한을 부여하지 않습니다.

## UI 참고 구현

2026년 7월 제공된 `ai-decision-support-dashboard.zip`의 화면 구성과 디자인 방향을
참고해 Streamlit UI를 재구성했습니다. 참고 구현의 코드와 디자인은 MIT License로
배포되며, 해당 ZIP의 저작권 고지와 허가 문구가 적용됩니다. 이 프로젝트는 React
원본 코드를 복사해 실행하지 않고 기존 Streamlit 구조에 맞게 독립적으로 재작성했습니다.

- 저작권 고지: Copyright (c) 2026 AI Decision Support Dashboard contributors
- 라이선스: MIT License
- 참고 범위: 내비게이션, 블루 포인트 색상, 히어로, 카드 및 방법론 정보 구조

이 문서는 라이선스 준수를 돕기 위한 프로젝트 고지이며 법률 자문이 아닙니다.
