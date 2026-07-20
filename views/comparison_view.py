import pandas as pd
import streamlit as st

from components.animations import restart_animations
from config.constants import FIELD_SCORES, PERSONA_WEIGHTS
from services.chart_service import make_compare_chart
from services.scoring_service import calculate_score


def show_compare_page(data):
    st.markdown('<div class="headline">국가별 협력기회 비교</div>', unsafe_allow_html=True)
    st.markdown('<div class="subline">동일한 사용자 유형과 분야 기준으로 시범국가를 비교합니다.</div>', unsafe_allow_html=True)

    control_column_1, control_column_2, _ = st.columns([1, 1, 2])
    with control_column_1:
        persona = st.selectbox(
            "사용자 유형",
            list(PERSONA_WEIGHTS),
            key="compare_persona",
            on_change=restart_animations,
        )
    with control_column_2:
        field = st.selectbox(
            "분석 분야",
            list(FIELD_SCORES),
            key="compare_field",
            on_change=restart_animations,
        )

    with st.container(border=True):
        st.markdown(
            f'<div class="panel-title"><span class="panel-icon">▥</span>{field} 분야 기회점수</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            make_compare_chart(data, persona, field),
            width="stretch",
            config={"displayModeBar": False},
            key="country_comparison",
        )

    compare_rows = []
    for _, row in data.iterrows():
        compare_rows.append(
            {
                "국가": row.country,
                "기회점수": calculate_score(row, persona, field),
                "외교활동": row.diplomacy,
                "ODA 수요": row.oda,
                "한국 연계기반": row.korean_base,
                "데이터 신뢰도": f"{row.completeness}%",
                "주의지표": row.risk_level,
            }
        )

    st.dataframe(pd.DataFrame(compare_rows), width="stretch", hide_index=True)
