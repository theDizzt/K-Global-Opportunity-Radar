from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "countries.csv"
STYLE_PATH = ROOT_DIR / "styles" / "dashboard.css"

PAGE_CONFIG = {
    "page_title": "외교협력 기회 레이더",
    "page_icon": "🌐",
    "layout": "wide",
    "initial_sidebar_state": "collapsed",
}

