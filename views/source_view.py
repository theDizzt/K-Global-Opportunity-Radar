import streamlit as st

from config.constants import SOURCE_DESCRIPTIONS, SOURCE_LINKS


def show_source_details():
    st.markdown('<div class="headline" style="font-size:2rem">근거 데이터</div>', unsafe_allow_html=True)
    st.markdown('<div class="subline">추천에 사용한 기관별 데이터와 원문 확인 경로입니다.</div>', unsafe_allow_html=True)

    columns = st.columns(4)
    for index, (source, url) in enumerate(SOURCE_LINKS.items()):
        columns[index].markdown(
            f"""
            <div class="source-card">
                <a href="{url}" target="_blank">{source} ↗</a>
                <p>{SOURCE_DESCRIPTIONS[source]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.info(
        "현재 국가별 수치와 최근 5년 추세는 화면·추천 흐름 검증용 시범 데이터입니다. "
        "운영 단계에서는 원문 기준일과 수집 로그를 함께 저장해야 합니다."
    )

