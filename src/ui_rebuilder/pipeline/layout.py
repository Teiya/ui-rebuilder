from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..util import load_data, stable_id


TYPE_MAP = {
    "FRAME": "frame",
    "COMPONENT": "component",
    "INSTANCE": "instance",
    "RECTANGLE": "rectangle",
    "ELLIPSE": "ellipse",
    "TEXT": "text",
}


def _color(profile: dict[str, Any], *keys: str, fallback: str) -> str:
    colors = profile.get("tokens", {}).get("colors", {})
    for key in keys:
        if key in colors:
            return colors[key]
    return fallback


def style_for(name: str, node_type: str, profile: dict[str, Any], *, is_root: bool = False) -> dict[str, Any]:
    lower = name.lower()
    paper = _color(profile, "surface.paper", "paper", fallback="#F5F0E3")
    subtle = _color(profile, "surface.subtle", "paperSubtle", fallback="#ECE6D8")
    ink = _color(profile, "text.primary", "ink", fallback="#34342C")
    muted = _color(profile, "text.muted", "muted", fallback="#777468")
    gold = _color(profile, "border.ornament", "gold", fallback="#A7803D")
    action = _color(profile, "action.primary", "teal", fallback="#3D6E66")
    white = _color(profile, "text.onAction", "white", fallback="#FFFDF5")
    typography = profile.get("tokens", {}).get("typography", {})
    family = typography.get("primary", {}).get("family", "Inter") if isinstance(typography.get("primary"), dict) else "Inter"

    style: dict[str, Any] = {"opacity": 1.0}
    if node_type in {"frame", "component", "instance"}:
        style["fill"] = paper if is_root else None
    elif node_type == "rectangle":
        style["fill"] = subtle
    elif node_type == "ellipse":
        style.update({"fill": None, "stroke": gold, "strokeWidth": 1.5})
    elif node_type == "text":
        style.update({"textColor": ink, "fontFamily": family, "fontSize": 12})

    if any(token in lower for token in ("button", "chip")):
        style.update({"fill": action, "stroke": gold, "strokeWidth": 1.0, "cornerRadius": 6})
        if node_type == "text":
            style["textColor"] = white
    elif "track" in lower:
        style.update({"fill": muted, "opacity": 0.55, "cornerRadius": 2})
    elif any(token in lower for token in ("panel", "result", "cost", "yield")) and node_type != "text":
        style.update({"fill": subtle, "stroke": gold, "strokeWidth": 1.0, "cornerRadius": 5, "opacity": 0.72})
    elif "locked" in lower:
        style["opacity"] = 0.52
    return style


def _unique_ids(names: list[str]) -> dict[str, str]:
    counts: Counter[str] = Counter()
    result: dict[str, str] = {}
    for name in names:
        base = stable_id(name)
        counts[base] += 1
        result[name] = base if counts[base] == 1 else f"{base}-{counts[base]}"
    return result


