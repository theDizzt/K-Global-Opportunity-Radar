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
    title_column, country_column, field_column, persona_column = st.columns(
        [3.35, 1, 1, 1.15],
        vertical_alignment="bottom",
    )

    with country_column:
        st.markdown('<div class="control-label">▣ 분석 대상 국가</div>', unsafe_allow_html=True)
        country = st.selectbox(
            "분석 대상 국가",
            data["country"].tolist(),
            index=0,
            label_visibility="collapsed",
            key="analysis_country",
            on_change=restart_animations,
        )

    with field_column:
        st.markdown('<div class="control-label">◇ 분석 분야</div>', unsafe_allow_html=True)
        field = st.selectbox(
            "분석 분야",
            options["fields"],
            index=0,
            label_visibility="collapsed",
            key="analysis_field",
            on_change=restart_animations,
        )

    with persona_column:
        st.markdown('<div class="control-label">◎ 사용자 유형</div>', unsafe_allow_html=True)
        persona = st.selectbox(
            "사용자 유형",
            options["personas"],
            index=0,
            label_visibility="collapsed",
            key="analysis_persona",
            on_change=restart_animations,
        )

    row = data[data["country"] == country].iloc[0]
    with title_column:
        st.markdown(
            '<div class="headline">'
            f'<span>{country}</span><span>{field} 분야</span><span>협력기회 분석</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="subline">분석 기준일&nbsp; {row.updated.replace("-", ".")} '
            f'&nbsp;·&nbsp; 데이터 신뢰도&nbsp; <strong>{row.completeness}%</strong></div>',
            unsafe_allow_html=True,
        )

    return row, field, persona


# 2. 선택된 조건에 맞는 종합 분석 화면 구성
def show_analysis_page(data, options):
    # 2.1. 사용자 선택값으로 백엔드 분석 결과 조회
    row, field, persona = show_analysis_controls(data, options)
    analysis, _ = load_analysis(row.iso3, persona, field)
    score = analysis["analysis"]["score"]
    main_column, side_column = st.columns([2.45, 1], gap="medium")

    # 2.2. 점수, 추세, 핵심 근거 영역 표시
    with main_column:
        with st.container(border=True, height=280, key="score_panel"):
            show_score_panel(score, analysis["analysis"]["score_level"], analysis["metrics"])

        chart_column, evidence_column = st.columns([1, 1], gap="medium")
        with chart_column:
            with st.container(border=True, height=350, key="signal_panel"):
                st.markdown(
                    '<div class="panel-title"><span class="panel-icon">⌁</span>최근 5년 협력 신호</div>',
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
            with st.container(border=True, height=350, key="evidence_panel"):
                show_evidence_panel(analysis["evidence"])

    # 2.3. 종합 해석, 추천 모델, 주의 요인 영역 표시
    with side_column:
        with st.container(border=True, height=168, key="ai_summary_panel"):
            show_ai_summary(analysis["country"]["name"], analysis["interpretation"])
        with st.container(border=True, height=312, key="model_panel"):
            show_model_panel(analysis["recommendations"])
        with st.container(border=True, height=134, key="warning_panel"):
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
