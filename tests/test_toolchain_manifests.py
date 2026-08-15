from __future__ import annotations

import json
import re
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]


class ToolchainManifestTests(unittest.TestCase):
    def test_tool_sources_are_immutable_and_confined(self) -> None:
        lock = json.loads((ROOT / "third_party" / "tools.lock.json").read_text(encoding="utf-8"))
        entries = [*lock["tools"], *lock["comfyuiCustomNodes"]]
        ids = [entry["id"] for entry in entries]
        self.assertEqual(len(ids), len(set(ids)))
        for entry in entries:
            self.assertTrue(entry["url"].startswith("https://github.com/"), entry["id"])
            self.assertRegex(entry["revision"], re.compile(r"^[0-9a-f]{40}$"))
            path = PurePosixPath(entry["path"])
            self.assertFalse(path.is_absolute())
            self.assertNotIn("..", path.parts)
            self.assertTrue(entry.get("license"))

    def test_models_are_manual_and_hashes_are_well_formed(self) -> None:
        lock = json.loads((ROOT / "third_party" / "models.lock.json").read_text(encoding="utf-8"))
        for model in lock["models"]:
            self.assertFalse(model["automaticDownload"], model["id"])
            self.assertTrue(model["source"].startswith("https://"), model["id"])
            if model.get("sha256"):
                self.assertRegex(model["sha256"], re.compile(r"^[0-9a-f]{64}$"))


if __name__ == "__main__":
    unittest.main()
