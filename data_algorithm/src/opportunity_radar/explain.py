from __future__ import annotations

import json
import os
import sqlite3
import urllib.request


COMPONENT_NAMES = {
    "demand": "관측된 분야 수요·지원 집중도",
    "alignment": "외교적 협력 정합성",
    "readiness": "기존 사업 수행 기반",
    "korea_base": "한국학·문화·인적 기반",
}


def _topic_particle(word: str) -> str:
    if not word:
        return "은"
    code = ord(word[-1]) - 0xAC00
    return "은" if 0 <= code <= 11171 and code % 28 else "는"


def build_explanation_context(conn: sqlite3.Connection, score_id: int) -> dict:
    score = conn.execute(
        """SELECT s.*, c.name_ko, sec.name_ko sector_name FROM score_snapshot s
           JOIN country c ON c.iso3=s.country_iso3 JOIN sector sec ON sec.code=s.sector_code
           WHERE s.id=?""", (score_id,)
    ).fetchone()
    if not score:
        raise ValueError(f"Unknown score_id: {score_id}")
    components = [dict(r) for r in conn.execute(
        "SELECT component_code, normalized_value, contribution FROM score_component WHERE score_id=? ORDER BY contribution DESC", (score_id,)
    )]
    evidence = [dict(r) for r in conn.execute(
        """SELECT e.id evidence_id, e.event_type, e.event_date, e.supporting_text,
                  r.source_type, r.title, r.source_url
           FROM evidence e JOIN source_record r ON r.id=e.source_record_id
           WHERE e.country_iso3=? AND (
             e.sector_code=? OR EXISTS (
               SELECT 1 FROM record_sector rs
               WHERE rs.source_record_id=e.source_record_id AND rs.sector_code=?))
           ORDER BY e.confidence DESC, e.event_date DESC LIMIT 8""",
        (score["country_iso3"], score["sector_code"], score["sector_code"]),
    )]
    return {"score": dict(score), "components": components, "evidence": evidence}


def template_explanation(context: dict) -> dict:
    score = context["score"]
    top = context["components"][0] if context["components"] else None
    evidence = context["evidence"][:3]
    cautions = []
    if score["data_confidence"] < 80:
        cautions.append("일부 자료의 충족률 또는 최신성이 낮아 추가 확인이 필요합니다.")
    if (score["risk_level"] or 0) >= 2:
        cautions.append(f"해외안전 주의지표가 {score['risk_level']}단계이므로 세부 지역을 확인해야 합니다.")
    if score["sensitivity_high"] - score["sensitivity_low"] > 8:
        cautions.append("가중치 변경에 따라 점수 변동폭이 커서 순위보다 세부지표를 우선 확인해야 합니다.")
    return {
        "summary": f"{score['name_ko']}{_topic_particle(score['name_ko'])} {score['sector_name']} 분야에서 {score['opportunity_score']:.1f}점의 우선 검토 후보입니다.",
        "strengths": [f"가장 큰 기여요인은 {COMPONENT_NAMES.get(top['component_code'], top['component_code'])}({top['normalized_value']:.1f}점)입니다."] if top else [],
        "cautions": cautions,
        "missing_data": [] if score["data_confidence"] >= 80 else ["신뢰도가 낮은 원천의 최신 자료"],
        "next_checks": ["기존 유사사업의 중복 여부", "현지 협력기관과 실제 수요 확인"],
        "evidence_ids": [e["evidence_id"] for e in evidence],
        "evidence": evidence,
    }


class LlmExplainer:
    """OpenAI-compatible chat endpoint adapter with a strict JSON response contract."""
    def __init__(self, api_url: str | None = None, api_key: str | None = None, model: str | None = None):
        self.api_url = api_url or os.getenv("LLM_API_URL")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model or os.getenv("LLM_MODEL")

    def explain(self, context: dict) -> dict:
        if not all((self.api_url, self.api_key, self.model)):
            return template_explanation(context)
        instruction = (
            "당신은 외교 공공데이터 분석 설명기다. 제공된 점수와 evidence만 사용한다. "
            "점수를 재계산하지 말고, evidence에 없는 기관·통계·사업을 만들지 않는다. "
            "근거가 없으면 추가 확인 필요라고 쓴다. summary, strengths, cautions, "
            "missing_data, next_checks, evidence_ids 키를 가진 JSON만 반환한다."
        )
        payload = json.dumps({
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.api_url, data=payload, method="POST", headers={
            "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=60) as response:
            body = json.loads(response.read())
        result = json.loads(body["choices"][0]["message"]["content"])
        valid_ids = {e["evidence_id"] for e in context["evidence"]}
        result["evidence_ids"] = [i for i in result.get("evidence_ids", []) if i in valid_ids]
        return result
