from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .adapters.openpencil import doctor
from .pipeline.package import build_package
from .validator import validate_package


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
    except Exception as exc:
        print(f"ui-rebuilder: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
