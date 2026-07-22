from config.constants import FIELD_SCORES, PERSONA_WEIGHTS


def calculate_score(row, persona, field):
    weights = PERSONA_WEIGHTS[persona]
    base_score = sum(getattr(row, column) * weight for column, weight in weights.items())
    field_score = FIELD_SCORES[field][row.iso3]

    return round(base_score * 0.78 + field_score * 0.22, 1)


def get_score_level(score):
    if score >= 85:
        return "매우 높음"
    if score >= 75:
        return "높음"
    if score >= 65:
        return "보통"

    return "검토 필요"


def get_analysis_metrics(row, field):
    return [
        ("수요성", round(row.oda * 0.72 + FIELD_SCORES[field][row.iso3] * 0.28), "teal", "●"),
        ("정책 정합성", round(row.diplomacy * 0.60 + row.esg * 0.40), "blue", "▤"),
        ("한국 연계기반", int(row.korean_base), "teal", "↗"),
        ("실행 준비도", round(row.people_exchange * 0.65 + row.completeness * 0.35), "blue", "✓"),
    ]
