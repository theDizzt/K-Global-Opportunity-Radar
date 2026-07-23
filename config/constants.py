# 1. 사용자 유형별 기회점수 지표 가중치
PERSONA_WEIGHTS = {
    "대학생 팀": {"diplomacy": 0.15, "oda": 0.25, "korean_base": 0.25, "people_exchange": 0.25, "esg": 0.10},
    "스타트업": {"diplomacy": 0.20, "oda": 0.20, "korean_base": 0.15, "people_exchange": 0.20, "esg": 0.25},
    "공공기관·지자체": {"diplomacy": 0.30, "oda": 0.25, "korean_base": 0.15, "people_exchange": 0.15, "esg": 0.15},
    "기업 ESG팀": {"diplomacy": 0.15, "oda": 0.25, "korean_base": 0.10, "people_exchange": 0.15, "esg": 0.35},
    "청년 구직자": {"diplomacy": 0.15, "oda": 0.10, "korean_base": 0.25, "people_exchange": 0.40, "esg": 0.10},
}

# 2. 국가·분야별 시범 적합도 점수
FIELD_SCORES = {
    "교육": {"VNM": 96, "IDN": 84, "MNG": 86},
    "보건": {"VNM": 82, "IDN": 92, "MNG": 91},
    "디지털": {"VNM": 95, "IDN": 90, "MNG": 80},
    "기후·환경": {"VNM": 80, "IDN": 97, "MNG": 94},
    "문화·한류": {"VNM": 96, "IDN": 86, "MNG": 87},
    "청년취업": {"VNM": 94, "IDN": 83, "MNG": 84},
}

# 3. 최근 5년 협력 신호 시범 추세
SIGNAL_HISTORY = {
    "VNM": [48, 59, 68, 79, 91],
    "IDN": [43, 55, 66, 76, 90],
    "MNG": [46, 53, 64, 72, 84],
}

# 4. 국가별 협력 프로젝트와 추천·주의 정보
PROJECTS = {
    "VNM": {
        "title": "K-Skill Bridge",
        "summary": "디지털 교육 수요와 한국 연계기반이 모두 높아 단기 협력사업 발굴 가능성이 큽니다.",
        "models": ["교원 디지털 역량 강화", "에듀테크 공동 실증", "대학·기업 컨소시엄"],
        "partners": "현지 대학·직업교육기관, 한국어교육기관, 에듀테크 기업",
        "sdgs": "SDG 4 - 양질의 교육 / SDG 8 - 양질의 일자리",
        "cautions": ["지역별 교육 인프라 격차", "현지 파트너 검증 필요"],
    },
    "IDN": {
        "title": "Green City Data Lab",
        "summary": "높은 ESG 수요와 활발한 외교 교류를 바탕으로 지역 문제 해결형 실증에 적합합니다.",
        "models": ["도시 기후 데이터 실증", "지역 보건 분석 협력", "지방정부 ESG 랩"],
        "partners": "지방정부, 보건·환경 기관, 대학 연구소, 임팩트 기업",
        "sdgs": "SDG 3 - 건강 / SDG 11 - 지속가능한 도시 / SDG 13 - 기후행동",
        "cautions": ["도서지역 실행비용 고려", "지역별 행정체계 확인"],
    },
    "MNG": {
        "title": "Healthy Air Connect",
        "summary": "한국과의 교류 기반 위에 보건·기후 문제 해결을 결합할 수 있는 후보국입니다.",
        "models": ["대기환경 데이터 협력", "원격 건강교육 실증", "한·몽 대학 공동연구"],
        "partners": "보건기관, 환경연구소, 대학, 원격의료·센서 기업",
        "sdgs": "SDG 3 - 건강 / SDG 13 - 기후행동 / SDG 17 - 파트너십",
        "cautions": ["계절별 데이터 편차", "현지 유지보수 역량 확인"],
    },
}

# 5. 국가별 핵심 근거 시범 데이터
EVIDENCE = {
    "VNM": [
        ("KOICA", "교육·디지털 분야 협력사업 흐름", "개발협력 수요"),
        ("KF", "한국어·한국학 교육 기반", "한국 연계기반"),
        ("MOFA", "교육·디지털 협력 의제", "정책 정합성"),
    ],
    "IDN": [
        ("KOICA", "기후·보건 분야 사업 수요", "개발협력 수요"),
        ("MOFA", "스마트시티·전환 협력 의제", "정책 정합성"),
        ("KF", "한국학·문화교류 기반", "한국 연계기반"),
    ],
    "MNG": [
        ("KOICA", "보건·환경 협력사업 흐름", "개발협력 수요"),
        ("KF", "높은 한국어·한국학 기반", "한국 연계기반"),
        ("MOFA", "보건·기후 협력 의제", "정책 정합성"),
    ],
}

# 6. 공공데이터 제공기관 원문 주소
SOURCE_LINKS = {
    "외교부 Open Data": "https://opendata.mofa.go.kr/lod/",
    "KOICA": "https://www.koica.go.kr/koica_kr/index.do",
    "KF 데이터포털": "https://www.kf.or.kr/koreanstudies/koreaStudiesList.do",
    "해외안전여행": "https://www.0404.go.kr/",
}

# 7. 공공데이터 제공기관별 활용 목적 설명
SOURCE_DESCRIPTIONS = {
    "외교부 Open Data": "외교일지, 보도자료, 국가·기관·사건 관계와 SPARQL 데이터를 확인합니다.",
    "KOICA": "국가별 개발협력 사업과 교육·보건·기후·디지털 분야 수요를 확인합니다.",
    "KF 데이터포털": "해외대학 한국학·한국어 교육과 글로벌 e-스쿨 기반을 확인합니다.",
    "해외안전여행": "국가별 최신 안전정보를 기회점수와 분리된 주의지표로 확인합니다.",
}