def from_layout_authority(
    path: Path,
    profile: dict[str, Any],
    *,
    screen_node: str | None = None,
    text_overrides: dict[str, str] | None = None,
) -> tuple[list[int], list[dict[str, Any]]]:
    data = load_data(path)
    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, dict) or not raw_nodes:
        raise ValueError(f"layout-authority nodes are missing: {path}")
    root_name = screen_node or data.get("screen")
    if not isinstance(root_name, str) or root_name not in raw_nodes:
        raise ValueError(f"Screen node is not present in layout authority: {root_name}")

    included = {root_name}
    changed = True
    while changed:
        changed = False
        for name, record in raw_nodes.items():
            if isinstance(record, dict) and record.get("parent") in included and name not in included:
                included.add(name)
                changed = True

    def depth(name: str) -> int:
        value = 0
        current = name
        visited: set[str] = set()
        while current in raw_nodes and current not in visited:
            visited.add(current)
            parent = raw_nodes[current].get("parent")
            if parent not in included:
                break
            value += 1
            current = parent
        return value

    ordered_names = sorted(included, key=lambda name: (depth(name), list(raw_nodes).index(name)))
    ids = _unique_ids(ordered_names)
    text_overrides = text_overrides or {}
    nodes: list[dict[str, Any]] = []
    for name in ordered_names:
        record = raw_nodes[name]
        absolute = [float(value) for value in record["bounds"]]
        parent_name = record.get("parent") if record.get("parent") in included else None
        if parent_name:
            parent_bounds = raw_nodes[parent_name]["bounds"]
            bounds = [absolute[0] - float(parent_bounds[0]), absolute[1] - float(parent_bounds[1]), absolute[2], absolute[3]]
        else:
            bounds = [0.0, 0.0, absolute[2], absolute[3]]
        node_type = TYPE_MAP.get(str(record.get("type", "FRAME")).upper(), "frame")
        node: dict[str, Any] = {
            "id": ids[name],
            "name": name,
            "type": node_type,
            "parent": ids[parent_name] if parent_name else None,
            "bounds": bounds,
            "absoluteBounds": absolute,
            "role": "screen" if name == root_name else "semantic-node",
            "dynamic": node_type == "text",
            "layout": {
                "mode": record.get("layoutMode") or "NONE",
                "positioning": record.get("layoutPositioning") or "AUTO"
            },
            "style": style_for(name, node_type, profile, is_root=name == root_name),
            "asset": None,
            "provenance": {
                "method": "layout-authority",
                "confidence": 1.0,
                "reviewRequired": False,
                "source": str(path)
            }
        }
        if node_type == "text":
            node["text"] = text_overrides.get(name, name.rsplit("/", 1)[-1])
        nodes.append(node)

    reference_size = data.get("referenceSize") or raw_nodes[root_name]["bounds"][2:4]
    return [int(round(reference_size[0])), int(round(reference_size[1]))], nodes


def from_inline(layout: dict[str, Any], profile: dict[str, Any]) -> tuple[list[int], list[dict[str, Any]]]:
    raw = [layout["screen"], *layout.get("nodes", [])]
    names = [str(node["name"]) for node in raw]
    ids = _unique_ids(names)
    name_to_raw = {str(node["name"]): node for node in raw}
    nodes: list[dict[str, Any]] = []

    def absolute_for(name: str) -> list[float]:
        record = name_to_raw[name]
        bounds = [float(value) for value in record["bounds"]]
        parent = record.get("parent")
        if parent and parent in name_to_raw:
            parent_abs = absolute_for(parent)
            return [parent_abs[0] + bounds[0], parent_abs[1] + bounds[1], bounds[2], bounds[3]]
        return bounds

    for index, record in enumerate(raw):
        name = str(record["name"])
        parent_name = record.get("parent")
        node_type = str(record["type"])
        node = {
            "id": ids[name],
            "name": name,
            "type": node_type,
            "parent": ids[parent_name] if parent_name else None,
            "bounds": [float(value) for value in record["bounds"]],
            "absoluteBounds": absolute_for(name),
            "role": record.get("role", "screen" if index == 0 else "semantic-node"),
            "dynamic": bool(record.get("dynamic", node_type == "text")),
            "layout": {"mode": record.get("layoutMode", "NONE"), "positioning": record.get("layoutPositioning", "AUTO")},
            "style": {**style_for(name, node_type, profile, is_root=index == 0), **record.get("style", {})},
            "asset": record.get("asset"),
            "provenance": {
                "method": "manual",
                "confidence": float(record.get("confidence", 1.0)),
                "reviewRequired": bool(record.get("reviewRequired", False))
            }
        }
        if node_type == "text":
            node["text"] = record.get("text", name.rsplit("/", 1)[-1])
        nodes.append(node)
    screen_bounds = raw[0]["bounds"]
    return [int(round(screen_bounds[2])), int(round(screen_bounds[3]))], nodes
