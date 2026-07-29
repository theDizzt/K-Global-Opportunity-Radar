"""근거 기반 보고서 서비스와 캐시 동작 테스트."""

import tempfile
import unittest
from pathlib import Path

from backend.database.connection import get_connection
from backend.database.init_db import initialize_database
from backend.models.analysis import AnalysisField, Persona
from backend.models.report import (
    CitedList,
    CitedText,
    GeneratedReportDraft,
    ReportRequest,
)
from backend.repositories.analysis_repository import AnalysisRepository
from backend.repositories.country_repository import CountryRepository
from backend.repositories.report_repository import ReportRepository
from backend.services.report_service import build_report


class DisabledGenerator:
    is_configured = False
    model = "disabled"


class StubGenerator:
    is_configured = True
    model = "test-model"

    def __init__(self, *, evidence_id=None, error=None):
        self.evidence_id = evidence_id
        self.error = error
        self.calls = 0

    def generate(self, context):
        self.calls += 1
        if self.error is not None:
            raise self.error
        evidence_id = self.evidence_id or context["evidence"][0]["evidence_id"]
        cited_text = lambda text: CitedText(text=text, evidence_ids=[evidence_id])
        cited_list = lambda *items: CitedList(
            items=list(items),
            evidence_ids=[evidence_id],
        )
        return GeneratedReportDraft(
            project_title=cited_text("교육 협력 실증 검토안"),
            background=cited_text("공개 근거에 기반한 초기 검토 배경입니다."),
            local_demand=cited_text("근거 문서에서 교육 협력 신호가 확인됩니다."),
            korean_capabilities=cited_text("입력된 데이터 분석 역량을 검토합니다."),
            target_beneficiaries=cited_list("구체적 수혜자는 추가 확인 필요"),
            partner_types=cited_list("현지 교육기관 유형"),
            implementation_steps=cited_list("원문 재확인", "소규모 실증 검토"),
            risks=cited_list("최신 현지 여건 추가 확인 필요"),
            additional_checks=cited_list("참여 의사와 예산 조건 확인"),
        )


class ReportServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "report.db"
        initialize_database(self.database_path, reset=True)
        self.analysis_repository = AnalysisRepository(self.database_path)
        self.country_repository = CountryRepository(self.database_path)
        self.report_repository = ReportRepository(self.database_path)
        self.request = ReportRequest(
            country_iso3="vnm",
            persona=Persona.STUDENT_TEAM,
            field=AnalysisField.EDUCATION,
            capabilities=["데이터 분석", "에듀테크"],
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_builds_rule_based_report_then_reuses_cache(self):
        country = self.country_repository.get_by_iso3("VNM")
        first = build_report(
            country,
            self.request,
            analysis_repo=self.analysis_repository,
            report_repo=self.report_repository,
            report_generator=DisabledGenerator(),
        )
        second = build_report(
            country,
            self.request,
            analysis_repo=self.analysis_repository,
            report_repo=self.report_repository,
            report_generator=DisabledGenerator(),
        )

        self.assertEqual(first.status, "fallback")
        self.assertEqual(first.generation_mode, "rule_based")
        self.assertEqual(second.status, "cached")
        self.assertEqual(first.request_hash, second.request_hash)
        self.assertEqual(self.report_repository.count(), 1)
        self.assertTrue(first.sources)
        self.assertTrue(first.citations)
        self.assertTrue(all(source.source_url for source in first.sources))

    def test_builds_llm_report_with_validated_citations_then_reuses_cache(self):
        country = self.country_repository.get_by_iso3("VNM")
        generator = StubGenerator()

        first = build_report(
            country,
            self.request,
            analysis_repo=self.analysis_repository,
            report_repo=self.report_repository,
            report_generator=generator,
        )
        second = build_report(
            country,
            self.request,
            analysis_repo=self.analysis_repository,
            report_repo=self.report_repository,
            report_generator=generator,
        )

        self.assertEqual(first.status, "generated")
        self.assertEqual(first.generation_mode, "llm")
        self.assertEqual(first.llm_model, "test-model")
        self.assertEqual(second.status, "cached")
        self.assertEqual(generator.calls, 1)
        self.assertEqual(len(first.sources), 1)
        cited_id = first.sources[0].evidence_id
        self.assertTrue(
            all(cited_id in evidence_ids for evidence_ids in first.citations.values())
        )

    def test_rejects_unknown_llm_evidence_and_does_not_cache_failure(self):
        country = self.country_repository.get_by_iso3("VNM")
        generator = StubGenerator(evidence_id="invented:evidence")

        result = build_report(
            country,
            self.request,
            analysis_repo=self.analysis_repository,
            report_repo=self.report_repository,
            report_generator=generator,
        )

        self.assertEqual(result.status, "fallback")
        self.assertEqual(result.generation_mode, "rule_based")
        self.assertIn("응답 검증에 실패", result.notice)
        self.assertEqual(self.report_repository.count(), 0)

    def test_blocks_generation_when_no_evidence_exists(self):
        with get_connection(self.database_path) as connection:
            connection.execute("DELETE FROM evidence WHERE country_iso3 = 'VNM'")

        country = self.country_repository.get_by_iso3("VNM")
        result = build_report(
            country,
            self.request,
            analysis_repo=self.analysis_repository,
            report_repo=self.report_repository,
            report_generator=DisabledGenerator(),
        )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.generation_mode, "none")
        self.assertEqual(result.sources, [])
        self.assertEqual(self.report_repository.count(), 0)


if __name__ == "__main__":
    unittest.main()
