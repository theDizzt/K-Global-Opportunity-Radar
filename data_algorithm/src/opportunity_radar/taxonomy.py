from __future__ import annotations

SECTORS = {
    "education": {
        "name_ko": "교육·디지털교육",
        "weights": {"demand": 0.40, "alignment": 0.20, "readiness": 0.20, "korea_base": 0.20},
        "terms": ["교육", "교사", "학교", "에듀테크", "디지털교육", "이러닝", "e-learning", "education", "teacher"],
    },
    "vocational": {
        "name_ko": "직업훈련·청년역량",
        "weights": {"demand": 0.50, "alignment": 0.20, "readiness": 0.25, "korea_base": 0.05},
        "terms": ["직업훈련", "기술교육", "청년", "취업", "역량강화", "TVET", "vocational", "skills"],
    },
    "health": {
        "name_ko": "보건·의료협력",
        "weights": {"demand": 0.55, "alignment": 0.20, "readiness": 0.25, "korea_base": 0.00},
        "terms": ["보건", "의료", "병원", "감염병", "모자보건", "health", "medical", "hospital"],
    },
    "climate_agri": {
        "name_ko": "농업·기후·환경",
        "weights": {"demand": 0.55, "alignment": 0.20, "readiness": 0.25, "korea_base": 0.00},
        "terms": ["농업", "농촌", "기후", "환경", "산림", "수자원", "agriculture", "climate", "environment"],
    },
    "korean_culture": {
        "name_ko": "한국어·한국학·문화교류",
        "weights": {"demand": 0.10, "alignment": 0.20, "readiness": 0.10, "korea_base": 0.60},
        "terms": ["한국어", "한국학", "한류", "문화", "예술", "K-POP", "Korean studies", "culture", "arts"],
    },
}

EVENT_WEIGHTS = {
    "agreement": 1.00,
    "joint_project": 0.80,
    "high_level_meeting": 0.60,
    "embassy_activity": 0.30,
    "press_mention": 0.15,
}

SOURCE_WEIGHTS = {"LOD": 1.0, "MOFA": 0.9, "KOICA": 1.0, "KF": 0.9}


def classify_sector(text: str) -> tuple[str | None, float]:
    """Deterministic first-pass classifier; ambiguous records remain unclassified."""
    lowered = text.casefold()
    hits = {
        code: sum(1 for term in config["terms"] if term.casefold() in lowered)
        for code, config in SECTORS.items()
    }
    best = max(hits, key=hits.get)
    if hits[best] == 0:
        return None, 0.0
    ordered = sorted(hits.values(), reverse=True)
    margin = hits[best] - (ordered[1] if len(ordered) > 1 else 0)
    confidence = min(0.99, 0.65 + 0.10 * hits[best] + 0.05 * margin)
    return best, confidence
