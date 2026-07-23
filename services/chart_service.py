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
            marker=dict(colors=["#079c9b", "#e7edf3"], line=dict(width=0)),
            textinfo="none",
            hoverinfo="skip",
        )
    )
    chart.add_annotation(
        text=f"<b>{score:.1f}</b><br><span style='font-size:17px'>/ 100</span>",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=32, color="#0a2949", family="Cafe24ProSlim, Pretendard, sans-serif"),
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
def make_signal_chart(trend):
    years = [point["year"] for point in trend]
    values = [point["score"] for point in trend]

    chart = go.Figure()
    chart.add_trace(
        go.Scatter(
            x=years,
            y=values,
            mode="lines+markers+text",
            text=values,
            textposition="top center",
            line=dict(color="#079c9b", width=3),
            marker=dict(size=9, color="#ffffff", line=dict(color="#079c9b", width=3)),
            hovertemplate="%{x}년 · %{y}점<extra></extra>",
        )
    )
    chart.update_layout(
        height=245,
        margin=dict(l=12, r=12, t=24, b=8),
        xaxis=dict(tickmode="array", tickvals=years, showgrid=False, fixedrange=True),
        yaxis=dict(range=[0, 105], dtick=25, gridcolor="#dce5ee", fixedrange=True),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Pretendard, sans-serif", color="#344d67", size=12),
        showlegend=False,
        transition=dict(duration=550, easing="cubic-in-out"),
    )

    return chart


# 3. 국가별 기회점수 가로 막대 차트 생성
def make_compare_chart(compare_data):
    compare_data = compare_data.sort_values("score")

    chart = go.Figure(
        go.Bar(
            x=compare_data["score"],
            y=compare_data["country"],
            orientation="h",
            text=compare_data["score"].map(lambda value: f"{value:.1f}"),
            textposition="outside",
            marker=dict(color=["#b7dfe0", "#54bcbc", "#087f9e"]),
            hovertemplate="%{y} · %{x:.1f}점<extra></extra>",
        )
    )
    chart.update_layout(
        height=320,
        margin=dict(l=10, r=55, t=20, b=20),
        xaxis=dict(range=[0, 100], gridcolor="#dce5ee"),
        yaxis=dict(title=None),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        font=dict(family="Pretendard, sans-serif", color="#344d67"),
        transition=dict(duration=500, easing="cubic-in-out"),
    )

    return chart
