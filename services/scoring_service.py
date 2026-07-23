# 0. 점수 계산에 사용하는 가중치와 분야별 시범점수 불러오기
from config.constants import FIELD_SCORES, PERSONA_WEIGHTS


# 데이터·알고리즘 파이프라인의 네 가지 점수 차원에 대한 사용자 유형별 가중치
PERSONA_DIMENSION_WEIGHTS = {
    "대학생 팀": {
        "demand_score": 0.25,
        "policy_alignment_score": 0.20,
        "readiness_score": 0.25,
        "korean_base_score": 0.30,
    },
    "스타트업": {
        "demand_score": 0.35,
        "policy_alignment_score": 0.20,
        "readiness_score": 0.35,
        "korean_base_score": 0.10,
    },
    "공공기관·지자체": {
        "demand_score": 0.25,
        "policy_alignment_score": 0.35,
        "readiness_score": 0.20,
        "korean_base_score": 0.20,
    },
    "기업 ESG팀": {
        "demand_score": 0.30,
        "policy_alignment_score": 0.30,
        "readiness_score": 0.30,
        "korean_base_score": 0.10,
    },
    "청년 구직자": {
        "demand_score": 0.25,
        "policy_alignment_score": 0.15,
        "readiness_score": 0.40,
        "korean_base_score": 0.20,
    },
}


# 1. 사용자 유형 가중치와 분야 적합도를 결합한 종합점수 계산
# 실제 알고리즘 점수가 없을 때만 사용하는 시범 데이터 폴백입니다.
def calculate_score(row, persona, field):
    weights = PERSONA_WEIGHTS[persona]
    base_score = sum(getattr(row, column) * weight for column, weight in weights.items())
    field_score = FIELD_SCORES[field][row.iso3]

    return round(base_score * 0.78 + field_score * 0.22, 1)


# 1.1. 실제 국가·분야 세부점수에 사용자 유형 가중치 적용
def calculate_opportunity_score(score_record, persona):
    weights = PERSONA_DIMENSION_WEIGHTS[persona]
    return round(
        sum(getattr(score_record, code) * weight for code, weight in weights.items()),
        1,
    )


# 2. 종합점수를 화면에 표시할 등급으로 변환
def get_score_level(score):
    if score >= 85:
        return "매우 높음"
    if score >= 75:
        return "높음"
    if score >= 65:
        return "보통"

    return "검토 필요"


# 3. 수요성·정책 정합성·한국 연계기반·실행 준비도 계산
def get_analysis_metrics(row, field):
    return [
        ("수요성", round(row.oda * 0.72 + FIELD_SCORES[field][row.iso3] * 0.28), "teal", "●"),
        ("정책 정합성", round(row.diplomacy * 0.60 + row.esg * 0.40), "blue", "▤"),
        ("한국 연계기반", int(row.korean_base), "teal", "↗"),
        ("실행 준비도", round(row.people_exchange * 0.65 + row.completeness * 0.35), "blue", "✓"),
    ]


# 3.1. 실제 알고리즘 점수를 기존 화면의 네 가지 지표 형식으로 변환
def get_opportunity_metrics(score_record):
    return [
        ("수요성", round(score_record.demand_score), "teal", "●"),
        ("정책 정합성", round(score_record.policy_alignment_score), "blue", "▤"),
        ("한국 연계기반", round(score_record.korean_base_score), "teal", "↗"),
        ("실행 준비도", round(score_record.readiness_score), "blue", "✓"),
    ]
