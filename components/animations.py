import streamlit as st


ANIMATION_VERSION_KEY = "_animation_version"


def initialize_animation_state():
    if ANIMATION_VERSION_KEY not in st.session_state:
        st.session_state[ANIMATION_VERSION_KEY] = 0


def restart_animations():
    initialize_animation_state()
    st.session_state[ANIMATION_VERSION_KEY] += 1


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
        .headline, .subline, [data-testid="stSelectbox"],
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
