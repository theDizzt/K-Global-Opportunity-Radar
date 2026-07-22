"""K-Global Opportunity Radar Streamlit entry point."""

####### 0. Modules #######

import streamlit as st

from components.animations import apply_animation_variant, initialize_animation_state
from components.header import show_header
from components.styles import set_page_style
from config.settings import PAGE_CONFIG
from services.data_service import load_countries, load_options
from views.analysis_view import show_analysis_page
from views.comparison_view import show_compare_page
from views.source_view import show_source_details


####### 1. App Config #######

st.set_page_config(**PAGE_CONFIG)


####### 2. Main #######

def main():
    initialize_animation_state()
    set_page_style()
    data, _ = load_countries()
    options, _ = load_options()
    menu = show_header()
    apply_animation_variant()

    if menu == "기회 분석":
        show_analysis_page(data, options)
    elif menu == "국가 비교":
        show_compare_page(data, options)
    elif menu == "근거 데이터":
        show_source_details()


if __name__ == "__main__":
    main()
