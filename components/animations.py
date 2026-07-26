# 0. 모듈 불러오기
import streamlit as st


# 1. 차트 채움 애니메이션의 재생 상태를 저장할 세션 키
ANIMATION_VERSION_KEY = "_chart_animation_version"


# 2. 차트 애니메이션 상태 초기화
def initialize_animation_state():
    if ANIMATION_VERSION_KEY not in st.session_state:
        st.session_state[ANIMATION_VERSION_KEY] = 0


# 3. 입력값 변경 시 막대·원형 차트 애니메이션 버전 갱신
def restart_animations():
    initialize_animation_state()
    st.session_state[ANIMATION_VERSION_KEY] += 1


# 4. 현재 버전에 맞는 차트 채움 애니메이션만 적용
def apply_animation_variant():
    initialize_animation_state()
    variant = "a" if st.session_state[ANIMATION_VERSION_KEY] % 2 == 0 else "b"

    st.markdown(
        f"""
        <style>
        .metric-fill,
        .card-metric em,
        .confidence-card i,
        .st-key-compare_chart_panel [data-testid="stPlotlyChart"]
        .barlayer .point path {{
            animation-name: bar-fill-{variant};
        }}

        .gauge-chart,
        .score-ring {{
            animation-name: circle-fill-{variant};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
