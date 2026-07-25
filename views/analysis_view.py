# 0. 모듈 불러오기
import streamlit as st

from components.animations import restart_animations
from components.analysis_panels import (
    show_ai_summary,
    show_evidence_panel,
    show_model_panel,
    show_score_panel,
    show_warning_panel,
)
from services.chart_service import make_signal_chart
from services.data_service import load_analysis
from services.pdf_service import make_report_pdf
from views.source_view import show_source_details


# 1. 국가, 분석 분야, 사용자 유형 선택 영역 구성
def show_analysis_controls(data, options):
    st.markdown(
        """
        <section class="page-hero">
            <div class="hero-grid"></div>
            <span class="page-kicker"><i></i> AI 기반 글로벌 협력 인텔리전스</span>
            <h1 class="page-hero-title">국가 협력 기회를<br><strong>데이터로 발견하다</strong></h1>
            <p class="page-hero-copy">
                외교 공공데이터의 정책·교류·사업 신호를 연결해<br>
                실행 가능한 협력 우선순위와 근거를 제안합니다.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    # 1.1. 분석 조건을 하나의 검색 패널 안에서 입력
    with st.container(key="analysis_controls"):
        st.markdown(
            '<div class="control-heading"><span>ANALYSIS QUERY</span>'
            '<b>분석 조건을 선택하세요</b></div>',
            unsafe_allow_html=True,
        )
        country_column, field_column, persona_column = st.columns(3)

        with country_column:
            st.markdown('<div class="control-label">01 · 분석 대상 국가</div>', unsafe_allow_html=True)
            country = st.selectbox(
                "분석 대상 국가",
                data["country"].tolist(),
                index=0,
                label_visibility="collapsed",
                key="analysis_country",
                on_change=restart_animations,
            )

        with field_column:
            st.markdown('<div class="control-label">02 · 분석 분야</div>', unsafe_allow_html=True)
            field = st.selectbox(
                "분석 분야",
                options["fields"],
                index=0,
                label_visibility="collapsed",
                key="analysis_field",
                on_change=restart_animations,
            )

        with persona_column:
            st.markdown('<div class="control-label">03 · 사용자 유형</div>', unsafe_allow_html=True)
            persona = st.selectbox(
                "사용자 유형",
                options["personas"],
                index=0,
                label_visibility="collapsed",
                key="analysis_persona",
                on_change=restart_animations,
            )

    row = data[data["country"] == country].iloc[0]
    st.markdown(
        f"""
        <div class="analysis-meta">
            <div><small>TARGET COUNTRY</small><strong>{country}</strong><span>{row.iso3}</span></div>
            <div><small>FOCUS SECTOR</small><strong>{field}</strong><span>우선 분석 분야</span></div>
            <div><small>DATA CONFIDENCE</small><strong>{row.completeness}%</strong><span>{row.updated.replace("-", ".")} 기준</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return row, field, persona


# 2. 선택된 조건에 맞는 종합 분석 화면 구성
def show_analysis_page(data, options):
    # 2.1. 사용자 선택값으로 백엔드 분석 결과 조회
    row, field, persona = show_analysis_controls(data, options)
    analysis, _ = load_analysis(row.iso3, persona, field)
    score = analysis["analysis"]["score"]
    st.markdown(
        f"""
        <div class="section-heading">
            <div>
                <span class="eyebrow">PRIORITY OPPORTUNITY</span>
                <h2>{analysis["country"]["name"]} · {field} 협력 인사이트</h2>
                <p>기회 적합도와 실행 조건을 현재 수집 가능한 근거로 정리했습니다.</p>
            </div>
            <span class="analysis-badge">AI SCORE · {score:.1f}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    main_column, side_column = st.columns([2.45, 1], gap="medium")

    # 2.2. 점수, 추세, 핵심 근거 영역 표시
    with main_column:
        with st.container(border=False, height=300, key="score_panel"):
            show_score_panel(score, analysis["analysis"]["score_level"], analysis["metrics"])

        chart_column, evidence_column = st.columns([1, 1], gap="medium")
        with chart_column:
            with st.container(border=False, height=360, key="signal_panel"):
                st.markdown(
                    '<div class="panel-title"><span class="panel-icon">⌁</span>'
                    '<span>최근 5년 협력 신호<small>COOPERATION SIGNAL</small></span></div>',
                    unsafe_allow_html=True,
                )
                st.plotly_chart(
                    make_signal_chart(analysis["trend"]),
                    width="stretch",
                    config={"displayModeBar": False},
                    key="cooperation_signal",
                )
                st.markdown(
                    '<div class="caption">* 협력 신호 지수(0~100) · MVP 시연용 추세</div>',
                    unsafe_allow_html=True,
                )

        with evidence_column:
            with st.container(border=False, height=360, key="evidence_panel"):
                show_evidence_panel(analysis["evidence"])

    # 2.3. 종합 해석, 추천 모델, 주의 요인 영역 표시
    with side_column:
        with st.container(border=False, height=195, key="ai_summary_panel"):
            show_ai_summary(analysis["country"]["name"], analysis["interpretation"])
        with st.container(border=False, height=292, key="model_panel"):
            show_model_panel(analysis["recommendations"])
        with st.container(border=False, height=156, key="warning_panel"):
            show_warning_panel(analysis["risks"])

    # 2.4. 근거 화면 이동과 PDF 다운로드 기능 제공
    st.markdown('<div class="action-row">', unsafe_allow_html=True)
    evidence_button_column, pdf_button_column = st.columns([1, 1.45], gap="large")
    with evidence_button_column:
        show_evidence = st.button("▤  근거 데이터 보기", width="stretch")
    with pdf_button_column:
        pdf_data = make_report_pdf(analysis)
        st.download_button(
            "▣  PDF 리포트 내보내기",
            data=pdf_data,
            file_name=f"K-Global_Radar_{analysis['country']['iso3']}_{field}_brief.pdf",
            mime="application/pdf",
            width="stretch",
            type="primary",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if show_evidence:
        show_source_details()
