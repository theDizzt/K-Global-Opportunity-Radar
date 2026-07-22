from html import escape

import streamlit as st

from services.data_service import load_sources


def show_source_details(sources=None):
    if sources is None:
        sources, _ = load_sources()
    st.markdown('<div class="headline" style="font-size:2rem">근거 데이터</div>', unsafe_allow_html=True)
    st.markdown('<div class="subline">추천에 사용한 기관별 데이터와 원문 확인 경로입니다.</div>', unsafe_allow_html=True)

    with st.container(key="source_cards"):
        columns = st.columns(len(sources))
        for index, source in enumerate(sources):
            columns[index].markdown(
                f"""
                <div class="source-card">
                    <a href="{escape(source['url'], quote=True)}" target="_blank">{escape(source['name'])} ↗</a>
                    <p>{escape(source['description'])}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.info(
        "현재 국가별 수치와 최근 5년 추세는 화면·추천 흐름 검증용 시범 데이터입니다. "
        "운영 단계에서는 원문 기준일과 수집 로그를 함께 저장해야 합니다."
    )
