from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ui_rebuilder.workspace import build_workspace, plan_workspace, validate_workspace


class WorkspaceTests(unittest.TestCase):
    def _style(self, style_id: str, action: str) -> dict:
        return {
            "schemaVersion": 1,
            "id": style_id,
            "status": "approved",
            "tokens": {
                "colors": {"surface.paper": "#EEE8DC", "text.primary": "#332F28", "action.primary": action},
                "spacing": {"sm": 8},
                "typography": {"primary": {"family": "Inter"}},
            },
            "reconstruction": {"methodPriority": ["extract", "repair"], "dynamicContent": ["text"]},
        }

    def _project(self, root: Path, styles: list[tuple[str, str]]) -> None:
        (root / "styles").mkdir(parents=True)
        Image.new("RGB", (160, 90), "#eee8dc").save(root / "reference.png")
        for style_id, color in styles:
            (root / "styles" / f"{style_id}.json").write_text(
                json.dumps(self._style(style_id, color)), encoding="utf-8"
            )
        job = {
            "schemaVersion": 1,
            "id": "screen",
            "reference": {"path": "reference.png"},
            "styleProfile": f"styles/{styles[0][0]}.json",
            "layout": {
                "kind": "inline",
                "screen": {"name": "Screen", "type": "frame", "bounds": [0, 0, 160, 90]},
                "nodes": [
                    {"name": "Panel", "type": "frame", "parent": "Screen", "bounds": [10, 10, 140, 70]},
                    {"name": "Title", "type": "text", "parent": "Panel", "bounds": [8, 8, 80, 20], "text": "Title"},
                ],
            },
            "outputs": ["package"],
        }
        (root / "job.json").write_text(json.dumps(job), encoding="utf-8")

    def _workspace(self, root: Path) -> Path:
        self._project(root / "cultivation", [("ink", "#426E68"), ("dark", "#55436E")])
        self._project(root / "space", [("neon", "#1678B8")])
        workspace = {
            "schemaVersion": 1,
            "id": "fixture-workspace",
            "outputRoot": "output",
            "maxWorkers": 3,
            "defaults": {"skipOpenPencil": True},
            "projects": [
                {
                    "id": "cultivation",
                    "root": "cultivation",
                    "styles": [
                        {"id": "ink", "profile": "styles/ink.json"},
                        {"id": "dark", "profile": "styles/dark.json"},
                    ],
                    "tasks": [{"id": "training", "job": "job.json", "styles": ["ink", "dark"]}],
                },
                {
                    "id": "space",
                    "root": "space",
                    "styles": [{"id": "neon", "profile": "styles/neon.json"}],
                    "tasks": [{"id": "dashboard", "job": "job.json", "styles": ["neon"]}],
                },
            ],
        }
        path = root / "workspace.json"
        path.write_text(json.dumps(workspace), encoding="utf-8")
        return path

    def test_workspace_builds_projects_and_styles_in_parallel(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace_path = self._workspace(root)
            report = build_workspace(workspace_path, max_workers=3, force=True, skip_openpencil=True)
            self.assertTrue(report["valid"])
            self.assertEqual(report["taskCount"], 3)
            self.assertEqual(report["succeeded"], 3)
            for project_id, style_id, task_id in [
                ("cultivation", "ink", "training"),
                ("cultivation", "dark", "training"),
                ("space", "neon", "dashboard"),
            ]:
                output = root / "output" / project_id / style_id / task_id
                uiir = json.loads((output / "uiir.json").read_text(encoding="utf-8"))
                self.assertEqual(uiir["styleProfile"]["id"], style_id)
                self.assertEqual(
                    uiir["metadata"]["workspace"],
                    {
                        "workspaceId": "fixture-workspace",
                        "projectId": project_id,
                        "styleId": style_id,
                        "taskId": task_id,
                    },
                )
            validation = validate_workspace(workspace_path)
            self.assertTrue(validation["valid"])
            self.assertTrue((root / "output" / "workspace-build.json").is_file())
            self.assertTrue((root / "output" / "workspace-validation.json").is_file())

    def test_workspace_selection_filters_build_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace_path = self._workspace(Path(raw))
            plan = plan_workspace(workspace_path, projects={"cultivation"}, styles={"dark"})
            self.assertEqual(len(plan["tasks"]), 1)
            self.assertEqual(plan["tasks"][0]["styleId"], "dark")

    def test_workspace_rejects_output_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace_path = self._workspace(root)
            workspace = json.loads(workspace_path.read_text(encoding="utf-8"))
            workspace["projects"][0]["tasks"][0]["output"] = "shared-output"
            workspace_path.write_text(json.dumps(workspace), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate workspace output path"):
                plan_workspace(workspace_path)

    def test_workspace_rejects_style_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace_path = self._workspace(root)
            style_path = root / "cultivation" / "styles" / "ink.json"
            style = json.loads(style_path.read_text(encoding="utf-8"))
            style["id"] = "wrong-style"
            style_path.write_text(json.dumps(style), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must match style profile id"):
                plan_workspace(workspace_path)

    def test_workspace_preserves_successes_when_one_task_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace_path = self._workspace(root)
            broken_job = json.loads((root / "space" / "job.json").read_text(encoding="utf-8"))
            broken_job["reference"]["path"] = "missing-reference.png"
            (root / "space" / "broken-job.json").write_text(json.dumps(broken_job), encoding="utf-8")
            workspace = json.loads(workspace_path.read_text(encoding="utf-8"))
            workspace["projects"][1]["tasks"][0]["job"] = "broken-job.json"
            workspace_path.write_text(json.dumps(workspace), encoding="utf-8")

            report = build_workspace(workspace_path, max_workers=3, force=True, skip_openpencil=True)
            self.assertFalse(report["valid"])
            self.assertEqual(report["succeeded"], 2)
            self.assertEqual(report["failed"], 1)
            self.assertTrue((root / "output" / "cultivation" / "ink" / "training" / "uiir.json").is_file())
            failed = next(item for item in report["results"] if not item["valid"])
            self.assertEqual(failed["projectId"], "space")
            self.assertIn("Reference image not found", failed["error"])


if __name__ == "__main__":
    unittest.main()
