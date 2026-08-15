from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_data(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected an object in {path}")
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_relative(base: Path, raw: str) -> Path:
    candidate = Path(raw).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()


def stable_id(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-").lower()
    return value or "node"


def rgba_hex_to_parts(value: str) -> tuple[str, float]:
    raw = value.lstrip("#")
    if len(raw) == 6:
        return f"#{raw.upper()}", 1.0
    if len(raw) == 8:
        return f"#{raw[:6].upper()}", int(raw[6:], 16) / 255.0
    raise ValueError(f"Invalid color: {value}")

