# 0. 모듈 불러오기
from html import escape

import streamlit as st

from services.data_service import load_sources


# 1. 공공데이터 제공기관과 원문 확인 경로 표시
def show_source_details(sources=None):
    if sources is None:
        sources, _ = load_sources()
    st.markdown(
        """
        <section class="subpage-hero">
            <span class="page-kicker"><i></i> OPEN METHODOLOGY</span>
            <h1 class="headline">설명 가능한 분석,<br>검증 가능한 판단</h1>
            <p class="subline">추천에 사용한 기관별 데이터와 원문 확인 경로를 투명하게 공개합니다.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    # 1.1. 데이터 처리 과정을 세 단계 방법론 카드로 설명
    st.markdown(
        """
        <div class="method-grid">
            <article><span>01</span><strong>신호 수집</strong><p>외교·개발협력 공개데이터를 국가와 분야 기준으로 수집합니다.</p></article>
            <article><span>02</span><strong>관계 분석</strong><p>정책·교류·사업 신호의 연결 강도와 시점을 비교합니다.</p></article>
            <article><span>03</span><strong>근거 검토</strong><p>AI 추천과 함께 원문 출처와 데이터 상태를 확인합니다.</p></article>
        </div>
        <div class="section-heading source-heading">
            <div><span class="eyebrow">DATA SOURCES</span><h2>연결된 공공데이터</h2>
            <p>기관명을 선택하면 해당 원문 제공 페이지로 이동합니다.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1.2. 제공기관별 데이터 설명과 원문 링크 표시
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

    # 1.3. 시범 데이터와 실제 수집 데이터의 구분 안내
    st.info(
        "현재 국가별 수치와 최근 5년 추세는 화면·추천 흐름 검증용 시범 데이터입니다. "
        "운영 단계에서는 원문 기준일과 수집 로그를 함께 저장해야 합니다."
    )
