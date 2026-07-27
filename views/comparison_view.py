# 0. 모듈 불러오기
from html import escape

import pandas as pd
import streamlit as st

from components.animations import restart_animations
from services.chart_service import make_compare_chart
from services.data_service import load_analysis


# 1. 비교 결과를 테마에 따라 색상이 바뀌는 고정 높이 표로 표시
def _show_comparison_table(rows):
    columns = (
        "국가",
        "기회점수",
        "수요성",
        "정책 정합성",
        "한국 연계기반",
        "실행 준비도",
        "데이터 신뢰도",
        "주의지표",
    )
    header_html = "".join(f"<th>{escape(column)}</th>" for column in columns)
    row_html = "".join(
        "<tr>"
        + "".join(f"<td>{escape(str(row[column]))}</td>" for column in columns)
        + "</tr>"
        for row in rows
    )
    st.markdown(
        f"""
        <div class="comparison-table-wrap">
            <table class="comparison-table">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{row_html}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


# 2. 동일 조건으로 국가별 기회점수 비교 화면 구성
def show_compare_page(data, options):
    st.markdown(
        """
        <section class="subpage-hero">
            <span class="page-kicker"><i></i> COMPARATIVE INTELLIGENCE</span>
            <h1 class="headline">국가별 협력기회 비교</h1>
            <p class="subline">동일한 사용자 유형과 분야를 적용해 후보 국가의 우선순위를 비교합니다.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    # 1.1. 비교에 공통 적용할 사용자 유형과 분야 선택
    with st.container(key="compare_controls"):
        st.markdown(
            '<div class="control-heading"><span>COMPARE QUERY</span>'
            '<b>비교 기준을 설정하세요</b></div>',
            unsafe_allow_html=True,
        )
        control_column_1, control_column_2 = st.columns(2)
        with control_column_1:
            st.markdown('<div class="control-label">01 · 사용자 유형</div>', unsafe_allow_html=True)
            persona = st.selectbox(
                "사용자 유형",
                options["personas"],
                key="compare_persona",
                label_visibility="collapsed",
                on_change=restart_animations,
            )
        with control_column_2:
            st.markdown('<div class="control-label">02 · 분석 분야</div>', unsafe_allow_html=True)
            field = st.selectbox(
                "분석 분야",
                options["fields"],
                key="compare_field",
                label_visibility="collapsed",
                on_change=restart_animations,
            )

    # 1.2. 국가별 분석 API 결과를 차트와 표 형식으로 변환
    compare_rows = []
    chart_rows = []
    for _, row in data.iterrows():
        result, _ = load_analysis(row.iso3, persona, field)
        metric_scores = {metric["code"]: metric["score"] for metric in result["metrics"]}
        score = result["analysis"]["score"]
        chart_rows.append({"country": result["country"]["name"], "score": score})
        compare_rows.append(
            {
                "국가": result["country"]["name"],
                "기회점수": score,
                "수요성": metric_scores["demand"],
                "정책 정합성": metric_scores["policy_alignment"],
                "한국 연계기반": metric_scores["korean_base"],
                "실행 준비도": metric_scores["readiness"],
                "데이터 신뢰도": f"{result['data_status']['completeness']}%",
                "주의지표": result["risks"][0]["level"] if result["risks"] else "확인 필요",
            }
        )

    # 1.3. 상위 국가와 비교 범위를 요약정보 카드로 표시
    ranked_rows = sorted(compare_rows, key=lambda item: item["기회점수"], reverse=True)
    top_country = ranked_rows[0]
    average_score = sum(item["기회점수"] for item in ranked_rows) / len(ranked_rows)
    st.markdown(
        f"""
        <div class="comparison-summary">
            <article><small>TOP OPPORTUNITY</small><strong class="summary-country">{top_country["국가"]}</strong><span class="summary-score">{top_country["기회점수"]:.1f}점</span></article>
            <article><small>AVERAGE SCORE</small><strong class="summary-number">{average_score:.1f}</strong><span>{field} 분야</span></article>
            <article><small>ANALYZED MARKETS</small><strong class="summary-number">{len(ranked_rows)}</strong><span>협력 후보국</span></article>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1.4. 국가별 기회점수 비교 차트 표시
    with st.container(border=False, key="compare_chart_panel"):
        st.markdown(
            f'<div class="panel-title"><span class="panel-icon">▥</span>'
            f'<span>{field} 분야 기회점수<small>COUNTRY RANKING</small></span></div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            make_compare_chart(
                pd.DataFrame(chart_rows),
                dark_mode=st.session_state.get("dark_mode", False),
            ),
            width="stretch",
            config={"displayModeBar": False},
            key="country_comparison",
        )

    # 1.5. 세부지표 비교표 표시
    st.markdown(
        '<div class="section-heading compact"><div><span class="eyebrow">METRIC BREAKDOWN</span>'
        '<h2>세부지표 비교</h2></div></div>',
        unsafe_allow_html=True,
    )
    _show_comparison_table(ranked_rows)
