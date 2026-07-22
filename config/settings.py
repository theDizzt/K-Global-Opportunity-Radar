import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "countries.csv"
DATABASE_PATH = ROOT_DIR / "data" / "k_global_radar.db"
STYLE_PATH = ROOT_DIR / "styles" / "dashboard.css"
API_BASE_URL = os.getenv("K_GLOBAL_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
API_TIMEOUT = float(os.getenv("K_GLOBAL_API_TIMEOUT", "2.0"))
API_FALLBACK_ENABLED = os.getenv("K_GLOBAL_API_FALLBACK", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

PAGE_CONFIG = {
    "page_title": "외교협력 기회 레이더",
    "page_icon": "🌐",
    "layout": "wide",
    "initial_sidebar_state": "collapsed",
}

