from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify manually downloaded ComfyUI model files.")
    parser.add_argument("--comfyui-root", type=Path, default=ROOT / "third_party" / "comfyui")
    parser.add_argument("--profile", choices=["recovery", "generation", "all"], default="all")
    parser.add_argument("--hash", action="store_true", help="Hash large files in addition to checking their size.")
    args = parser.parse_args()

    manifest = json.loads((ROOT / "third_party" / "models.lock.json").read_text(encoding="utf-8"))
    results = []
    valid = True
    for model in manifest["models"]:
        if args.profile != "all" and args.profile not in model.get("profiles", []):
            continue
        path = args.comfyui_root.resolve() / model["file"]
        item = {"id": model["id"], "path": str(path), "source": model["source"], "exists": path.is_file()}
        if path.is_file():
            item["bytes"] = path.stat().st_size
            if model.get("bytes") is not None:
                item["sizeValid"] = item["bytes"] == model["bytes"]
            if args.hash and model.get("sha256"):
                item["sha256"] = sha256(path)
                item["hashValid"] = item["sha256"].lower() == model["sha256"].lower()
        item_valid = item["exists"] and item.get("sizeValid", True) and item.get("hashValid", True)
        item["valid"] = item_valid
        valid = valid and item_valid
        results.append(item)
    print(json.dumps({"valid": valid, "comfyuiRoot": str(args.comfyui_root.resolve()), "models": results}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
