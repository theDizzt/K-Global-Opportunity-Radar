# 0. 모듈 불러오기
from html import escape

import streamlit as st


# 1. 세부 평가지표별 색상과 아이콘 설정
METRIC_STYLES = {
    "demand": ("blue", "01"),
    "policy_alignment": ("violet", "02"),
    "korean_base": ("teal", "03"),
    "readiness": ("blue", "04"),
}


# 2. 종합점수, 게이지, 세부지표 패널 표시
def show_score_panel(score, score_level, metrics):
    score_column, gauge_column, metric_column = st.columns(
        [0.78, 0.95, 2.2],
        vertical_alignment="center",
    )

    with score_column:
        st.markdown(
            '<div class="score-kicker">OPPORTUNITY SCORE</div>'
            '<div class="score-label">협력기회 점수</div>',
            unsafe_allow_html=True,
        )
        st.markdown(f'<div class="score-number">{score:.1f}</div>', unsafe_allow_html=True)
        st.markdown(f'<span class="score-level">{escape(score_level)}</span>', unsafe_allow_html=True)

    with gauge_column:
        st.markdown(
            f"""
            <div
                class="gauge-chart"
                style="--gauge-score:{score}"
                role="progressbar"
                aria-label="협력기회 점수"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-valuenow="{score:.1f}"
            >
                <div class="gauge-center">
                    <strong>{score:.1f}</strong>
                    <span>/ 100</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with metric_column:
        metric_html = ""
        for metric in metrics:
            name = escape(metric["name"])
            value = metric["score"]
            color, icon = METRIC_STYLES.get(metric["code"], ("teal", "●"))
            metric_html += f"""
            <div class="metric-item">
                <div class="metric-icon {color}">{icon}</div>
                <div class="metric-name">{name}</div>
                <div class="metric-track"><div class="metric-fill {color}" style="width:{value}%"></div></div>
                <div class="metric-value">{value}</div>
            </div>
            """
        st.markdown(metric_html, unsafe_allow_html=True)


# 3. 국가별 종합 해석 패널 표시
def show_ai_summary(country_name, interpretation):
    st.markdown(
        f"""
        <div class="ai-card">
            <div class="ai-heading"><span class="ai-icon">✦</span><span><small>AI INTERPRETATION</small>AI 종합 해석</span></div>
            <div class="ai-copy">{escape(country_name)}은 {escape(interpretation)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# 4. 분석에 사용된 핵심 근거 목록 표시
def show_evidence_panel(evidence):
    st.markdown(
        '<div class="panel-title"><span class="panel-icon">▦</span>'
        '<span>핵심 근거<small>VERIFIABLE EVIDENCE</small></span></div>',
        unsafe_allow_html=True,
    )
    for item in evidence:
        st.markdown(
            f"""
            <div class="evidence-row">
                <div class="evidence-symbol">▦</div>
                <div><b>{escape(item['title'])}</b><br><span class="caption">{escape(item['category'])}</span></div>
                <a class="evidence-source" href="{escape(item['source_url'], quote=True)}" target="_blank">{escape(item['source'])}</a>
            </div>
            """,
            unsafe_allow_html=True,
        )


# 5. 추천 협력 모델 목록 표시
def show_model_panel(recommendations):
    st.markdown(
        '<div class="panel-title"><span class="panel-icon">✦</span>'
        '<span>추천 협력 모델<small>NEXT ACTION</small></span></div>',
        unsafe_allow_html=True,
    )
    for number, model in enumerate(recommendations, 1):
        st.markdown(
            f'<div class="model-row"><span class="model-number">{number}</span><b>{escape(model)}</b></div>',
            unsafe_allow_html=True,
        )


# 6. 사업 추진 전 확인할 주의 요인 표시
def show_warning_panel(risks):
    st.markdown(
        '<div class="panel-title warning-title"><span>△</span>'
        '<span>주의 요인<small>RISK CHECK</small></span></div>',
        unsafe_allow_html=True,
    )
    warning_html = "".join(
        f'<span class="warning-tag">{escape(risk["title"])}</span>'
        for risk in risks
    )
    st.markdown(warning_html, unsafe_allow_html=True)
