import pandas as pd
import streamlit as st

from frontend_services.api_client import radar_gateway


@st.cache_data(ttl=60, show_spinner=False)
def load_options():
    result = radar_gateway.get_options()
    return result.payload, result.transport


@st.cache_data(ttl=60, show_spinner=False)
def load_countries():
    result = radar_gateway.get_countries()
    data = pd.DataFrame(result.payload).rename(
        columns={
            "name": "country",
            "english_name": "english",
            "data_completeness": "completeness",
            "reference_date": "updated",
        }
    )
    return data, result.transport


@st.cache_data(ttl=30, show_spinner=False)
def load_analysis(country_iso3, persona, field, capabilities=()):
    result = radar_gateway.analyze(country_iso3, persona, field, capabilities)
    return result.payload, result.transport


@st.cache_data(ttl=60, show_spinner=False)
def load_sources():
    result = radar_gateway.get_sources()
    return result.payload, result.transport


def load_data():
    """Compatibility helper for callers that only need the country table."""
    return load_countries()[0]

