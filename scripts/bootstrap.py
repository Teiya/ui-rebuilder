from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
THIRD_PARTY = ROOT / "third_party"
LOCK_PATH = THIRD_PARTY / "tools.lock.json"


def run(args: list[str], *, cwd: Path | None = None, dry_run: bool = False) -> None:
    location = f" (cwd={cwd})" if cwd else ""
    print(f"+ {' '.join(args)}{location}")
    if not dry_run:
        subprocess.run(args, cwd=cwd, check=True)


def git_output(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()


def selected(item: dict[str, Any], profiles: set[str]) -> bool:
    return bool(profiles.intersection(item.get("profiles", [])))


def safe_destination(relative: str, base: Path = ROOT) -> Path:
    destination = (base / relative).resolve()
    allowed = THIRD_PARTY.resolve()
    if destination != allowed and allowed not in destination.parents:
        raise RuntimeError(f"Third-party destination escapes third_party/: {destination}")
    return destination


def ensure_locked_repo(
    item: dict[str, Any],
    destination: Path,
    *,
    dry_run: bool,
    base: Path = ROOT,
) -> None:
    revision = item["revision"]
    url = item["url"]
    empty_slot = (
        destination.exists()
        and not (destination / ".git").exists()
        and not any(path.is_file() for path in destination.rglob("*"))
    )
    if not destination.exists() or empty_slot:
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "init", str(destination)], dry_run=dry_run)
        run(["git", "-C", str(destination), "remote", "add", "origin", url], dry_run=dry_run)
        run(["git", "-C", str(destination), "fetch", "--depth", "1", "origin", revision], dry_run=dry_run)
        run(["git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"], dry_run=dry_run)
    elif not (destination / ".git").exists():
        raise RuntimeError(f"Existing tool slot is not a Git repository: {destination}")
    elif not dry_run:
        head = git_output(["rev-parse", "HEAD"], destination)
        if head != revision:
            dirty = git_output(["status", "--porcelain"], destination)
            if dirty:
                raise RuntimeError(f"Refusing to change a dirty third-party checkout: {destination}")
            run(["git", "fetch", "--depth", "1", "origin", revision], cwd=destination)
            run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=destination)
    if not dry_run and git_output(["rev-parse", "HEAD"], destination) != revision:
        raise RuntimeError(f"Checked-out revision does not match the lock for {item['id']}")
    for relative_patch in item.get("patches", []):
        patch = (base / relative_patch).resolve()
        if not patch.is_file():
            raise FileNotFoundError(f"Pinned patch does not exist: {patch}")
        if dry_run:
            print(f"+ git apply {patch} (cwd={destination})")
            continue
        applicable = subprocess.run(
            ["git", "apply", "--check", str(patch)], cwd=destination, capture_output=True
        ).returncode == 0
        if applicable:
            run(["git", "apply", str(patch)], cwd=destination)
            continue
        already_applied = subprocess.run(
            ["git", "apply", "--reverse", "--check", str(patch)], cwd=destination, capture_output=True
        ).returncode == 0
        if not already_applied:
            raise RuntimeError(f"Patch is neither applicable nor already applied: {patch}")


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def install_requirements(python: Path, path: Path, *, dry_run: bool) -> None:
    if path.is_file():
        run([str(python), "-m", "pip", "install", "-r", str(path)], dry_run=dry_run)


def project_bun_path() -> Path:
    return THIRD_PARTY / ".runtimes" / "bun" / ("bun.exe" if os.name == "nt" else "bun")


def resolve_system_bun() -> Path | None:
    direct = shutil.which("bun.exe") or shutil.which("bun")
    if direct:
        path = Path(direct).resolve()
        if path.suffix.lower() == ".exe" or os.name != "nt":
            return path
    shim = shutil.which("bun.cmd") or direct
    if shim:
        candidate = Path(shim).resolve().parent / "node_modules" / "bun" / "bin" / "bun.exe"
        if candidate.is_file():
            return candidate
    return None


def ensure_project_bun(*, dry_run: bool) -> str:
    local = project_bun_path()
    if local.is_file():
        return str(local)
    source = resolve_system_bun()
    if source is None:
        if dry_run:
            return "bun"
        raise RuntimeError("Bun 1.3.5 is required for OpenPencil: https://bun.sh/")
    print(f"+ copy {source} {local}")
    if not dry_run:
        local.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, local)
    return str(local)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install pinned UI Rebuilder tool profiles into third_party/.")
    parser.add_argument(
        "--profile",
        action="append",
        choices=["fig", "recovery", "generation", "operator", "evaluation", "all"],
        help="Repeat to combine profiles. Default: fig.",
    )
    parser.add_argument("--install-comfy-python", action="store_true", help="Create a ComfyUI venv and install requirements.")
    parser.add_argument("--torch-index-url", help="Optional PyTorch wheel index selected by the user for their accelerator.")
    parser.add_argument("--skip-core-install", action="store_true")
    parser.add_argument("--skip-openpencil-build", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    profiles = set(args.profile or ["fig"])
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    if not shutil.which("git") and not args.dry_run:
        raise RuntimeError("Git is required: https://git-scm.com/downloads")

    if not args.skip_core_install:
        run([sys.executable, "-m", "pip", "install", "-e", str(ROOT)], dry_run=args.dry_run)

    comfy_root: Path | None = None
    selected_nodes: list[dict[str, Any]] = []
    for tool in lock["tools"]:
        if not selected(tool, profiles):
            continue
        destination = safe_destination(tool["path"])
        ensure_locked_repo(tool, destination, dry_run=args.dry_run)
        if tool["id"] == "openpencil" and not args.skip_openpencil_build:
            bun_command = ensure_project_bun(dry_run=args.dry_run)
            for command in tool.get("build", []):
                resolved = [bun_command if part == "bun" else part for part in command]
                run(resolved, cwd=destination, dry_run=args.dry_run)
        if tool["id"] == "comfyui":
            comfy_root = destination

    if comfy_root:
        for node in lock.get("comfyuiCustomNodes", []):
            if not selected(node, profiles):
                continue
            destination = safe_destination(node["path"], comfy_root)
            ensure_locked_repo(node, destination, dry_run=args.dry_run, base=comfy_root)
            selected_nodes.append(node)

    if comfy_root and args.install_comfy_python:
        venv = THIRD_PARTY / ".venvs" / "comfyui"
        python = venv_python(venv)
        if not python.is_file():
            run([sys.executable, "-m", "venv", str(venv)], dry_run=args.dry_run)
        run([str(python), "-m", "pip", "install", "--upgrade", "pip"], dry_run=args.dry_run)
        if args.torch_index_url:
            run(
                [str(python), "-m", "pip", "install", "torch", "torchvision", "torchaudio", "--index-url", args.torch_index_url],
                dry_run=args.dry_run,
            )
        comfy_tool = next(tool for tool in lock["tools"] if tool["id"] == "comfyui")
        install_requirements(python, comfy_root / comfy_tool["pythonRequirements"], dry_run=args.dry_run)
        for node in selected_nodes:
            install_requirements(python, comfy_root / node["path"] / "requirements.txt", dry_run=args.dry_run)

    print("Tool source installation complete.")
    if comfy_root:
        print("Models are not redistributed. Download them from third_party/models.lock.json, then run scripts/verify_models.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
