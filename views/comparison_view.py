import pandas as pd
import streamlit as st

from components.animations import restart_animations
from services.chart_service import make_compare_chart
from services.data_service import load_analysis


def show_compare_page(data, options):
    st.markdown('<div class="headline">국가별 협력기회 비교</div>', unsafe_allow_html=True)
    st.markdown('<div class="subline">동일한 사용자 유형과 분야 기준으로 시범국가를 비교합니다.</div>', unsafe_allow_html=True)

    control_column_1, control_column_2, _ = st.columns([1, 1, 2])
    with control_column_1:
        persona = st.selectbox(
            "사용자 유형",
            options["personas"],
            key="compare_persona",
            on_change=restart_animations,
        )
    with control_column_2:
        field = st.selectbox(
            "분석 분야",
            options["fields"],
            key="compare_field",
            on_change=restart_animations,
        )

    compare_rows = []
    chart_rows = []
    for _, row in data.iterrows():
        result, _ = load_analysis(row.iso3, persona, field)
        metric_scores = {metric["code"]: metric["score"] for metric in result["metrics"]}
        score = result["analysis"]["score"]
        chart_rows.append({"country": result["country"]["name"], "score": score})
        compare_rows.append(
            {
                "국가": result["country"]["name"],
                "기회점수": score,
                "수요성": metric_scores["demand"],
                "정책 정합성": metric_scores["policy_alignment"],
                "한국 연계기반": metric_scores["korean_base"],
                "실행 준비도": metric_scores["readiness"],
                "데이터 신뢰도": f"{result['data_status']['completeness']}%",
                "주의지표": result["risks"][0]["level"] if result["risks"] else "확인 필요",
            }
        )

    with st.container(border=True, key="compare_chart_panel"):
        st.markdown(
            f'<div class="panel-title"><span class="panel-icon">▥</span>{field} 분야 기회점수</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            make_compare_chart(pd.DataFrame(chart_rows)),
            width="stretch",
            config={"displayModeBar": False},
            key="country_comparison",
        )

    st.dataframe(pd.DataFrame(compare_rows), width="stretch", hide_index=True)
