"""OpenAI Responses API 어댑터의 요청 형식과 오류 처리를 검증한다."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from backend.models.report import CitedList, CitedText, GeneratedReportDraft
from backend.services.openai_report_client import (
    OpenAIReportError,
    OpenAIReportGenerator,
)
from config.llm_settings import OpenAISettings, load_openai_settings


def build_draft():
    cited_text = lambda text: CitedText(text=text, evidence_ids=["evidence:1"])
    cited_list = lambda text: CitedList(items=[text], evidence_ids=["evidence:1"])
    return GeneratedReportDraft(
        project_title=cited_text("검토안"),
        background=cited_text("배경"),
        local_demand=cited_text("수요"),
        korean_capabilities=cited_text("역량"),
        target_beneficiaries=cited_list("수혜자"),
        partner_types=cited_list("파트너"),
        implementation_steps=cited_list("단계"),
        risks=cited_list("위험"),
        additional_checks=cited_list("확인사항"),
    )


def success_response():
    return {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": build_draft().model_dump_json(),
                    }
                ],
            }
        ]
    }


class OpenAIReportClientTestCase(unittest.TestCase):
    def settings(self):
        return OpenAISettings(
            enabled=True,
            api_key="test-key",
            model="test-model",
            timeout_seconds=1,
        )

    def test_sends_stateless_structured_responses_request(self):
        captured = {}

        def handler(request):
            captured["authorization"] = request.headers["Authorization"]
            captured["payload"] = json.loads(request.content)
            return httpx.Response(200, json=success_response())

        generator = OpenAIReportGenerator(
            self.settings(),
            transport=httpx.MockTransport(handler),
            sleep=lambda _: None,
        )
        result = generator.generate({"evidence": [{"evidence_id": "evidence:1"}]})

        self.assertEqual(result.project_title.text, "검토안")
        self.assertEqual(captured["authorization"], "Bearer test-key")
        self.assertEqual(captured["payload"]["model"], "test-model")
        self.assertFalse(captured["payload"]["store"])
        self.assertEqual(
            captured["payload"]["text"]["format"]["type"],
            "json_schema",
        )
        self.assertTrue(captured["payload"]["text"]["format"]["strict"])

    def test_retries_one_transient_failure(self):
        attempts = []

        def handler(request):
            attempts.append(request)
            if len(attempts) == 1:
                return httpx.Response(500, json={"error": {"message": "temporary"}})
            return httpx.Response(200, json=success_response())

        generator = OpenAIReportGenerator(
            self.settings(),
            transport=httpx.MockTransport(handler),
            sleep=lambda _: None,
        )
        result = generator.generate({"evidence": [{"evidence_id": "evidence:1"}]})

        self.assertEqual(result.background.text, "배경")
        self.assertEqual(len(attempts), 2)

    def test_rejects_response_without_output_text(self):
        generator = OpenAIReportGenerator(
            self.settings(),
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"output": []})
            ),
            sleep=lambda _: None,
        )

        with self.assertRaises(OpenAIReportError):
            generator.generate({"evidence": []})

    def test_env_loader_ignores_unrelated_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "OPENAI_API_KEY=test-key\n"
                "OPENAI_MODEL=test-model\n"
                "DISCORD_BOT_TOKEN=must-not-load\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                settings = load_openai_settings(env_path)
                self.assertNotIn("DISCORD_BOT_TOKEN", os.environ)

        self.assertTrue(settings.is_configured)
        self.assertEqual(settings.model, "test-model")
        self.assertNotIn("test-key", repr(settings))


if __name__ == "__main__":
    unittest.main()
