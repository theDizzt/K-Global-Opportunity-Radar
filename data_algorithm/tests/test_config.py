from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from opportunity_radar.config import find_env_file, load_env


class ConfigTest(unittest.TestCase):
    def test_find_env_file_searches_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "repo" / "data_algorithm"
            nested.mkdir(parents=True)
            env_path = root / ".env"
            env_path.write_text("A=from_parent\n", encoding="utf-8")
            self.assertEqual(find_env_file(nested), env_path)

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
