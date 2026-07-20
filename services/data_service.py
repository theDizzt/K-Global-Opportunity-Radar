import pandas as pd
import streamlit as st

from config.settings import DATA_PATH


@st.cache_data
def load_data():
    return pd.read_csv(DATA_PATH)

