"""실제 키로 OpenAI Structured Outputs 연결만 안전하게 확인한다."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.openai_report_client import (
    OpenAIReportError,
    OpenAIReportGenerator,
)


def main():
    generator = OpenAIReportGenerator.from_environment()
    if not generator.is_configured:
        print(json.dumps({"status": "not_configured"}))
        return 2

    evidence_id = "smoke:evidence:1"
    context = {
        "request": {
            "country_iso3": "VNM",
            "persona": "대학생 팀",
            "field": "교육",
            "capabilities": ["데이터 분석"],
        },
        "analysis": {
            "country": {"name": "베트남"},
            "score": {"notice": "연결 확인용 입력이며 실제 분석 결과가 아님"},
            "metrics": [],
            "trend": [],
            "risks": [],
            "data_status": {"notice": "추가 확인 필요"},
        },
        "evidence": [
            {
                "evidence_id": evidence_id,
                "title": "OpenAI 연결 확인용 근거",
                "category": "연결 테스트",
                "source": "K-Global Opportunity Radar",
                "reference_date": "2026-07-29",
                "source_url": "https://www.mofa.go.kr/",
                "is_demo": True,
            }
        ],
    }

    try:
        draft = generator.generate(context)
    except OpenAIReportError as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "model": generator.model,
                    "reason": str(exc),
                },
                ensure_ascii=False,
            )
        )
        return 1

    sections = draft.model_dump(mode="python").values()
    cited_ids = {
        cited_id
        for section in sections
        for cited_id in section["evidence_ids"]
    }
    print(
        json.dumps(
            {
                "status": "ok",
                "model": generator.model,
                "section_count": len(sections),
                "citations_valid": cited_ids == {evidence_id},
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
