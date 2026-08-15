from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ui_rebuilder.exporters.openpencil_script import render_openpencil_script
from ui_rebuilder.pipeline.layout import from_layout_authority
from ui_rebuilder.pipeline.assets import _nine_slice
from ui_rebuilder.pipeline.package import build_package
from ui_rebuilder.validator import validate_package


class PackageTests(unittest.TestCase):
    def _style(self) -> dict:
        return {
            "schemaVersion": 1,
            "id": "fixture",
            "status": "draft",
            "tokens": {
                "colors": {"surface.paper": "#EEE8DC", "text.primary": "#332F28", "action.primary": "#3D6E66"},
                "spacing": {"sm": 8},
                "typography": {"primary": {"family": "Inter"}},
            },
            "reconstruction": {"methodPriority": ["extract", "repair"], "dynamicContent": ["text"]},
        }

    def test_inline_package_builds_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            Image.new("RGB", (200, 100), "#eee8dc").save(root / "reference.png")
            icon = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
            icon.paste((50, 110, 90, 255), (10, 2, 30, 18))
            icon.save(root / "icon.png")
            style = self._style()
            (root / "style.json").write_text(json.dumps(style), encoding="utf-8")
            job = {
                "schemaVersion": 1,
                "id": "fixture-screen",
                "reference": {"path": "reference.png"},
                "styleProfile": "style.json",
                "layout": {
                    "kind": "inline",
                    "screen": {"name": "Screen", "type": "frame", "bounds": [0, 0, 200, 100]},
                    "nodes": [
                        {"name": "Panel", "type": "frame", "parent": "Screen", "bounds": [10, 10, 180, 80]},
                        {"name": "Title", "type": "text", "parent": "Panel", "bounds": [10, 8, 80, 20], "text": "Title"},
                    ],
                },
                "extraNodes": [
                    {
                        "name": "Status",
                        "type": "rectangle",
                        "parent": "Panel",
                        "bounds": [120, 8, 20, 20],
                    }
                ],
                "assets": [
                    {"id": "panel-crop", "sourceBox": [10, 10, 50, 30], "method": "extracted", "scaling": "none"},
                    {
                        "id": "external-icon",
                        "sourcePath": "icon.png",
                        "method": "extracted",
                        "scaling": "uniform",
                        "targetSize": [20, 20],
                        "alphaRequired": True,
                        "targetNodes": ["Panel", "Status"],
                    },
                ],
                "outputs": ["package"],
            }
            (root / "job.json").write_text(json.dumps(job), encoding="utf-8")
            output = root / "output"
            report = build_package(root / "job.json", output, skip_openpencil=True)
            self.assertEqual(report["nodeCount"], 4)
            self.assertTrue((output / "Assets" / "panel-crop.png").is_file())
            with Image.open(output / "Assets" / "external-icon.png") as processed_icon:
                self.assertEqual(processed_icon.size, (20, 20))
            uiir = json.loads((output / "uiir.json").read_text(encoding="utf-8"))
            panel = next(node for node in uiir["pages"][0]["nodes"] if node["name"] == "Panel")
            status = next(node for node in uiir["pages"][0]["nodes"] if node["name"] == "Status")
            self.assertEqual(panel["asset"]["id"], "external-icon")
            self.assertEqual(status["asset"]["id"], "external-icon")
            self.assertEqual(status["absoluteBounds"], [130.0, 18.0, 20.0, 20.0])
            self.assertTrue(validate_package(output)["valid"])
            (output / "Reports" / "build-state.json").write_text('{"status":"building"}', encoding="utf-8")
            self.assertFalse(validate_package(output)["valid"])

    def test_nine_slice_preserves_corner_pixels(self) -> None:
        source = Image.new("RGBA", (6, 6), (20, 20, 20, 255))
        source.putpixel((0, 0), (255, 0, 0, 255))
        source.putpixel((5, 0), (0, 255, 0, 255))
        source.putpixel((0, 5), (0, 0, 255, 255))
        source.putpixel((5, 5), (255, 255, 0, 255))
        resized = _nine_slice(source, (12, 10), [2, 2, 2, 2], "fixture")
        self.assertEqual(resized.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(resized.getpixel((11, 0)), (0, 255, 0, 255))
        self.assertEqual(resized.getpixel((0, 9)), (0, 0, 255, 255))
        self.assertEqual(resized.getpixel((11, 9)), (255, 255, 0, 255))

    def test_layout_authority_becomes_parent_relative(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "layout.json"
            path.write_text(
                json.dumps(
                    {
                        "screen": "Screen",
                        "referenceSize": [200, 100],
                        "nodes": {
                            "Screen": {"type": "FRAME", "parent": "Page", "bounds": [0, 0, 200, 100]},
                            "Panel": {"type": "FRAME", "parent": "Screen", "bounds": [20, 10, 160, 80]},
                            "Title": {"type": "TEXT", "parent": "Panel", "bounds": [35, 18, 80, 20]},
                        },
                    }
                ),
                encoding="utf-8",
            )
            _, nodes = from_layout_authority(path, self._style())
            by_name = {node["name"]: node for node in nodes}
            self.assertEqual(by_name["Panel"]["bounds"], [20.0, 10.0, 160.0, 80.0])
            self.assertEqual(by_name["Title"]["bounds"], [15.0, 8.0, 80.0, 20.0])

    def test_openpencil_attaches_before_setting_local_geometry(self) -> None:
        uiir = {
            "id": "fixture",
            "pages": [
                {
                    "name": "20_Visual",
                    "nodes": [
                        {
                            "id": "screen",
                            "name": "Screen",
                            "type": "frame",
                            "parent": None,
                            "bounds": [0, 0, 200, 100],
                            "style": {},
                            "provenance": {},
                        }
                    ],
                }
            ],
        }
        script = render_openpencil_script(
            uiir,
            self._style(),
            {"fixture-image": "AA=="},
            [{"id": "fixture-image", "pixelSize": [16, 12], "opacity": 1}],
        )
        attach = script.index("parent.appendChild(node)")
        position = script.index("positionNode(node, spec, parent)", attach)
        self.assertLess(attach, position)
        self.assertIn("Asset/${asset.id}/Runtime", script)
        self.assertIn("figma.createImage", script)


if __name__ == "__main__":
    unittest.main()
