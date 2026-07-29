# 0. 모듈 불러오기
import pandas as pd
import streamlit as st

from frontend_services.api_client import radar_gateway


# 1. 사용자 유형, 분석 분야, 권역 선택 항목 조회
@st.cache_data(ttl=60, show_spinner=False)
def load_options():
    result = radar_gateway.get_options()
    return result.payload, result.transport


# 2. 국가 목록 조회 및 화면용 열 이름으로 변환
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


# 3. 국가·사용자·분야별 분석 결과 조회
@st.cache_data(ttl=30, show_spinner=False)
def load_analysis(country_iso3, persona, field, capabilities=()):
    result = radar_gateway.analyze(country_iso3, persona, field, capabilities)
    return result.payload, result.transport


# 4. 선택 국가의 출처 기반 AI 초기 사업 검토안 생성
def load_report(country_iso3, persona, field, capabilities=()):
    result = radar_gateway.generate_report(
        country_iso3,
        persona,
        field,
        capabilities,
    )
    return result.payload, result.transport


# 5. 공공데이터 출처 목록 조회
@st.cache_data(ttl=60, show_spinner=False)
def load_sources():
    result = radar_gateway.get_sources()
    return result.payload, result.transport


# 6. 국가 표만 사용하는 기존 호출부를 위한 호환 함수
def load_data():
    """국가 표만 필요한 기존 호출부에 국가 데이터를 반환합니다."""
    return load_countries()[0]

