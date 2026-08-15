from __future__ import annotations

import math
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from ..util import resolve_relative, sha256_file


def _crop_checked(image: Image.Image, box: list[int], asset_id: str) -> Image.Image:
    x, y, width, height = box
    if width <= 0 or height <= 0:
        raise ValueError(f"Asset {asset_id} has a non-positive sourceBox")
    if x < 0 or y < 0 or x + width > image.width or y + height > image.height:
        raise ValueError(f"Asset {asset_id} sourceBox exceeds its source image")
    return image.crop((x, y, x + width, y + height))


def _trim_transparent(image: Image.Image, asset_id: str) -> Image.Image:
    alpha = image.getchannel("A")
    box = alpha.getbbox()
    if box is None:
        raise ValueError(f"Asset {asset_id} is fully transparent")
    return image.crop(box)


def _uniform_contain(image: Image.Image, target: tuple[int, int]) -> Image.Image:
    output = Image.new("RGBA", target, (0, 0, 0, 0))
    contained = image.copy()
    contained.thumbnail(target, Image.Resampling.LANCZOS)
    x = (target[0] - contained.width) // 2
    y = (target[1] - contained.height) // 2
    output.alpha_composite(contained, (x, y))
    return output


def _nine_slice(image: Image.Image, target: tuple[int, int], border: list[int], asset_id: str) -> Image.Image:
    left, top, right, bottom = border
    if min(border) < 0 or left + right >= image.width or top + bottom >= image.height:
        raise ValueError(f"Asset {asset_id} has invalid source nine-slice borders")
    if left + right > target[0] or top + bottom > target[1]:
        raise ValueError(f"Asset {asset_id} target is smaller than its nine-slice borders")
    source_x = [0, left, image.width - right, image.width]
    source_y = [0, top, image.height - bottom, image.height]
    target_x = [0, left, target[0] - right, target[0]]
    target_y = [0, top, target[1] - bottom, target[1]]
    output = Image.new("RGBA", target, (0, 0, 0, 0))
    for row in range(3):
        for column in range(3):
            crop = image.crop((source_x[column], source_y[row], source_x[column + 1], source_y[row + 1]))
            size = (target_x[column + 1] - target_x[column], target_y[row + 1] - target_y[row])
            if crop.size != size:
                crop = crop.resize(size, Image.Resampling.LANCZOS)
            output.alpha_composite(crop, (target_x[column], target_y[row]))
    return output


def _tile(image: Image.Image, target: tuple[int, int]) -> Image.Image:
    output = Image.new("RGBA", target, (0, 0, 0, 0))
    for y in range(0, target[1], image.height):
        for x in range(0, target[0], image.width):
            output.alpha_composite(image, (x, y))
    return output


def _process_size(image: Image.Image, spec: dict[str, Any]) -> Image.Image:
    target_raw = spec.get("targetSize")
    if not target_raw:
        return image
    target = (int(target_raw[0]), int(target_raw[1]))
    scaling = spec.get("scaling", "none")
    if scaling == "none":
        if image.size != target:
            raise ValueError(f"Asset {spec['id']} uses scaling=none but is {image.size}, expected {target}")
        return image
    if scaling == "uniform":
        return _uniform_contain(image, target)
    if scaling == "nine-slice":
        border = spec.get("borderLTRB")
        if not border:
            raise ValueError(f"Asset {spec['id']} requires borderLTRB for nine-slice")
        return _nine_slice(image, target, border, spec["id"])
    if scaling == "tile":
        return _tile(image, target)
    raise ValueError(f"Unsupported scaling mode for {spec['id']}: {scaling}")


