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

`styles/dashboard.css`는 다음 폰트를 저장소에 포함하지 않고 jsDelivr CDN에서 실행 시점에 불러옵니다.

### Pretendard Medium

- 저작권: Pretendard 프로젝트 및 해당 라이선스 파일에 기재된 원저작자
- 라이선스: SIL Open Font License 1.1
- 공식 프로젝트와 라이선스: [orioncactus/pretendard](https://github.com/orioncactus/pretendard/blob/main/LICENSE)
- 런타임 배포 미러: [projectnoonnu/pretendard](https://github.com/projectnoonnu/pretendard)

### Cafe24 PRO Slim Bold

- 저작권: Cafe24 Corp.
- 이용 조건: 개인·기업 사용자를 포함한 모든 사용자에게 무료이며 상업적 사용이 가능합니다. 폰트 파일 자체의 유료 판매는 금지됩니다.
- 공식 안내: [Cafe24 무료폰트](https://fonts.cafe24.com/), [Cafe24 도움말](https://help.cafe24.com/faq/web-hosting/introduce/new-renewal-change/cafe24_free_fonts_usage/)
- 런타임 배포 미러: [projectnoonnu/2511-1](https://github.com/projectnoonnu/2511-1)

폰트 파일을 저장소에 직접 포함하거나 수정본을 재배포할 때에는 각 폰트의 최신 원문 조건과 고지 의무를 다시 확인해야 합니다.

## 외부 데이터와 상표

- 외교부·KOICA·KF 등 외부 제공기관의 데이터는 이 프로젝트의 MIT License 대상이 아닙니다. 실제 데이터를 추가할 때에는 각 데이터셋의 이용허락 조건과 출처 표시 기준을 따라야 합니다.
- 기관명, 로고 및 상표에 대한 권리는 각 권리자에게 있으며, 이 저장소의 라이선스는 상표 사용 권한을 부여하지 않습니다.

이 문서는 라이선스 준수를 돕기 위한 프로젝트 고지이며 법률 자문이 아닙니다.
