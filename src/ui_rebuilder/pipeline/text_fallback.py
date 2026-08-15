from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from ..util import resolve_relative, sha256_file


def _color(value: str) -> tuple[int, int, int, int]:
    raw = value.lstrip("#")
    if len(raw) == 6:
        raw += "FF"
    if len(raw) != 8:
        raise ValueError(f"Invalid text color: {value}")
    return tuple(int(raw[index:index + 2], 16) for index in range(0, 8, 2))  # type: ignore[return-value]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> str:
    if not text or width <= 1:
        return text
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        tokens = re.findall(r"\S+\s*|\s+", paragraph) if " " in paragraph else list(paragraph)
        for token in tokens:
            candidate = current + token
            if current and draw.textlength(candidate, font=font) > width:
                lines.append(current.rstrip())
                current = token.lstrip()
            else:
                current = candidate
        lines.append(current.rstrip())
    return "\n".join(lines)


def _render_text(text: str, style: dict[str, Any], size: tuple[int, int], font_path: Path) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font_size = max(1, int(round(float(style.get("fontSize", 12)))))
    font = ImageFont.truetype(str(font_path), font_size)
    wrapped = _wrap(draw, text, font, max(1, width - 2))
    spacing = max(1, round(font_size * 0.18))
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    horizontal = str(style.get("textAlignHorizontal", "LEFT")).upper()
    vertical = str(style.get("textAlignVertical", "CENTER")).upper()
    x = 1 if horizontal == "LEFT" else width - text_width - 1 if horizontal == "RIGHT" else (width - text_width) / 2
    y = 0 if vertical == "TOP" else height - text_height if vertical == "BOTTOM" else (height - text_height) / 2
    draw.multiline_text(
        (x, y - bbox[1]),
        wrapped,
        font=font,
        fill=_color(style.get("textColor", "#333333")),
        spacing=spacing,
        align=horizontal.lower() if horizontal in {"LEFT", "CENTER", "RIGHT"} else "left",
    )
    return image


def build_text_fallbacks(
    job: dict[str, Any], job_dir: Path, uiir: dict[str, Any], output_root: Path
) -> dict[str, Any]:
    config = job.get("textFallback")
    if not config or config.get("enabled", True) is False:
        return {"enabled": False, "count": 0}
    font_path = resolve_relative(job_dir, config["fontPath"])
    if not font_path.is_file():
        raise FileNotFoundError(f"Text fallback font not found: {font_path}")
    output_dir = output_root / "Design" / "TextFallbacks"
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for page in uiir["pages"]:
        for node in page["nodes"]:
            if node["type"] != "text" or node.get("visible", True) is False:
                continue
            width = max(1, int(round(node["bounds"][2])))
            height = max(1, int(round(node["bounds"][3])))
            output = output_dir / f"{node['id']}.png"
            _render_text(node.get("text", ""), node.get("style", {}), (width, height), font_path).save(output)
            node["textFallback"] = {
                "id": f"text-{node['id']}",
                "path": output.relative_to(output_root).as_posix(),
                "fontFamily": config.get("fontFamily", font_path.stem),
                "fontSha256": sha256_file(font_path),
                "hideEditableTextInPreview": config.get("hideEditableTextInPreview", True),
            }
            count += 1
    return {
        "enabled": True,
        "count": count,
        "fontFamily": config.get("fontFamily", font_path.stem),
        "fontSha256": sha256_file(font_path),
    }
