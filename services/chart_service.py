# 0. 모듈 불러오기
import plotly.graph_objects as go


# 1. 최근 연도별 협력 신호 추세 차트 생성
def make_signal_chart(trend, dark_mode=False):
    years = [point["year"] for point in trend]
    values = [point["score"] for point in trend]
    text_color = "#dce7f3" if dark_mode else "#344d67"
    grid_color = "#2a3d53" if dark_mode else "#dce5ee"
    marker_fill = "#0d1826" if dark_mode else "#ffffff"

    chart = go.Figure()
    chart.add_trace(
        go.Scatter(
            x=years,
            y=values,
            mode="lines+markers+text",
            text=values,
            textposition="top center",
            line=dict(color="#2787ef", width=3),
            marker=dict(size=9, color=marker_fill, line=dict(color="#2787ef", width=3)),
            hovertemplate="%{x}년 · %{y}점<extra></extra>",
        )
    )
    chart.update_layout(
        height=245,
        margin=dict(l=12, r=12, t=24, b=8),
        xaxis=dict(
            tickmode="array",
            tickvals=years,
            showgrid=False,
            fixedrange=True,
            tickfont=dict(family="Pretendard, sans-serif", size=14, color=text_color),
        ),
        yaxis=dict(
            range=[0, 105],
            dtick=25,
            gridcolor=grid_color,
            fixedrange=True,
            tickfont=dict(family="Pretendard, sans-serif", size=14, color=text_color),
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Pretendard, sans-serif", color=text_color, size=14),
        showlegend=False,
    )

    return chart


# 2. 국가별 기회점수 가로 막대 차트 생성
def make_compare_chart(compare_data, dark_mode=False):
    compare_data = compare_data.sort_values("score")
    text_color = "#dce7f3" if dark_mode else "#344d67"
    grid_color = "#2a3d53" if dark_mode else "#dce5ee"

    chart = go.Figure(
        go.Bar(
            x=compare_data["score"],
            y=compare_data["country"],
            orientation="h",
            text=compare_data["score"].map(lambda value: f"{value:.1f}"),
            textposition="outside",
            textfont=dict(
                family="Cafe24ProSlim, Pretendard, sans-serif",
                size=17,
                color=text_color,
            ),
            marker=dict(color=["#9fc9f7", "#5aa5f2", "#237fdf"]),
            hovertemplate="%{y} · %{x:.1f}점<extra></extra>",
        )
    )
    chart.update_layout(
        height=340,
        margin=dict(l=10, r=55, t=20, b=20),
        xaxis=dict(
            range=[0, 100],
            gridcolor=grid_color,
            tickfont=dict(family="Pretendard, sans-serif", size=14, color=text_color),
        ),
        yaxis=dict(
            title=None,
            tickfont=dict(family="Pretendard, sans-serif", size=14, color=text_color),
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        font=dict(family="Pretendard, sans-serif", color=text_color, size=14),
    )

    return chart
