from __future__ import annotations


SECTORS = {
    "education": {
        "name_ko": "교육",
        "weights": {"demand": 0.35, "alignment": 0.20, "readiness": 0.20, "korea_base": 0.25},
        "terms": (
            "교육", "교원", "교사", "학교", "교육과정", "교육정책", "이러닝",
            "education", "teacher", "school", "curriculum", "e-learning",
        ),
    },
    "digital": {
        "name_ko": "디지털·ICT",
        "weights": {"demand": 0.45, "alignment": 0.25, "readiness": 0.30, "korea_base": 0.00},
        "terms": (
            "디지털", "정보통신", "정보화", "인공지능", "데이터", "전자정부", "스마트시티",
            "ICT", "AI", "digital", "data", "e-government", "smart city", "cyber",
        ),
    },
    "health": {
        "name_ko": "보건·의료",
        "weights": {"demand": 0.55, "alignment": 0.20, "readiness": 0.25, "korea_base": 0.00},
        "terms": (
            "보건", "의료", "병원", "감염병", "모자보건", "공중보건", "원격의료", "의약",
            "health", "medical", "hospital", "public health", "disease", "pharmaceutical",
        ),
    },
    "agriculture": {
        "name_ko": "농업·농촌",
        "weights": {"demand": 0.55, "alignment": 0.20, "readiness": 0.25, "korea_base": 0.00},
        "terms": (
            "농업", "농촌", "농가", "농산물", "식량", "축산", "관개", "스마트팜",
            "agriculture", "rural", "farming", "food security", "livestock", "irrigation",
        ),
    },
    "climate_environment": {
        "name_ko": "기후·환경",
        "weights": {"demand": 0.50, "alignment": 0.25, "readiness": 0.25, "korea_base": 0.00},
        "terms": (
            "기후", "환경", "산림", "탄소", "대기오염", "수자원", "재생에너지", "생물다양성",
            "climate", "environment", "forestry", "carbon", "air pollution", "water resource",
            "renewable energy", "biodiversity",
        ),
    },
    "vocational": {
        "name_ko": "직업훈련·인력양성",
        "weights": {"demand": 0.50, "alignment": 0.20, "readiness": 0.25, "korea_base": 0.05},
        "terms": (
            "직업훈련", "직업교육", "기술교육", "취업", "취창업", "인력양성", "역량강화", "청년훈련",
            "TVET", "vocational", "skills training", "workforce", "capacity building",
        ),
    },
    "korean_studies": {
        "name_ko": "한국어·한국학",
        "weights": {"demand": 0.10, "alignment": 0.20, "readiness": 0.10, "korea_base": 0.60},
        "terms": (
            "한국어", "한국학", "세종학당", "한국연구", "한국학과", "코리아코너",
            "Korean language", "Korean studies", "King Sejong Institute", "Korea corner",
        ),
    },
    "culture_content": {
        "name_ko": "문화·콘텐츠",
        "weights": {"demand": 0.15, "alignment": 0.20, "readiness": 0.15, "korea_base": 0.50},
        "terms": (
            "문화", "콘텐츠", "한류", "예술", "공연", "영화", "방송", "웹툰", "음악", "게임",
            "culture", "content", "hallyu", "arts", "performance", "film", "broadcast", "webtoon", "K-POP",
        ),
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

LEGACY_SECTOR_DEFAULTS = {
    "climate_agri": "climate_environment",
    "korean_culture": "culture_content",
}


def classify_sector(text: str) -> tuple[str | None, float]:
    """Classify text into one of the eight competition sectors."""
    lowered = (text or "").casefold()
    hits = {
        code: sum(1 for term in cfg["terms"] if term.casefold() in lowered)
        for code, cfg in SECTORS.items()
    }
    best = max(hits, key=hits.get)
    if hits[best] == 0:
        return None, 0.0
    ordered = sorted(hits.values(), reverse=True)
    second = ordered[1] if len(ordered) > 1 else 0
    margin = hits[best] - second
    confidence = min(0.99, 0.60 + 0.10 * hits[best] + 0.05 * max(0, margin))
    if margin == 0:
        confidence = min(confidence, 0.65)
    return best, confidence


def canonical_sector(code: str | None, text: str = "") -> tuple[str | None, float]:
    """Map current or legacy sector codes to the eight-sector taxonomy."""
    if code in SECTORS:
        return code, 1.0
    if code in LEGACY_SECTOR_DEFAULTS:
        inferred, confidence = classify_sector(text)
        if code == "climate_agri" and inferred in {"agriculture", "climate_environment"}:
            return inferred, confidence
        if code == "korean_culture" and inferred in {"korean_studies", "culture_content"}:
            return inferred, confidence
        return LEGACY_SECTOR_DEFAULTS[code], 0.7
    return classify_sector(text)
