from __future__ import annotations

from .taxonomy import classify_sector as legacy_classify_sector


TERMS = {
    "education": (
        "교육", "교사", "교원", "학교", "대학", "한국학", "한국어", "이러닝",
        "e-learning", "education", "teacher", "university", "korean studies",
    ),
    "vocational": (
        "직업훈련", "기술교육", "청년", "취업", "역량강화", "인력양성",
        "tvet", "vocational", "skills", "workforce",
    ),
    "health": (
        "보건", "의료", "병원", "감염병", "모자보건", "공중보건",
        "health", "medical", "hospital", "public health",
    ),
    "climate_agri": (
        "농업", "농촌", "기후", "환경", "산림", "수자원", "에너지",
        "agriculture", "climate", "environment", "forestry", "water resource",
    ),
    "korean_culture": (
        "한류", "문화", "예술", "공공외교", "문화교류", "k-pop",
        "culture", "arts", "public diplomacy",
    ),
}


def classify_sector(text: str) -> tuple[str | None, float]:
    """UTF-8 Korean/English deterministic classifier with legacy fallback."""
    lowered = text.casefold()
    hits = {code: sum(term.casefold() in lowered for term in terms) for code, terms in TERMS.items()}
    best = max(hits, key=hits.get)
    if hits[best] == 0:
        return legacy_classify_sector(text)
    ordered = sorted(hits.values(), reverse=True)
    margin = hits[best] - (ordered[1] if len(ordered) > 1 else 0)
    confidence = min(0.99, 0.65 + 0.10 * hits[best] + 0.05 * margin)
    return best, confidence