def build_assets(
    job: dict[str, Any],
    job_dir: Path,
    reference: Path,
    output_root: Path,
    resolution: list[int],
) -> dict[str, Any]:
    assets_dir = output_root / "Assets"
    source_assets_dir = output_root / "Source" / "Assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    source_assets_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in job.get("assets", []):
        asset_id = spec["id"]
        if asset_id in seen:
            raise ValueError(f"Duplicate asset id: {asset_id}")
        seen.add(asset_id)
        declared = spec.get("sourcePath")
        source = resolve_relative(job_dir, declared) if declared else reference
        if not source.is_file():
            raise FileNotFoundError(f"Asset source not found for {asset_id}: {source}")

        if declared:
            snapshot = source_assets_dir / f"{asset_id}{source.suffix.lower() or '.png'}"
            shutil.copy2(source, snapshot)
        else:
            snapshot = reference
        with Image.open(snapshot) as opened:
            image = opened.convert("RGBA")
        if spec.get("sourceBox"):
            image = _crop_checked(image, spec["sourceBox"], asset_id)
        if spec.get("trimTransparent"):
            image = _trim_transparent(image, asset_id)
        if spec.get("scaling") == "nine-slice" and not spec.get("borderLTRB"):
            raise ValueError(f"Asset {asset_id} requires borderLTRB for nine-slice")
        image = _process_size(image, spec)

        output = assets_dir / f"{asset_id}.png"
        image.save(output)
        alpha_min, alpha_max = image.getchannel("A").getextrema()
        if alpha_max == 0:
            raise ValueError(f"Asset {asset_id} output is fully transparent")
        has_transparency = alpha_min < 255
        if spec.get("alphaRequired") and not has_transparency:
            raise ValueError(f"Asset {asset_id} requires transparency but its output is fully opaque")
        source_relative = snapshot.relative_to(output_root).as_posix()
        record: dict[str, Any] = {
            "id": asset_id,
            "role": spec.get("role", "visual-asset"),
            "method": spec["method"],
            "source": {
                "path": source_relative,
                "sha256": sha256_file(snapshot),
                "declaredPath": declared or job["reference"]["path"],
            },
            "output": output.relative_to(output_root).as_posix(),
            "sha256": sha256_file(output),
            "scaling": spec.get("scaling", "none"),
            "pixelSize": [image.width, image.height],
            "alpha": {"min": alpha_min, "max": alpha_max, "hasTransparency": has_transparency},
            "alphaRequired": bool(spec.get("alphaRequired", False)),
            "reviewRequired": spec.get("method") in {"repaired", "generated"},
        }
        for key in ("sourceBox", "targetNode", "targetNodes", "targetSize", "borderLTRB", "opacity", "backgroundDependency"):
            if key in spec:
                record[key] = spec[key]
        records.append(record)
    return {
        "schemaVersion": 1,
        "jobId": job["id"],
        "referenceResolution": resolution,
        "assets": records,
    }


def build_asset_contact_sheet(manifest: dict[str, Any], output_root: Path) -> Path | None:
    assets = manifest.get("assets", [])
    if not assets:
        return None
    tile_width, tile_height = 240, 190
    columns = min(4, max(1, len(assets)))
    rows = math.ceil(len(assets) / columns)
    sheet = Image.new("RGB", (columns * tile_width, rows * tile_height), (224, 224, 218))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, asset in enumerate(assets):
        left = (index % columns) * tile_width
        top = (index // columns) * tile_height
        for y in range(top + 8, top + 152, 12):
            for x in range(left + 8, left + 232, 12):
                shade = 238 if ((x - left) // 12 + (y - top) // 12) % 2 == 0 else 202
                draw.rectangle((x, y, min(x + 11, left + 231), min(y + 11, top + 151)), fill=(shade, shade, shade))
        with Image.open(output_root / asset["output"]) as opened:
            preview = opened.convert("RGBA")
        preview.thumbnail((216, 136), Image.Resampling.LANCZOS)
        px = left + (tile_width - preview.width) // 2
        py = top + 8 + (144 - preview.height) // 2
        sheet.paste(preview, (px, py), preview)
        draw.text((left + 8, top + 158), asset["id"][:36], fill=(38, 38, 34), font=font)
        draw.text((left + 8, top + 173), f"{asset['method']} · {asset['scaling']} · {asset['pixelSize'][0]}×{asset['pixelSize'][1]}", fill=(86, 84, 76), font=font)
    output = output_root / "Previews" / "assets-checkerboard.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return output
