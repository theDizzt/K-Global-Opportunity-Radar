# 0. 모듈 불러오기
from html import escape

import streamlit as st

from components.animations import restart_animations
from components.analysis_panels import (
    show_evidence_panel,
    show_model_panel,
    show_warning_panel,
)
from services.data_service import load_analysis
from services.pdf_service import make_report_pdf


# 1. 국가 카드별 강조색과 카드에 표시할 핵심지표 설정
CARD_ACCENTS = ("red", "teal", "violet")
CARD_METRICS = (
    ("policy_alignment", "정책 적합도"),
    ("korean_base", "한국 연계기반"),
    ("readiness", "실행 가능성"),
)


# 2. 선택한 국가의 근거·추천·PDF 기능을 상세 팝업으로 표시
@st.dialog("협력 인사이트", width="large")
def show_opportunity_dialog(analysis, field):
    score = analysis["analysis"]["score"]
    country = analysis["country"]
    st.markdown(
        f"""
        <div class="dialog-overview">
            <span class="dialog-kicker">{escape(country["iso3"])} · {escape(field)}</span>
            <h2>{escape(country["name"])} 협력 인사이트</h2>
            <p>{escape(analysis["interpretation"])}</p>
            <div class="dialog-score">
                <strong>{score:.1f}</strong>
                <span>AI 협력 적합도<br><b>{escape(analysis["analysis"]["score_level"])}</b></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    evidence_column, recommendation_column = st.columns([1.12, 1], gap="large")
    with evidence_column:
        show_evidence_panel(analysis["evidence"])
    with recommendation_column:
        show_model_panel(analysis["recommendations"])
        show_warning_panel(analysis["risks"])

    pdf_data = make_report_pdf(analysis)
    st.download_button(
        "이 인사이트를 PDF 리포트로 저장  →",
        data=pdf_data,
        file_name=f"NEXUS_{country['iso3']}_{field}_brief.pdf",
        mime="application/pdf",
        width="stretch",
        type="primary",
        key=f"dialog_pdf_{country['iso3']}_{field}",
    )


# 3. 히어로와 서비스 분석 범위 요약 표시
def show_landing_intro(data, options):
    st.markdown(
        f"""
        <section class="landing-hero" id="top">
            <div class="hero-grid"></div>
            <span class="status-pill"><i></i> AI 기반 글로벌 협력 인텔리전스</span>
            <h1>국가 협력 기회를<br><strong>데이터로 발견하다</strong></h1>
            <p>흩어진 외교·정책·사업 신호를 하나의 관점으로 연결해<br>
            다음 협력 파트너와 실행 우선순위를 제안합니다.</p>
            <div class="hero-actions">
                <a class="primary-link" href="#priority-opportunities">기회 대시보드 보기 <b>→</b></a>
                <a class="ghost-link" href="#signal-map">핵심 신호 살펴보기</a>
            </div>
        </section>
        <section class="landing-metrics">
            <article><strong>{len(data)}</strong><span>개 후보국</span><p>우선 협력시장 비교</p></article>
            <article><strong>{len(options["fields"])}</strong><span>개 분야</span><p>정책·사업 분야별 분석</p></article>
            <article><strong>4</strong><span>개 핵심지표</span><p>수요·정책·연계·실행 조건</p></article>
        </section>
        """,
        unsafe_allow_html=True,
    )


# 4. 국가별 분석 결과를 참고 UI의 어두운 기회 카드로 표시
def show_opportunity_cards(results, field):
    card_columns = st.columns(len(results), gap="medium")
    selected_result = None

    for index, (column, analysis) in enumerate(zip(card_columns, results, strict=True)):
        accent = CARD_ACCENTS[index % len(CARD_ACCENTS)]
        country = analysis["country"]
        score = analysis["analysis"]["score"]
        metrics = {item["code"]: item["score"] for item in analysis["metrics"]}
        trend = analysis["trend"]
        change = score - trend[-2]["score"] if len(trend) > 1 else 0
        metric_html = "".join(
            f"""
            <div class="card-metric">
                <span>{escape(label)} <b>{metrics[code]}</b></span>
                <i><em style="width:{metrics[code]}%"></em></i>
            </div>
            """
            for code, label in CARD_METRICS
        )

        with column:
            with st.container(key=f"opportunity_card_{index}"):
                st.markdown(
                    f"""
                    <div class="opportunity-card accent-{accent}">
                        <div class="card-topline">
                            <span class="country-code">{escape(country["iso3"])}</span>
                            <span class="change">↑ {change:+.1f}</span>
                        </div>
                        <div class="score-ring" style="--score:{score}">
                            <div><strong>{score:.0f}</strong><small>적합도</small></div>
                        </div>
                        <span class="card-meta">{escape(country["region"])} · {escape(field)}</span>
                        <h3>{escape(country["name"])}</h3>
                        <p>{escape(analysis["interpretation"])}</p>
                        <div class="metric-bars">{metric_html}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "상세 인사이트  →",
                    key=f"open_opportunity_{country['iso3']}",
                    width="stretch",
                ):
                    selected_result = analysis

    if selected_result is not None:
        show_opportunity_dialog(selected_result, field)


