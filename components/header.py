import streamlit as st

from components.animations import restart_animations


def show_header():
    st.markdown(
        """
        <div class="brand-row">
            <div class="brand-logo">◢</div>
            <div>외교협력 기회 레이더</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.radio(
        "메인 메뉴",
        ["기회 분석", "국가 비교", "근거 데이터"],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
        key="main_menu",
        on_change=restart_animations,
    )
