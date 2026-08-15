from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pipeline.package import build_package
from .schema import validate_data
from .util import load_data, resolve_relative, write_json
from .validator import validate_package


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_unique(values: list[str], label: str) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ValueError(f"Duplicate {label}: {', '.join(duplicates)}")


def _safe_output(output_root: Path, template: str, context: dict[str, str]) -> Path:
    try:
        rendered = template.format(**context)
    except KeyError as exc:
        raise ValueError(f"Unknown output template field: {exc.args[0]}") from exc
    relative = Path(rendered)
    if relative.is_absolute():
        raise ValueError(f"Workspace task output must be relative to outputRoot: {rendered}")
    output = (output_root / relative).resolve()
    if output == output_root or output_root not in output.parents:
        raise ValueError(f"Workspace task output escapes outputRoot: {rendered}")
    return output


def plan_workspace(
    workspace_path: Path,
    *,
    projects: set[str] | None = None,
    styles: set[str] | None = None,
    tasks: set[str] | None = None,
) -> dict[str, Any]:
    workspace_path = workspace_path.resolve()
    workspace_dir = workspace_path.parent
    workspace = load_data(workspace_path)
    validate_data("workspace", workspace, source=workspace_path)
    output_root = resolve_relative(workspace_dir, workspace["outputRoot"])
    project_specs = workspace["projects"]
    _require_unique([item["id"] for item in project_specs], "project id")

    planned: list[dict[str, Any]] = []
    for project in project_specs:
        project_id = project["id"]
        if projects and project_id not in projects:
            continue
        project_root = resolve_relative(workspace_dir, project["root"])
        if not project_root.is_dir():
            raise FileNotFoundError(f"Project root does not exist: {project_root}")
        style_specs = project["styles"]
        _require_unique([item["id"] for item in style_specs], f"style id in project {project_id}")
        style_map: dict[str, Path] = {}
        for style_spec in style_specs:
            style_id = style_spec["id"]
            profile_path = resolve_relative(project_root, style_spec["profile"])
            if not profile_path.is_file():
                raise FileNotFoundError(f"Style profile does not exist: {profile_path}")
            profile = load_data(profile_path)
            validate_data("style-profile", profile, source=profile_path)
            if profile["id"] != style_id:
                raise ValueError(
                    f"Workspace style id must match style profile id: {project_id}/{style_id} != {profile['id']}"
                )
            style_map[style_id] = profile_path

        task_specs = project["tasks"]
        _require_unique([item["id"] for item in task_specs], f"task id in project {project_id}")
        for task in task_specs:
            if task.get("enabled", True) is False:
                continue
            task_id = task["id"]
            if tasks and task_id not in tasks:
                continue
            job_path = resolve_relative(project_root, task["job"])
            if not job_path.is_file():
                raise FileNotFoundError(f"Reconstruction job does not exist: {job_path}")
            for style_id in task["styles"]:
                if style_id not in style_map:
                    raise ValueError(f"Task references an unknown style: {project_id}/{task_id} -> {style_id}")
                if styles and style_id not in styles:
                    continue
                context = {
                    "workspaceId": workspace["id"],
                    "projectId": project_id,
                    "styleId": style_id,
                    "taskId": task_id,
                }
                template_context = {"project": project_id, "style": style_id, "task": task_id}
                output = _safe_output(
                    output_root,
                    task.get("output", "{project}/{style}/{task}"),
                    template_context,
                )
                planned.append(
                    {
                        "index": len(planned),
                        "projectId": project_id,
                        "styleId": style_id,
                        "taskId": task_id,
                        "job": job_path,
                        "styleProfile": style_map[style_id],
                        "output": output,
                        "context": context,
                    }
                )

    if not planned:
        raise ValueError("Workspace selection matched no enabled tasks")
    output_keys = [str(item["output"]).casefold() for item in planned]
    _require_unique(output_keys, "workspace output path")
    return {
        "workspace": workspace,
        "workspacePath": workspace_path,
        "outputRoot": output_root,
        "tasks": planned,
    }


