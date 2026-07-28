from __future__ import annotations

import os


# 1. KF·MOFA·KOICA가 함께 사용할 공공데이터포털 인증키 조회
def public_data_service_key() -> str:
    """Return the generic portal key, falling back to the existing KOICA key."""
    value = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip()
    if not value:
        value = os.getenv("KOICA_SERVICE_KEY", "").strip()
    if not value:
        raise RuntimeError(
            "DATA_GO_KR_SERVICE_KEY (or KOICA_SERVICE_KEY) is empty. "
            "Add the public data portal key to .env."
        )
    return value
