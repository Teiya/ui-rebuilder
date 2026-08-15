from __future__ import annotations

from pathlib import Path
from typing import Any

from .schema import SchemaValidationError, validate_data
from .util import load_data, sha256_file


def validate_package(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    required = [
        "README.md",
        "uiir.json",
        "asset-manifest.json",
        "Source/reference.png",
        "Reports/build.json",
        "Reports/build-state.json",
    ]
    for relative in required:
        if not (root / relative).is_file():
            errors.append(f"Missing required file: {relative}")
    if errors:
        return {"valid": False, "root": str(root), "errors": errors, "warnings": warnings}

    build_state = load_data(root / "Reports" / "build-state.json")
    if build_state.get("status") != "complete":
        errors.append(f"Package build is not complete: {build_state.get('status', 'unknown')}")
        return {"valid": False, "root": str(root), "errors": errors, "warnings": warnings}

    try:
        uiir = load_data(root / "uiir.json")
        validate_data("uiir", uiir)
        manifest = load_data(root / "asset-manifest.json")
        validate_data("asset-manifest", manifest)
    except (ValueError, SchemaValidationError) as exc:
        errors.append(str(exc))
        return {"valid": False, "root": str(root), "errors": errors, "warnings": warnings}

    source = root / uiir["source"]["path"]
    if not source.is_file():
        errors.append(f"UIIR source does not exist: {uiir['source']['path']}")
    elif sha256_file(source) != uiir["source"]["sha256"]:
        errors.append(f"UIIR source hash mismatch: {uiir['source']['path']}")

    for asset in manifest["assets"]:
        path = root / asset["output"]
        if not path.is_file():
            errors.append(f"Asset does not exist: {asset['output']}")
        elif sha256_file(path) != asset["sha256"]:
            errors.append(f"Asset hash mismatch: {asset['output']}")
        if asset.get("reviewRequired"):
            warnings.append(f"Asset requires human review: {asset['id']}")

    ids = [node["id"] for page in uiir["pages"] for node in page["nodes"]]
    if len(ids) != len(set(ids)):
        errors.append("UIIR node ids are not unique")
    known = set(ids)
    nodes_by_name = {node["name"]: node for page in uiir["pages"] for node in page["nodes"]}
    for page in uiir["pages"]:
        for node in page["nodes"]:
            if node["parent"] is not None and node["parent"] not in known:
                errors.append(f"Unknown parent {node['parent']} for node {node['id']}")
    for asset in manifest["assets"]:
        target_names = asset.get("targetNodes") or ([asset["targetNode"]] if asset.get("targetNode") else [])
        for target_name in target_names:
            target = nodes_by_name.get(target_name)
            if target is None:
                errors.append(f"Asset targets an unknown UIIR node: {asset['id']} -> {target_name}")
            elif target.get("asset", {}).get("id") != asset["id"]:
                errors.append(f"Asset binding mismatch: {asset['id']} -> {target_name}")

    report = load_data(root / "Reports" / "build.json")
    if report.get("openpencil"):
        fig = root / report["openpencil"]["fig"]
        if not fig.is_file():
            errors.append(f"OpenPencil output does not exist: {report['openpencil']['fig']}")
        conformance_raw = report["openpencil"].get("layoutConformance")
        if conformance_raw:
            conformance_path = root / conformance_raw
            if not conformance_path.is_file():
                errors.append(f"OpenPencil conformance report does not exist: {conformance_raw}")
            elif not load_data(conformance_path).get("valid"):
                errors.append("OpenPencil layout does not conform to UIIR")
        else:
            warnings.append("OpenPencil layout conformance was not checked")
        export_conformance_raw = report["openpencil"].get("exportConformance")
        if export_conformance_raw:
            export_conformance_path = root / export_conformance_raw
            if not export_conformance_path.is_file():
                errors.append(f"OpenPencil export conformance report does not exist: {export_conformance_raw}")
            elif not load_data(export_conformance_path).get("valid"):
                errors.append("OpenPencil export components do not conform to the asset manifest")
        else:
            warnings.append("OpenPencil export component conformance was not checked")
        completeness_raw = report["openpencil"].get("figCompleteness")
        if completeness_raw:
            completeness_path = root / completeness_raw
            if not completeness_path.is_file():
                errors.append(f"OpenPencil completeness report does not exist: {completeness_raw}")
            elif not load_data(completeness_path).get("structurallyComplete"):
                errors.append("OpenPencil .fig is not structurally complete")
        else:
            errors.append("OpenPencil .fig completeness was not checked")
    else:
        warnings.append("OpenPencil output was not built")
    warnings.append("Schema validation does not replace visual approval")
    return {"valid": not errors, "root": str(root), "errors": errors, "warnings": warnings}
