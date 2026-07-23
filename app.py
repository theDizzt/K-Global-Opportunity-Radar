"""K-Global Opportunity Radar의 Streamlit 실행 진입점."""

# 0. 모듈 불러오기

import streamlit as st

from components.animations import apply_animation_variant, initialize_animation_state
from components.header import show_header
from components.styles import set_page_style
from config.settings import PAGE_CONFIG
from services.data_service import load_countries, load_options
from views.analysis_view import show_analysis_page
from views.comparison_view import show_compare_page
from views.source_view import show_source_details


# 1. Streamlit 페이지 기본 설정

st.set_page_config(**PAGE_CONFIG)


# 2. 애플리케이션 실행 및 메뉴별 화면 연결

def main():
    # 2.1. 공통 상태와 스타일 초기화
    initialize_animation_state()
    set_page_style()

    # 2.2. 화면 공통 데이터와 선택 항목 불러오기
    data, _ = load_countries()
    options, _ = load_options()

    # 2.3. 상단 메뉴를 표시하고 선택된 화면 실행
    menu = show_header()
    apply_animation_variant()

    if menu == "기회 분석":
        show_analysis_page(data, options)
    elif menu == "국가 비교":
        show_compare_page(data, options)
    elif menu == "근거 데이터":
        show_source_details()


# 3. 파일을 직접 실행했을 때 애플리케이션 시작
if __name__ == "__main__":
    main()
