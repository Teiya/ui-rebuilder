from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the project-local ComfyUI service.")
    parser.add_argument("--comfyui-root", type=Path, default=ROOT / "third_party" / "comfyui")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8190)
    args, extra = parser.parse_known_args()

    comfy_root = args.comfyui_root.resolve()
    main_py = comfy_root / "main.py"
    if not main_py.is_file():
        raise SystemExit("ComfyUI is missing. Run: python scripts/bootstrap.py --profile recovery --profile generation")
    candidates = [
        ROOT / "third_party" / ".venvs" / "comfyui" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"),
        ROOT / "third_party" / ".runtimes" / "comfyui-python" / ("python.exe" if sys.platform == "win32" else "bin/python"),
        Path(sys.executable),
    ]
    python = next((candidate for candidate in candidates if candidate.is_file()), None)
    if python is None:
        raise SystemExit("No Python runtime was found for ComfyUI.")
    command = [str(python), str(main_py), "--listen", args.host, "--port", str(args.port), "--disable-auto-launch", *extra]
    return subprocess.run(command, cwd=comfy_root).returncode


if __name__ == "__main__":
    raise SystemExit(main())
