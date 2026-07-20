from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config.constants import PROJECTS


def make_report_pdf(row, persona, field, score):
    def pdf_safe(value):
        return str(value).replace("·", "-").replace("→", "->")

    buffer = BytesIO()
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "KTitle",
        parent=styles["Title"],
        fontName="HYSMyeongJo-Medium",
        fontSize=20,
        leading=26,
        textColor=colors.HexColor("#123A5C"),
        alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        "KHeading",
        parent=styles["Heading2"],
        fontName="HYSMyeongJo-Medium",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#078C8A"),
        spaceBefore=8,
        spaceAfter=5,
    )
    body_style = ParagraphStyle(
        "KBody",
        parent=styles["BodyText"],
        fontName="HYSMyeongJo-Medium",
        fontSize=9.3,
        leading=14,
        textColor=colors.HexColor("#273B4D"),
    )

    project = PROJECTS[row.iso3]
    story = [
        Paragraph("K-Global Opportunity Radar", title_style),
        Paragraph(f"{row.country} {pdf_safe(field)} 분야 초기 사업 검토안", title_style),
        Spacer(1, 5 * mm),
    ]
    summary_data = [
        ["사용자", pdf_safe(persona), "분석 분야", pdf_safe(field)],
        ["기회점수", f"{score:.1f} / 100", "데이터 신뢰도", f"{row.completeness}%"],
        ["안전 주의지표", row.risk_level, "기준일", row.updated],
    ]
    summary_table = Table(summary_data, colWidths=[25 * mm, 55 * mm, 30 * mm, 52 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "HYSMyeongJo-Medium"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF6F3")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EAF6F3")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8E3EB")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story += [
        summary_table,
        Paragraph("AI 종합 해석", heading_style),
        Paragraph(pdf_safe(project["summary"]), body_style),
        Paragraph("추천 협력 모델", heading_style),
        Paragraph(" / ".join(project["models"]), body_style),
        Paragraph("협력 파트너 유형", heading_style),
        Paragraph(pdf_safe(project["partners"]), body_style),
        Paragraph("ESG-SDGs 연결", heading_style),
        Paragraph(pdf_safe(project["sdgs"]), body_style),
        Paragraph("주의 요인", heading_style),
        Paragraph(" / ".join(project["cautions"]), body_style),
        Paragraph("근거 데이터와 한계", heading_style),
        Paragraph(
            "외교부 Open Data, KOICA, KF 데이터포털, 해외안전여행 데이터를 국가 단위로 결합한 시연용 정제 데이터입니다. 실제 사업 결정 전 최신 원문과 현지 정보를 다시 확인해야 합니다.",
            body_style,
        ),
        Spacer(1, 4 * mm),
        Paragraph("DEMO - 추가 확인과 내부 논의를 위한 초기 초안", body_style),
    ]

    document.build(story)
    return buffer.getvalue()
