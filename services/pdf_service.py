from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def make_report_pdf(result):
    country = result["country"]
    analysis = result["analysis"]
    status = result["data_status"]
    risks = result["risks"]

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

    risk_level = risks[0]["level"] if risks else "확인 필요"
    story = [
        Paragraph("K-Global Opportunity Radar", title_style),
        Paragraph(
            f"{escape(country['name'])} {escape(analysis['field'])} 분야 초기 사업 검토안",
            title_style,
        ),
        Spacer(1, 5 * mm),
    ]
    summary_data = [
        ["사용자", analysis["persona"], "분석 분야", analysis["field"]],
        ["기회점수", f"{analysis['score']:.1f} / 100", "데이터 신뢰도", f"{status['completeness']}%"],
        ["안전 주의지표", risk_level, "기준일", status["reference_date"]],
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
        Paragraph(escape(result["interpretation"]), body_style),
        Paragraph("추천 협력 모델", heading_style),
        Paragraph(" / ".join(map(escape, result["recommendations"])), body_style),
        Paragraph("협력 파트너 유형", heading_style),
        Paragraph(escape(result["partner_types"]), body_style),
        Paragraph("ESG-SDGs 연결", heading_style),
        Paragraph(escape(result["sdgs"]), body_style),
        Paragraph("주의 요인", heading_style),
        Paragraph(" / ".join(escape(risk["title"]) for risk in risks), body_style),
        Paragraph("근거 데이터와 한계", heading_style),
        Paragraph(escape(status["notice"]), body_style),
        Spacer(1, 4 * mm),
        Paragraph("DEMO - 추가 확인과 내부 논의를 위한 초기 초안", body_style),
    ]

    document.build(story)
    return buffer.getvalue()
