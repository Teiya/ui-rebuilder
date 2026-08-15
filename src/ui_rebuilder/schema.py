from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .util import REPO_ROOT, load_data


SCHEMAS = {
    "reconstruction-job": REPO_ROOT / "schemas" / "reconstruction-job.schema.json",
    "style-profile": REPO_ROOT / "schemas" / "style-profile.schema.json",
    "uiir": REPO_ROOT / "schemas" / "uiir.schema.json",
    "asset-manifest": REPO_ROOT / "schemas" / "asset-manifest.schema.json",
    "workspace": REPO_ROOT / "schemas" / "workspace.schema.json",
}


class SchemaValidationError(ValueError):
    pass


def validate_data(schema_name: str, data: Any, *, source: Path | None = None) -> None:
    schema = load_data(SCHEMAS[schema_name])
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.absolute_path))
    if not errors:
        return
    lines = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        lines.append(f"{location}: {error.message}")
    label = str(source) if source else schema_name
    raise SchemaValidationError(f"Schema validation failed for {label}:\n- " + "\n- ".join(lines))
