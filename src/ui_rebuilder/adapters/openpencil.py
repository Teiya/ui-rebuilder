from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..exporters.openpencil_script import render_openpencil_script
from ..util import REPO_ROOT, load_data, write_json


class OpenPencilError(RuntimeError):
    pass


def _layout_conformance(uiir: dict[str, Any], tree: Any, tolerance: float = 0.51) -> dict[str, Any]:
    actual_by_name: dict[str, dict[str, Any]] = {}

    def visit(items: Any) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str):
                actual_by_name[name] = item
            visit(item.get("children"))

    visit(tree)
    expected = [node for page in uiir["pages"] if page["name"] == "20_Visual" for node in page["nodes"]]
    mismatches: list[dict[str, Any]] = []
    for node in expected:
        actual = actual_by_name.get(node["name"])
        if actual is None:
            mismatches.append({"id": node["id"], "name": node["name"], "kind": "missing"})
            continue
        target = node["bounds"]
        observed = [actual.get("x"), actual.get("y"), actual.get("width"), actual.get("height")]
        fields = ["x", "y", "width", "height"]
        deltas: dict[str, float | None] = {}
        for index, field in enumerate(fields):
            value = observed[index]
            if value is None:
                deltas[field] = None
                continue
            delta = float(value) - float(target[index])
            if abs(delta) > tolerance:
                deltas[field] = round(delta, 4)
        if deltas:
            mismatches.append(
                {
                    "id": node["id"],
                    "name": node["name"],
                    "kind": "geometry",
                    "expected": target,
                    "actual": observed,
                    "deltas": deltas,
                }
            )
    return {
        "valid": not mismatches,
        "page": "20_Visual",
        "tolerance": tolerance,
        "expectedNodeCount": len(expected),
        "observedNodeCount": len(actual_by_name),
        "mismatchCount": len(mismatches),
        "mismatches": mismatches,
    }


def _export_conformance(asset_catalog: list[dict[str, Any]], tree: Any, tolerance: float = 0.51) -> dict[str, Any]:
    actual = {item.get("name"): item for item in tree if isinstance(item, dict)} if isinstance(tree, list) else {}
    mismatches: list[dict[str, Any]] = []
    for asset in asset_catalog:
        name = f"Asset/{asset['id']}/Runtime"
        node = actual.get(name)
        if node is None:
            mismatches.append({"id": asset["id"], "kind": "missing", "name": name})
            continue
        expected = asset["pixelSize"]
        observed = [node.get("width"), node.get("height")]
        if node.get("type") != "COMPONENT" or any(
            value is None or abs(float(value) - float(expected[index])) > tolerance
            for index, value in enumerate(observed)
        ):
            mismatches.append(
                {
                    "id": asset["id"],
                    "kind": "component",
                    "expectedSize": expected,
                    "actualSize": observed,
                    "actualType": node.get("type"),
                }
            )
    return {
        "valid": not mismatches,
        "page": "90_Export",
        "tolerance": tolerance,
        "expectedComponentCount": len(asset_catalog),
        "observedComponentCount": len(actual),
        "mismatchCount": len(mismatches),
        "mismatches": mismatches,
    }


def _bun() -> str | None:
    local = REPO_ROOT / "third_party" / ".runtimes" / "bun" / ("bun.exe" if os.name == "nt" else "bun")
    if local.is_file():
        return str(local)
    direct = shutil.which("bun.exe") or shutil.which("bun")
    if direct:
        return direct
    shim = shutil.which("bun.cmd")
    if shim:
        candidate = Path(shim).resolve().parent / "node_modules" / "bun" / "bin" / "bun.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def resolve_cli(explicit_repo: Path | None = None) -> tuple[list[str], dict[str, str]]:
    candidates: list[Path] = []
    if explicit_repo:
        candidates.append(explicit_repo)
    configured = os.environ.get("UI_REBUILDER_OPENPENCIL_ROOT")
    if configured:
        candidates.append(Path(configured))
    candidates.append(REPO_ROOT / "third_party" / "open-pencil")
    candidates.append(REPO_ROOT.parent / "open-pencil")
    for candidate in candidates:
        repo = candidate.expanduser().resolve()
        entry = repo / "packages" / "cli" / "bin" / "openpencil.js"
        dist = repo / "packages" / "cli" / "dist" / "index.mjs"
        if entry.is_file() and dist.is_file():
            bun = _bun()
            if not bun:
                raise OpenPencilError("Bun is required for a repository-backed OpenPencil CLI")
            return [bun, str(entry)], {"source": "repository", "repo": str(repo)}
    executable = shutil.which("openpencil")
    if executable:
        return [executable], {"source": "PATH", "repo": ""}
    raise OpenPencilError("OpenPencil was not found; pass --openpencil-repo or set UI_REBUILDER_OPENPENCIL_ROOT")


