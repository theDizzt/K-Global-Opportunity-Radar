from html import escape

import streamlit as st

from services.chart_service import make_gauge_chart


METRIC_STYLES = {
    "demand": ("teal", "●"),
    "policy_alignment": ("blue", "▤"),
    "korean_base": ("teal", "↗"),
    "readiness": ("blue", "✓"),
}


def show_score_panel(score, score_level, metrics):
    score_column, gauge_column, metric_column = st.columns(
        [0.78, 0.95, 2.2],
        vertical_alignment="center",
    )

    with score_column:
        st.markdown('<div class="score-label">협력기회 점수</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="score-number">{score:.1f}</div>', unsafe_allow_html=True)
        st.markdown(f'<span class="score-level">{escape(score_level)}</span>', unsafe_allow_html=True)

    with gauge_column:
        st.plotly_chart(
            make_gauge_chart(score),
            width="stretch",
            config={"displayModeBar": False},
            key="opportunity_gauge",
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


def show_ai_summary(country_name, interpretation):
    st.markdown(
        f"""
        <div class="ai-card">
            <div class="ai-heading"><span class="ai-icon">AI</span><span>AI 종합 해석</span></div>
            <div class="ai-copy">{escape(country_name)}은 {escape(interpretation)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_evidence_panel(evidence):
    st.markdown('<div class="panel-title"><span class="panel-icon">⚑</span>핵심 근거</div>', unsafe_allow_html=True)
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


def show_model_panel(recommendations):
    st.markdown('<div class="panel-title"><span class="panel-icon">♟</span>추천 협력 모델</div>', unsafe_allow_html=True)
    for number, model in enumerate(recommendations, 1):
        st.markdown(
            f'<div class="model-row"><span class="model-number">{number}</span><b>{escape(model)}</b></div>',
            unsafe_allow_html=True,
        )


def show_warning_panel(risks):
    st.markdown('<div class="panel-title warning-title"><span>▲</span>주의 요인</div>', unsafe_allow_html=True)
    warning_html = "".join(
        f'<span class="warning-tag">{escape(risk["title"])}</span>'
        for risk in risks
    )
    st.markdown(warning_html, unsafe_allow_html=True)
