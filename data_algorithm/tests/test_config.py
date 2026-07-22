from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from opportunity_radar.config import load_env


class ConfigTest(unittest.TestCase):
    def test_load_env_without_overwriting_existing_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("A=from_file\nB=\"quoted value\"\n", encoding="utf-8")
            os.environ["A"] = "existing"
            loaded = load_env(path)
            self.assertEqual(loaded["A"], "from_file")
            self.assertEqual(os.environ["A"], "existing")
            self.assertEqual(os.environ["B"], "quoted value")
            os.environ.pop("A", None)
            os.environ.pop("B", None)


if __name__ == "__main__":
    unittest.main()