# 5. 최상위 기회의 점수와 데이터 신뢰도를 신호 맵으로 표시
def show_signal_map(top_analysis):
    score = top_analysis["analysis"]["score"]
    confidence = top_analysis["data_status"]["completeness"]
    st.markdown(
        f"""
        <section class="signals-section" id="signal-map">
            <div class="signal-copy">
                <span class="eyebrow">SIGNAL MAP</span>
                <h2>의사결정에 필요한 신호만<br>선명하게 연결합니다.</h2>
                <p>단순한 국가 순위가 아니라, 협력이 실제 성과로 이어질 조건을 함께 보여줍니다.</p>
                <ul>
                    <li><i>◎</i><span><strong>기회 탐지</strong>정책 변화와 협력사업 신호를 비교합니다.</span></li>
                    <li><i>◇</i><span><strong>리스크 보정</strong>주의 요인과 데이터 공백을 분리해 확인합니다.</span></li>
                    <li><i>✦</i><span><strong>실행 제안</strong>근거와 함께 다음 협력 모델을 제안합니다.</span></li>
                </ul>
            </div>
            <div class="signal-visual">
                <div class="radar-field">
                    <span class="orbit orbit-one"></span>
                    <span class="orbit orbit-two"></span>
                    <span class="orbit orbit-three"></span>
                    <span class="radar-line"></span>
                    <span class="signal-dot dot-one"><i>정책</i></span>
                    <span class="signal-dot dot-two"><i>기회</i></span>
                    <span class="signal-dot dot-three"><i>실행</i></span>
                    <span class="radar-core"><small>AI SCORE</small><strong>{score:.0f}</strong></span>
                </div>
                <div class="confidence-card">
                    <span>분석 신뢰도</span><strong>{confidence}%</strong>
                    <div><i style="width:{confidence}%"></i></div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


# 6. 설명 가능한 분석 절차를 세 단계로 표시
def show_methodology():
    st.markdown(
        """
        <section class="method-section">
            <span class="eyebrow">OPEN METHODOLOGY</span>
            <h2>설명 가능한 AI, 검증 가능한 판단</h2>
            <p>모든 점수는 데이터 출처와 산정 기준을 추적할 수 있도록 설계했습니다.</p>
            <div class="method-grid">
                <article><span>01</span><strong>신호 수집</strong><p>공개 외교·정책·사업 데이터를 표준화합니다.</p></article>
                <article><span>02</span><strong>관계 분석</strong><p>국가·분야·기관 사이의 연결 강도를 계산합니다.</p></article>
                <article><span>03</span><strong>근거 검토</strong><p>AI 추천을 원문 근거와 함께 확인하고 보정합니다.</p></article>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


# 7. 랜딩 페이지에서 분석 조건과 우선 기회·신호·방법론을 순서대로 구성
def show_analysis_page(data, options):
    show_landing_intro(data, options)

    st.markdown(
        """
        <div class="section-heading" id="priority-opportunities">
            <div><span class="eyebrow">PRIORITY OPPORTUNITIES</span>
            <h2>우선 협력 기회 리포트</h2>
            <p>현재 데이터의 적합도와 실행 가능성을 기준으로 정렬했습니다.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 7.1. 분야와 사용자 유형을 카드 전체에 공통 적용
    with st.container(key="opportunity_filters"):
        field_column, persona_column = st.columns([1.6, 1])
        with field_column:
            # 같은 항목을 다시 눌러도 선택이 해제되지 않는 필수 단일 선택 메뉴
            field = st.radio(
                "분석 분야",
                options["fields"],
                index=0,
                horizontal=True,
                key="opportunity_field",
                on_change=restart_animations,
            )
        with persona_column:
            persona = st.selectbox(
                "사용자 유형",
                options["personas"],
                key="opportunity_persona",
                on_change=restart_animations,
            )

    # 7.2. 모든 후보국을 분석하고 점수순으로 정렬
    results = [
        load_analysis(row.iso3, persona, field)[0]
        for _, row in data.iterrows()
    ]
    results.sort(key=lambda item: item["analysis"]["score"], reverse=True)

    show_opportunity_cards(results, field)
    st.markdown(
        f'<div class="show-all-note">기회 {len(results)}개 모두 표시 중&nbsp; ↓</div>',
        unsafe_allow_html=True,
    )
    show_signal_map(results[0])
    show_methodology()
