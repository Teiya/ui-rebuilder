from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


COLORS = {
    "frame": (56, 116, 143, 210),
    "component": (47, 142, 104, 220),
    "instance": (42, 160, 118, 180),
    "rectangle": (181, 126, 42, 210),
    "ellipse": (170, 66, 106, 220),
    "text": (100, 70, 180, 220),
    "image": (204, 72, 52, 220),
}


def build_overlay(reference: Path, nodes: list[dict[str, Any]], output: Path, target_size: tuple[int, int]) -> None:
    image = Image.open(reference).convert("RGBA").resize(target_size, Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image, "RGBA")
    font = ImageFont.load_default()
    for node in nodes:
        if node.get("parent") is None:
            continue
        x, y, width, height = node.get("absoluteBounds", node["bounds"])
        if width < 4 or height < 4:
            continue
        color = COLORS.get(node["type"], (80, 80, 80, 190))
        draw.rectangle((x, y, x + width, y + height), outline=color, width=1)
        if width >= 54 and height >= 18:
            label = node["id"][:32]
            box = draw.textbbox((0, 0), label, font=font)
            label_width = min(width, box[2] - box[0] + 6)
            draw.rectangle((x, y, x + label_width, y + 13), fill=(255, 255, 255, 190))
            draw.text((x + 3, y + 2), label, fill=color, font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output)

