import json
import shutil
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PROJECT_ROOT / "scripts" / "run_auto_collection.ps1"


class AutoCollectionScriptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.powershell = shutil.which("powershell.exe")
        if cls.powershell is None:
            raise unittest.SkipTest("Windows PowerShell is required for scheduler tests.")

    def run_dry_plan(self, *arguments):
        result = subprocess.run(
            [
                self.powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(RUNNER),
                "-DryRun",
                *arguments,
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_default_plan_uses_low_cost_public_sources(self):
        plan = self.run_dry_plan()

        self.assertEqual(plan["sources"], ["lod", "kf_eschool"])
        self.assertFalse(plan["include_koica"])
        self.assertTrue(plan["score_and_sync"])

    def test_authenticated_and_koica_options_extend_plan(self):
        plan = self.run_dry_plan(
            "-IncludeAuthenticatedSources",
            "-IncludeKoica",
            "-KoicaFromYear",
            "2024",
            "-KoicaToYear",
            "2026",
        )

        self.assertEqual(plan["sources"], ["lod", "kf_eschool", "kf", "mofa"])
        self.assertTrue(plan["include_koica"])
        self.assertEqual(plan["koica_years"], "2024-2026")


if __name__ == "__main__":
    unittest.main()
