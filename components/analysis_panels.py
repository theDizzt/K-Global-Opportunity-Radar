import streamlit as st

from config.constants import EVIDENCE, PROJECTS
from services.chart_service import make_gauge_chart
from services.scoring_service import get_analysis_metrics, get_score_level


def show_score_panel(row, field, score):
    metrics = get_analysis_metrics(row, field)
    score_column, gauge_column, metric_column = st.columns(
        [0.78, 0.95, 2.2],
        vertical_alignment="center",
    )

    with score_column:
        st.markdown('<div class="score-label">협력기회 점수</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="score-number">{score:.1f}</div>', unsafe_allow_html=True)
        st.markdown(f'<span class="score-level">{get_score_level(score)}</span>', unsafe_allow_html=True)

    with gauge_column:
        st.plotly_chart(
            make_gauge_chart(score),
            width="stretch",
            config={"displayModeBar": False},
            key="opportunity_gauge",
        )

    with metric_column:
        metric_html = ""
        for name, value, color, icon in metrics:
            metric_html += f"""
            <div class="metric-item">
                <div class="metric-icon {color}">{icon}</div>
                <div class="metric-name">{name}</div>
                <div class="metric-track"><div class="metric-fill {color}" style="width:{value}%"></div></div>
                <div class="metric-value">{value}</div>
            </div>
            """
        st.markdown(metric_html, unsafe_allow_html=True)


def show_ai_summary(row):
    project = PROJECTS[row.iso3]
    st.markdown(
        f"""
        <div class="ai-card">
            <div class="ai-heading"><span class="ai-icon">AI</span><span>AI 종합 해석</span></div>
            <div class="ai-copy">{row.country}은 {project['summary']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_evidence_panel(row):
    st.markdown('<div class="panel-title"><span class="panel-icon">⚑</span>핵심 근거</div>', unsafe_allow_html=True)
    for source, description, category in EVIDENCE[row.iso3]:
        st.markdown(
            f"""
            <div class="evidence-row">
                <div class="evidence-symbol">▦</div>
                <div><b>{description}</b><br><span class="caption">{category}</span></div>
                <div class="evidence-source">{source}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def show_model_panel(row):
    project = PROJECTS[row.iso3]
    st.markdown('<div class="panel-title"><span class="panel-icon">♟</span>추천 협력 모델</div>', unsafe_allow_html=True)
    for number, model in enumerate(project["models"], 1):
        st.markdown(
            f'<div class="model-row"><span class="model-number">{number}</span><b>{model}</b></div>',
            unsafe_allow_html=True,
        )


def show_warning_panel(row):
    project = PROJECTS[row.iso3]
    st.markdown('<div class="panel-title warning-title"><span>▲</span>주의 요인</div>', unsafe_allow_html=True)
    warning_html = "".join(
        f'<span class="warning-tag">{warning}</span>'
        for warning in project["cautions"]
    )
    st.markdown(warning_html, unsafe_allow_html=True)
