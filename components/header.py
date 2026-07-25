# 0. 모듈 불러오기
import streamlit as st

from components.animations import restart_animations


# 1. 상단 내비게이션의 화면 이동과 테마 상태 변경
def _toggle_theme():
    st.session_state["dark_mode"] = not st.session_state.get("dark_mode", False)


# 1.1. 선택한 상단 메뉴를 저장하고 화면 애니메이션 재시작
def _navigate(menu):
    st.session_state["active_menu"] = menu
    restart_animations()


# 2. 서비스 브랜드와 메인 메뉴를 참고 UI의 내비게이션으로 표시
def show_header():
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = False
    if "active_menu" not in st.session_state:
        st.session_state["active_menu"] = "기회 탐색"

    with st.container(key="site_header"):
        brand_column, menu_column, action_column = st.columns(
            [1.2, 1.15, 0.75],
            vertical_alignment="center",
        )
        with brand_column:
            st.markdown(
                """
                <div class="brand">
                    <span class="brand-mark">✦</span>
                    <span class="brand-name">NEXUS</span>
                    <span class="brand-divider"></span>
                    <span class="brand-caption">DECISION INTELLIGENCE</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with menu_column:
            menu_columns = st.columns(3, gap="small")
            for index, menu_name in enumerate(("기회 탐색", "핵심 신호", "분석 방법")):
                with menu_columns[index]:
                    st.button(
                        menu_name,
                        key=f"nav_{index}",
                        type=(
                            "primary"
                            if st.session_state["active_menu"] == menu_name
                            else "secondary"
                        ),
                        on_click=_navigate,
                        args=(menu_name,),
                        width="stretch",
                    )
        with action_column:
            theme_column, report_column = st.columns(
                [0.28, 1],
                vertical_alignment="center",
            )
            with theme_column:
                st.button(
                    "◔",
                    key="theme_toggle",
                    help="화면 테마 전환",
                    on_click=_toggle_theme,
                    width="stretch",
                )
            with report_column:
                report_clicked = st.button(
                    "리포트 내보내기  →",
                    key="header_report",
                    width="stretch",
                    type="primary",
                )

    # 2.1. 테마 버튼을 누르면 공통 디자인 토큰을 다크 모드 값으로 교체
    if st.session_state["dark_mode"]:
        st.markdown(
            """
            <style>
            :root {
                --background:#08111d; --surface:#0d1826; --surface-soft:#111e2d;
                --text:#edf3fa; --muted:#98a8ba; --line:#233247;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    return st.session_state["active_menu"], report_clicked


# 3. 모든 메뉴 하단에 서비스와 라이선스 정보를 표시
def show_footer():
    st.markdown(
        """
        <footer class="site-footer">
            <div class="footer-brand"><span class="brand-mark">✦</span>NEXUS</div>
            <p>Open decision intelligence for better global partnerships.</p>
            <span>MIT License · 2026</span>
        </footer>
        """,
        unsafe_allow_html=True,
    )
