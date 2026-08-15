from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .adapters.openpencil import doctor
from .pipeline.package import build_package
from .validator import validate_package
from .workspace import build_workspace, plan_workspace, validate_workspace


def _emit(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ui-rebuilder", description="Rebuild flattened UI references into auditable design packages")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_parser = sub.add_parser("doctor", help="Check optional tool adapters")
    doctor_parser.add_argument("--openpencil-repo", type=Path)

    build_parser = sub.add_parser("build", help="Build a reconstruction package")
    build_parser.add_argument("job", type=Path)
    build_parser.add_argument("--output", type=Path)
    build_parser.add_argument("--force", action="store_true")
    build_parser.add_argument("--skip-openpencil", action="store_true")
    build_parser.add_argument("--skip-openpencil-preview", action="store_true")
    build_parser.add_argument("--openpencil-repo", type=Path)

    validate_parser = sub.add_parser("validate", help="Validate a generated package")
    validate_parser.add_argument("package", type=Path)

    workspace_parser = sub.add_parser("workspace", help="Plan, build, or validate a multi-project workspace")
    workspace_commands = workspace_parser.add_subparsers(dest="workspace_command", required=True)

    def add_workspace_selection(command: argparse.ArgumentParser) -> None:
        command.add_argument("workspace", type=Path)
        command.add_argument("--project", action="append", help="Select a project id; repeat to select more than one")
        command.add_argument("--style", action="append", help="Select a style id; repeat to select more than one")
        command.add_argument("--task", action="append", help="Select a task id; repeat to select more than one")

    workspace_plan = workspace_commands.add_parser("plan", help="Resolve and preflight the build matrix without writing outputs")
    add_workspace_selection(workspace_plan)

    workspace_build = workspace_commands.add_parser("build", help="Build and validate the selected workspace matrix")
    add_workspace_selection(workspace_build)
    workspace_build.add_argument("--max-workers", type=int)
    workspace_build.add_argument("--force", action="store_true")
    workspace_build.add_argument("--skip-openpencil", action="store_true")
    workspace_build.add_argument("--skip-openpencil-preview", action="store_true")
    workspace_build.add_argument("--openpencil-repo", type=Path)

    workspace_validate = workspace_commands.add_parser("validate", help="Validate previously built workspace outputs")
    add_workspace_selection(workspace_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "doctor":
            _emit(doctor(args.openpencil_repo))
            return 0
        if args.command == "build":
            report = build_package(
                args.job,
                args.output,
                force=args.force,
                skip_openpencil=args.skip_openpencil,
                openpencil_repo=args.openpencil_repo,
                export_openpencil_preview=not args.skip_openpencil_preview,
            )
            _emit(report)
            return 0
        if args.command == "validate":
            report = validate_package(args.package)
            _emit(report)
            return 0 if report["valid"] else 1
        if args.command == "workspace":
            selection = {
                "projects": set(args.project) if args.project else None,
                "styles": set(args.style) if args.style else None,
                "tasks": set(args.task) if args.task else None,
            }
            if args.workspace_command == "plan":
                plan = plan_workspace(args.workspace, **selection)
                _emit(
                    {
                        "schemaVersion": 1,
                        "workspaceId": plan["workspace"]["id"],
                        "workspace": str(plan["workspacePath"]),
                        "outputRoot": str(plan["outputRoot"]),
                        "taskCount": len(plan["tasks"]),
                        "tasks": [
                            {
                                "projectId": item["projectId"],
                                "styleId": item["styleId"],
                                "taskId": item["taskId"],
                                "job": str(item["job"]),
                                "styleProfile": str(item["styleProfile"]),
                                "output": str(item["output"]),
                            }
                            for item in plan["tasks"]
                        ],
                    }
                )
                return 0
            if args.workspace_command == "build":
                report = build_workspace(
                    args.workspace,
                    max_workers=args.max_workers,
                    force=args.force,
                    skip_openpencil=args.skip_openpencil,
                    skip_openpencil_preview=args.skip_openpencil_preview,
                    openpencil_repo=args.openpencil_repo,
                    **selection,
                )
                _emit(report)
                return 0 if report["valid"] else 1
            if args.workspace_command == "validate":
                report = validate_workspace(args.workspace, **selection)
                _emit(report)
                return 0 if report["valid"] else 1
    except Exception as exc:
        print(f"ui-rebuilder: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
