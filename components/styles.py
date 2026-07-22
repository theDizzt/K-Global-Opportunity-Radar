# 0. 모듈 불러오기
import streamlit as st

from config.settings import STYLE_PATH


# 1. 외부 CSS 파일을 읽어 전체 페이지에 적용
def set_page_style():
    css = STYLE_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

