# 0. 모듈 불러오기
import streamlit as st


# 1. 애니메이션 재생 상태를 저장할 세션 키
ANIMATION_VERSION_KEY = "_animation_version"


# 2. 애니메이션 상태 초기화
def initialize_animation_state():
    if ANIMATION_VERSION_KEY not in st.session_state:
        st.session_state[ANIMATION_VERSION_KEY] = 0


# 3. 입력값 변경 시 애니메이션 버전 갱신
def restart_animations():
    initialize_animation_state()
    st.session_state[ANIMATION_VERSION_KEY] += 1


# 4. 현재 버전에 맞는 CSS 애니메이션 적용
def apply_animation_variant():
    initialize_animation_state()
    variant = "a" if st.session_state[ANIMATION_VERSION_KEY] % 2 == 0 else "b"

    st.markdown(
        f"""
        <style>
        .score-number {{ animation-name: score-refresh-{variant}; }}
        .score-level, .metric-item, .ai-card, .evidence-row,
        .model-row, .warning-tag, .source-card {{
            animation-name: fade-refresh-{variant};
        }}
        .landing-hero h1, .landing-hero > p, .landing-metrics,
        .page-hero-title, .page-hero-copy, .headline, .subline,
        [data-testid="stSelectbox"], [data-testid="stPills"],
        .analysis-meta, .comparison-summary,
        .st-key-compare_chart_panel .panel-title, [data-testid="stAlert"] {{
            animation-name: page-refresh-{variant};
        }}
        .metric-fill {{ animation-name: bar-refresh-{variant}; }}
        [data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {{
            animation-name: chart-refresh-{variant};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
