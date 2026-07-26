# 0. 모듈 불러오기
import plotly.graph_objects as go


# 1. 협력기회 종합점수 도넛 게이지 생성
def make_gauge_chart(score):
    chart = go.Figure(
        go.Pie(
            values=[score, 100 - score],
            hole=0.78,
            sort=False,
            direction="clockwise",
            rotation=90,
            marker=dict(colors=["#2f8df4", "#223247"], line=dict(width=0)),
            textinfo="none",
            hoverinfo="skip",
        )
    )
    chart.add_annotation(
        text=f"{score:.1f}<br><span style='font-size:19px'>/ 100</span>",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=38, color="#f4f8fd", family="Cafe24ProSlim, Pretendard, sans-serif"),
    )
    chart.update_layout(
        height=230,
        margin=dict(l=6, r=6, t=6, b=6),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        font=dict(family="Pretendard, sans-serif", color="#344d67"),
        transition=dict(duration=500, easing="cubic-in-out"),
    )

    return chart


# 2. 최근 연도별 협력 신호 추세 차트 생성
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
        transition=dict(duration=550, easing="cubic-in-out"),
    )

    return chart


# 3. 국가별 기회점수 가로 막대 차트 생성
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
        transition=dict(duration=500, easing="cubic-in-out"),
    )

    return chart
