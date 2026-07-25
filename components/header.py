# 0. 모듈 불러오기
import streamlit as st

from components.animations import restart_animations


# 1. 서비스 브랜드와 메인 메뉴를 어두운 상단 내비게이션으로 표시
def show_header():
    with st.container(key="site_header"):
        brand_column, menu_column, status_column = st.columns(
            [1.45, 1.5, 0.8],
            vertical_alignment="center",
        )
        with brand_column:
            st.markdown(
                """
                <div class="brand">
                    <span class="brand-mark">✦</span>
                    <span class="brand-name">K-GLOBAL RADAR</span>
                    <span class="brand-divider"></span>
                    <span class="brand-caption">DIPLOMATIC OPPORTUNITY INTELLIGENCE</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with menu_column:
            menu = st.radio(
                "메인 메뉴",
                ["기회 분석", "국가 비교", "근거 데이터"],
                index=0,
                horizontal=True,
                label_visibility="collapsed",
                key="main_menu",
                on_change=restart_animations,
            )
        with status_column:
            st.markdown(
                '<div class="system-status"><span></span> PUBLIC DATA · AI READY</div>',
                unsafe_allow_html=True,
            )
    return menu


# 2. 모든 메뉴 하단에 서비스와 라이선스 정보를 표시
def show_footer():
    st.markdown(
        """
        <footer class="site-footer">
            <div class="footer-brand"><span class="brand-mark">✦</span>K-GLOBAL RADAR</div>
            <p>공공데이터로 발견하는 글로벌 협력 기회</p>
            <span>MIT License · 2026</span>
        </footer>
        """,
        unsafe_allow_html=True,
    )
