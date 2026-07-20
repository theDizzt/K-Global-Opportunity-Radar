import streamlit as st

from config.settings import STYLE_PATH


def set_page_style():
    css = STYLE_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