def run_cli(
    command: list[str],
    args: list[str],
    *,
    stdin: str | None = None,
    timeout: int = 180,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            [*command, *args],
            input=stdin,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise OpenPencilError(f"OpenPencil timed out after {timeout}s: {' '.join(args)}") from exc
    if check and completed.returncode != 0:
        raise OpenPencilError(completed.stderr.strip() or completed.stdout.strip() or f"OpenPencil failed: {args}")
    return completed


def _contains_pending_note(tree: Any) -> bool:
    if isinstance(tree, list):
        return any(_contains_pending_note(item) for item in tree)
    if not isinstance(tree, dict):
        return False
    name = str(tree.get("name", ""))
    if name.startswith("Note/") and ("Pending" in name or "ConsumerOwned" in name):
        return True
    return _contains_pending_note(tree.get("children"))


def _lint_review(lint_payload: Any, return_code: int) -> dict[str, Any]:
    messages = lint_payload.get("messages", []) if isinstance(lint_payload, dict) else []
    reviewed: list[dict[str, Any]] = []
    counts = {"nonApplicable": 0, "diagnosticOnly": 0, "consumerReviewRequired": 0}
    decorative_terms = ("AssetInstance/", "PreviewText/", "State/LevelMarker/", "Icon/")
    for message in messages:
        item = dict(message) if isinstance(message, dict) else {"message": str(message)}
        path = item.get("nodePath") or []
        page = str(path[0]) if path else ""
        node_name = str(item.get("nodeName", ""))
        rule = str(item.get("ruleId", ""))
        if page in {"00_Foundations", "10_Wireframe", "30_States", "90_Export"}:
            disposition = "diagnosticOnly"
            reason = "Documentation, wireframe, state-catalogue or export-library page; not a shipped interaction surface."
        elif rule == "touch-target-size" and node_name.startswith(decorative_terms):
            disposition = "nonApplicable"
            reason = "Raster preview, decoration or state marker; not an interactive target."
        else:
            disposition = "consumerReviewRequired"
            reason = "Potential issue on the reconstructed visual page; visual/UX owner must accept or revise it."
        item["disposition"] = disposition
        item["dispositionReason"] = reason
        reviewed.append(item)
        counts[disposition] += 1
    return {
        "preset": "accessibility",
        "toolReturnCode": return_code,
        "rawMessageCount": len(messages),
        "counts": counts,
        "blockingForStructuralFigCompleteness": False,
        "visualApprovalRequired": counts["consumerReviewRequired"] > 0,
        "messages": reviewed,
    }


def _fig_completeness(
    uiir: dict[str, Any],
    asset_catalog: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    payloads: dict[str, Any],
    layout_conformance: dict[str, Any],
    export_conformance: dict[str, Any],
) -> dict[str, Any]:
    required_pages = ["00_Foundations", "10_Wireframe", "20_Visual", "30_States", "90_Export"]
    info = payloads.get("info", {}) if isinstance(payloads.get("info"), dict) else {}
    page_counts = info.get("pageCounts", {}) if isinstance(info.get("pageCounts"), dict) else {}
    expected_visual = sum(len(page["nodes"]) for page in uiir["pages"] if page["name"] == "20_Visual")
    expected_fallbacks = sum(
        1 for page in uiir["pages"] for node in page["nodes"] if node.get("textFallback")
    )
    checks = {
        "fiveCanonicalPages": info.get("pages") == len(required_pages) and all(page in page_counts for page in required_pages),
        "foundationsPopulated": page_counts.get("00_Foundations", 0) >= 2,
        "wireframeCoversUiir": page_counts.get("10_Wireframe", 0) >= expected_visual,
        "visualCoversUiir": page_counts.get("20_Visual", 0) >= expected_visual,
        "statesPopulated": page_counts.get("30_States", 0) >= 2,
        "exportComponentCount": page_counts.get("90_Export", 0) == len(asset_catalog),
        "assetsEmbedded": diagnostics.get("embeddedAssetImageCount") == len(asset_catalog),
        "textFallbacksEmbedded": diagnostics.get("embeddedTextFallbackCount") == expected_fallbacks,
        "layoutConforms": bool(layout_conformance.get("valid")),
        "exportConforms": bool(export_conformance.get("valid")),
        "noPlaceholderStatePage": not _contains_pending_note(payloads.get("states-tree")),
    }
    return {
        "structurallyComplete": all(checks.values()),
        "visualApproval": "consumer-review-required",
        "requiredPages": required_pages,
        "pageCounts": page_counts,
        "expected": {
            "visualUiirNodes": expected_visual,
            "assets": len(asset_catalog),
            "textFallbacks": expected_fallbacks,
        },
        "checks": checks,
    }


def doctor(explicit_repo: Path | None = None) -> dict[str, Any]:
    command, metadata = resolve_cli(explicit_repo)
    version = run_cli(command, ["--version"]).stdout.strip()
    formats = run_cli(command, ["formats", "--json"]).stdout.strip()
    report: dict[str, Any] = {**metadata, "command": command, "version": version, "formats": json.loads(formats)}
    if metadata.get("repo"):
        repo = Path(metadata["repo"])
        for key, args in (("commit", ["rev-parse", "HEAD"]), ("branch", ["rev-parse", "--abbrev-ref", "HEAD"]), ("status", ["status", "--short"])):
            completed = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
            report[key] = completed.stdout.strip() if completed.returncode == 0 else None
    return report


def build_fig(
    uiir: dict[str, Any],
    style_profile: dict[str, Any],
    output_root: Path,
    *,
    explicit_repo: Path | None = None,
    export_preview: bool = True,
) -> dict[str, Any]:
    command, metadata = resolve_cli(explicit_repo)
    design_dir = output_root / "Design"
    report_dir = output_root / "Reports" / "OpenPencil"
    preview_dir = output_root / "Previews"
    design_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    output_fig = design_dir / f"{uiir['id']}.fig"
    embedded_images: dict[str, str] = {}
    manifest_path = output_root / "asset-manifest.json"
    asset_catalog = load_data(manifest_path).get("assets", []) if manifest_path.is_file() else []
    for asset in asset_catalog:
        asset_path = output_root / asset["output"]
        if not asset_path.is_file():
            raise OpenPencilError(f"Manifest asset does not exist: {asset['output']}")
        embedded_images[asset["id"]] = base64.b64encode(asset_path.read_bytes()).decode("ascii")
    text_fallback_count = 0
    for page in uiir["pages"]:
        for node in page["nodes"]:
            asset = node.get("asset")
            if asset:
                asset_path = output_root / asset["path"]
                if not asset_path.is_file():
                    raise OpenPencilError(f"UIIR asset does not exist: {asset['path']}")
                embedded_images.setdefault(asset["id"], base64.b64encode(asset_path.read_bytes()).decode("ascii"))
            text_fallback = node.get("textFallback")
            if text_fallback:
                fallback_path = output_root / text_fallback["path"]
                if not fallback_path.is_file():
                    raise OpenPencilError(f"UIIR text fallback does not exist: {text_fallback['path']}")
                embedded_images[text_fallback["id"]] = base64.b64encode(fallback_path.read_bytes()).decode("ascii")
                text_fallback_count += 1
    source = render_openpencil_script(uiir, style_profile, embedded_images, asset_catalog)

    with tempfile.TemporaryDirectory(prefix="ui-rebuilder-openpencil-") as temp_raw:
        temp = Path(temp_raw)
        seed_html = temp / "seed.html"
        seed_fig = temp / "seed.fig"
        built_fig = temp / "built.fig"
        seed_html.write_text("<!doctype html><html><body><div></div></body></html>\n", encoding="utf-8")
        run_cli(command, ["import", str(seed_html), "-o", str(seed_fig), "--json"])
        run_cli(command, ["eval", str(seed_fig), "--stdin", "--output", str(built_fig), "--json"], stdin=source)
        shutil.copy2(built_fig, output_fig)

    diagnostics: dict[str, Any] = {
        "tool": metadata,
        "fig": str(output_fig.relative_to(output_root)),
        "embeddedImageCount": len(embedded_images),
        "embeddedAssetImageCount": len(asset_catalog),
        "embeddedTextFallbackCount": text_fallback_count,
        "exportComponentCount": len(asset_catalog),
    }
    commands: dict[str, tuple[list[str], bool]] = {
        "info": (["info", str(output_fig), "--json"], True),
        "foundations-tree": (["tree", str(output_fig), "--page", "00_Foundations", "--depth", "4", "--json"], True),
        "wireframe-tree": (["tree", str(output_fig), "--page", "10_Wireframe", "--depth", "8", "--json"], True),
        "tree": (["tree", str(output_fig), "--page", "20_Visual", "--depth", "8", "--json"], True),
        "states-tree": (["tree", str(output_fig), "--page", "30_States", "--depth", "4", "--json"], True),
        "export-tree": (["tree", str(output_fig), "--page", "90_Export", "--depth", "2", "--json"], True),
        "variables": (["variables", str(output_fig), "--json"], True),
        "overlaps": (["analyze", "overlaps", str(output_fig), "--page", "20_Visual", "--include-absolute", "--json"], True),
        "colors": (["analyze", "colors", str(output_fig), "--page", "20_Visual", "--json"], True),
        "typography": (["analyze", "typography", str(output_fig), "--page", "20_Visual", "--json"], True),
        "spacing": (["analyze", "spacing", str(output_fig), "--page", "20_Visual", "--json"], True),
        "clusters": (["analyze", "clusters", str(output_fig), "--json"], True),
        "lint": (["lint", str(output_fig), "--preset", "accessibility", "--json"], False),
    }
    payloads: dict[str, Any] = {}
    return_codes: dict[str, int] = {}
    for name, (args, strict) in commands.items():
        result = run_cli(command, args, check=strict)
        try:
            payload: Any = json.loads(result.stdout)
        except json.JSONDecodeError:
            payload = {"stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
        write_json(report_dir / f"{name}.json", payload)
        payloads[name] = payload
        return_codes[name] = result.returncode
        diagnostics[name] = str((report_dir / f"{name}.json").relative_to(output_root))

    lint_review = _lint_review(payloads["lint"], return_codes["lint"])
    lint_review_path = report_dir / "lint-review.json"
    write_json(lint_review_path, lint_review)
    diagnostics["lintReview"] = str(lint_review_path.relative_to(output_root))

    conformance = _layout_conformance(uiir, payloads["tree"])
    conformance_path = report_dir / "layout-conformance.json"
    write_json(conformance_path, conformance)
    diagnostics["layoutConformance"] = str(conformance_path.relative_to(output_root))
    if not conformance["valid"]:
        raise OpenPencilError(f"OpenPencil layout does not conform to UIIR: {conformance['mismatchCount']} mismatches")
    export_conformance = _export_conformance(asset_catalog, payloads["export-tree"])
    export_conformance_path = report_dir / "export-conformance.json"
    write_json(export_conformance_path, export_conformance)
    diagnostics["exportConformance"] = str(export_conformance_path.relative_to(output_root))
    if not export_conformance["valid"]:
        raise OpenPencilError(
            f"OpenPencil export components do not conform to the asset manifest: {export_conformance['mismatchCount']} mismatches"
        )

    completeness = _fig_completeness(
        uiir,
        asset_catalog,
        diagnostics,
        payloads,
        conformance,
        export_conformance,
    )
    completeness_path = report_dir / "fig-completeness.json"
    write_json(completeness_path, completeness)
    diagnostics["figCompleteness"] = str(completeness_path.relative_to(output_root))
    diagnostics["structurallyComplete"] = completeness["structurallyComplete"]
    if not completeness["structurallyComplete"]:
        failed = [name for name, valid in completeness["checks"].items() if not valid]
        raise OpenPencilError(f"OpenPencil .fig is structurally incomplete: {', '.join(failed)}")

    if export_preview:
        page_previews = {
            "00_Foundations": preview_dir / f"{uiir['id']}-foundations-openpencil.png",
            "10_Wireframe": preview_dir / f"{uiir['id']}-wireframe-openpencil.png",
            "20_Visual": preview_dir / f"{uiir['id']}-openpencil.png",
            "30_States": preview_dir / f"{uiir['id']}-states-openpencil.png",
            "90_Export": preview_dir / f"{uiir['id']}-assets-openpencil.png",
        }
        for page_name, preview_path in page_previews.items():
            run_cli(command, ["export", str(output_fig), "--page", page_name, "-f", "png", "-o", str(preview_path)])
        diagnostics["pagePreviews"] = {
            page: str(path.relative_to(output_root)) for page, path in page_previews.items()
        }
        diagnostics["preview"] = diagnostics["pagePreviews"]["20_Visual"]
        diagnostics["assetsPreview"] = diagnostics["pagePreviews"]["90_Export"]
    return diagnostics