def _build_one(
    item: dict[str, Any],
    *,
    force: bool,
    skip_openpencil: bool,
    openpencil_repo: Path | None,
    export_openpencil_preview: bool,
) -> dict[str, Any]:
    base = {
        "index": item["index"],
        "projectId": item["projectId"],
        "styleId": item["styleId"],
        "taskId": item["taskId"],
        "job": str(item["job"]),
        "styleProfile": str(item["styleProfile"]),
        "output": str(item["output"]),
    }
    try:
        build = build_package(
            item["job"],
            item["output"],
            style_override=item["styleProfile"],
            build_context=item["context"],
            force=force,
            skip_openpencil=skip_openpencil,
            openpencil_repo=openpencil_repo,
            export_openpencil_preview=export_openpencil_preview,
        )
        validation = validate_package(item["output"])
        return {
            **base,
            "status": "complete" if validation["valid"] else "validation-failed",
            "valid": validation["valid"],
            "buildStatus": build["status"],
            "validation": validation,
        }
    except Exception as exc:
        return {**base, "status": "failed", "valid": False, "error": str(exc)}


def build_workspace(
    workspace_path: Path,
    *,
    max_workers: int | None = None,
    force: bool = False,
    skip_openpencil: bool = False,
    skip_openpencil_preview: bool = False,
    openpencil_repo: Path | None = None,
    projects: set[str] | None = None,
    styles: set[str] | None = None,
    tasks: set[str] | None = None,
) -> dict[str, Any]:
    plan = plan_workspace(workspace_path, projects=projects, styles=styles, tasks=tasks)
    workspace = plan["workspace"]
    defaults = workspace.get("defaults", {})
    workers = max_workers if max_workers is not None else workspace.get("maxWorkers", 1)
    if workers < 1 or workers > 32:
        raise ValueError("maxWorkers must be between 1 and 32")
    effective_skip_openpencil = skip_openpencil or bool(defaults.get("skipOpenPencil", False))
    export_preview = not skip_openpencil_preview and bool(defaults.get("exportOpenPencilPreview", True))
    output_root: Path = plan["outputRoot"]
    output_root.mkdir(parents=True, exist_ok=True)
    started = _utc_now()

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ui-rebuilder") as pool:
        futures = {
            pool.submit(
                _build_one,
                item,
                force=force,
                skip_openpencil=effective_skip_openpencil,
                openpencil_repo=openpencil_repo,
                export_openpencil_preview=export_preview,
            ): item
            for item in plan["tasks"]
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item["index"])
    for result in results:
        result.pop("index", None)
    succeeded = sum(1 for item in results if item["valid"])
    report = {
        "schemaVersion": 1,
        "workspaceId": workspace["id"],
        "workspace": str(plan["workspacePath"]),
        "outputRoot": str(output_root),
        "startedAtUtc": started,
        "completedAtUtc": _utc_now(),
        "maxWorkers": workers,
        "taskCount": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "valid": succeeded == len(results),
        "status": "complete" if succeeded == len(results) else "partial-failure",
        "results": results,
    }
    write_json(output_root / "workspace-build.json", report)
    return report


def validate_workspace(
    workspace_path: Path,
    *,
    projects: set[str] | None = None,
    styles: set[str] | None = None,
    tasks: set[str] | None = None,
) -> dict[str, Any]:
    plan = plan_workspace(workspace_path, projects=projects, styles=styles, tasks=tasks)
    results: list[dict[str, Any]] = []
    for item in plan["tasks"]:
        validation = validate_package(item["output"])
        results.append(
            {
                "projectId": item["projectId"],
                "styleId": item["styleId"],
                "taskId": item["taskId"],
                "output": str(item["output"]),
                "valid": validation["valid"],
                "validation": validation,
            }
        )
    succeeded = sum(1 for item in results if item["valid"])
    report = {
        "schemaVersion": 1,
        "workspaceId": plan["workspace"]["id"],
        "workspace": str(plan["workspacePath"]),
        "outputRoot": str(plan["outputRoot"]),
        "validatedAtUtc": _utc_now(),
        "taskCount": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "valid": succeeded == len(results),
        "results": results,
    }
    plan["outputRoot"].mkdir(parents=True, exist_ok=True)
    write_json(plan["outputRoot"] / "workspace-validation.json", report)
    return report
