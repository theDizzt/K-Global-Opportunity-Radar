# 0. 모듈 불러오기
import os
from pathlib import Path


# 1. 프로젝트 내부 파일과 데이터베이스 경로 설정
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "countries.csv"
DATABASE_PATH = ROOT_DIR / "data" / "k_global_radar.db"
STYLE_PATH = ROOT_DIR / "styles" / "dashboard.css"
# 2. 백엔드 API 연결과 SQLite 안전 모드 환경변수 설정
API_BASE_URL = os.getenv("K_GLOBAL_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
API_TIMEOUT = float(os.getenv("K_GLOBAL_API_TIMEOUT", "2.0"))
API_FALLBACK_ENABLED = os.getenv("K_GLOBAL_API_FALLBACK", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# 3. 외교부 LOD 수집 요청 설정
MOFA_SPARQL_TIMEOUT = float(os.getenv("MOFA_SPARQL_TIMEOUT", "20"))
MOFA_COLLECTION_LIMIT = int(os.getenv("MOFA_COLLECTION_LIMIT", "100"))

# 4. Streamlit 페이지 기본 설정
PAGE_CONFIG = {
    "page_title": "외교협력 기회 레이더",
    "page_icon": "🌐",
    "layout": "wide",
    "initial_sidebar_state": "collapsed",
}

