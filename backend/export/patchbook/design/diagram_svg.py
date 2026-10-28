"""Deterministic SVG technical diagrams for Design Engine packs.

Color is never the sole encoding: dash patterns + edge numbers + labels
always accompany stroke color (PATCH_BOOK_GENERATOR diagram rules).
"""

from __future__ import annotations

import html
import math
from typing import Any

from canon.contracts import PatchCompilation

# Stroke color + dash for grayscale discrimination
_SIGNAL_STYLE: dict[str, tuple[str, str, str]] = {
    # color, dasharray, marker label
    "audio": ("#F5A623", "0", "solid"),
    "cv": ("#3DDCFF", "6 3", "dash"),
    "gate": ("#7B61FF", "2 2", "dot"),
    "trigger": ("#E23D4A", "1 3", "dotdash"),
    "clock": ("#00C896", "8 2 2 2", "longdash"),
    "unknown": ("#8B919C", "4 4", "dash"),
}


def render_patch_diagram_svg(
    compilation: PatchCompilation,
    *,
    layout_algorithm_id: str = "orthogonal_schematic",
    width: int = 720,
    height: int = 480,
) -> str:
    """Return deterministic SVG for a sealed compilation graph."""
    graph = compilation.patch_graph
    title = html.escape(compilation.patch_plan.title)
    nodes = list(graph.nodes)
    edges = list(graph.edges)

    # Deterministic grid placement from sorted node ids
    sorted_nodes = sorted(nodes, key=lambda n: n.node_id)
    cols = max(1, int(len(sorted_nodes) ** 0.5 + 0.999) or 1)
    positions: dict[str, tuple[float, float]] = {}
    cell_w = (width - 80) / max(cols, 1)
    cell_h = (height - 100) / max((len(sorted_nodes) + cols - 1) // cols, 1)
    for i, node in enumerate(sorted_nodes):
        col = i % cols
        row = i // cols
        x = 50 + col * cell_w + cell_w / 2
        y = 60 + row * cell_h + cell_h / 2
        positions[node.node_id] = (x, y)

    # Port index for edge endpoints
    port_to_node: dict[str, str] = {}
    for n in nodes:
        for p in n.ports:
            port_to_node[p.port_id] = n.node_id

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" data-layout="{html.escape(layout_algorithm_id)}" '
        f'data-artifact="{html.escape(graph.artifact_id)}">',
        "<defs>",
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#1A1A1A"/>',
        "</marker>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#FAFAFA"/>',
        f'<text x="16" y="24" font-family="Helvetica, sans-serif" font-size="14" '
        f'font-weight="700" fill="#1A1A1A">{title}</text>',
        f'<text x="16" y="42" font-family="Courier, monospace" font-size="10" fill="#6B7280">'
        f"nodes={len(nodes)} edges={len(edges)} · non-color: dash+number+label</text>",
    ]

    # Legend
    lx = width - 150
    ly = 20
    parts.append(
        f'<text x="{lx}" y="{ly}" font-family="Helvetica" font-size="9" fill="#6B7280">legend</text>'
    )
    for i, (sig, (color, dash, name)) in enumerate(_SIGNAL_STYLE.items()):
        yy = ly + 14 + i * 12
        parts.append(
            f'<line x1="{lx}" y1="{yy}" x2="{lx + 28}" y2="{yy}" '
            f'stroke="{color}" stroke-width="2" stroke-dasharray="{dash}"/>'
        )
        parts.append(
            f'<text x="{lx + 34}" y="{yy + 3}" font-family="Courier" font-size="8" fill="#1A1A1A">'
            f"{sig}/{name}</text>"
        )

    # Edges first (under nodes)
    for idx, edge in enumerate(sorted(edges, key=lambda e: e.edge_id)):
        src_node = port_to_node.get(edge.source_port_id)
        dst_node = port_to_node.get(edge.target_port_id)
        if not src_node or not dst_node:
            continue
        x1, y1 = positions[src_node]
        x2, y2 = positions[dst_node]
        color, dash, _ = _SIGNAL_STYLE.get(edge.signal_type, _SIGNAL_STYLE["unknown"])
        # Orthogonal-ish mid path for schematic family
        mx = (x1 + x2) / 2
        if layout_algorithm_id in {"orthogonal_schematic", "title_block_engineering"}:
            d = f"M {x1:.1f} {y1:.1f} L {mx:.1f} {y1:.1f} L {mx:.1f} {y2:.1f} L {x2:.1f} {y2:.1f}"
        elif layout_algorithm_id == "hex_cell_map":
            d = f"M {x1:.1f} {y1:.1f} Q {mx:.1f} {(y1+y2)/2 - 20:.1f} {x2:.1f} {y2:.1f}"
        else:
            d = f"M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}"
        parts.append(
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-dasharray="{dash}" marker-end="url(#arrow)" '
            f'data-edge="{html.escape(edge.edge_id)}" data-signal="{html.escape(edge.signal_type)}"/>'
        )
        # Route number (color-independent)
        parts.append(
            f'<circle cx="{mx:.1f}" cy="{(y1+y2)/2:.1f}" r="9" fill="#fff" stroke="#1A1A1A" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{mx:.1f}" y="{(y1+y2)/2 + 3:.1f}" text-anchor="middle" '
            f'font-family="Courier" font-size="9" font-weight="700" fill="#1A1A1A">{idx + 1}</text>'
        )

    # Nodes
    for node in sorted_nodes:
        x, y = positions[node.node_id]
        label_lines = _label_lines(node.label)
        # Hex-ish for hive; rounded rect otherwise
        if layout_algorithm_id == "hex_cell_map":
            r = 28
            pts = _hex_points(x, y, r)
            parts.append(
                f'<polygon points="{pts}" fill="#1A1A1A" stroke="#F5A623" stroke-width="1.5"/>'
            )
        elif layout_algorithm_id == "brutalist_blocks":
            parts.append(
                f'<rect x="{x-40:.1f}" y="{y-22:.1f}" width="80" height="44" fill="#1A1A1A"/>'
            )
        else:
            parts.append(
                f'<rect x="{x-42:.1f}" y="{y-20:.1f}" width="84" height="40" rx="4" '
                f'fill="#FFFFFF" stroke="#1A1A1A" stroke-width="1.5"/>'
            )
        fill = (
            "#FFFFFF" if layout_algorithm_id in {"hex_cell_map", "brutalist_blocks"} else "#1A1A1A"
        )
        if len(label_lines) == 1:
            parts.append(
                f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" '
                f'font-family="Helvetica" font-size="10" fill="{fill}">{html.escape(label_lines[0])}</text>'
            )
        else:
            # A long name wraps inside the node instead of being cut (spec 002 FR-003).
            top = y + 4 - (len(label_lines) - 1) * 5.5
            spans = "".join(
                f'<tspan x="{x:.1f}" y="{top + i * 11:.1f}">{html.escape(text)}</tspan>'
                for i, text in enumerate(label_lines)
            )
            parts.append(
                f'<text text-anchor="middle" font-family="Helvetica" font-size="10" '
                f'fill="{fill}"><title>{html.escape(node.label)}</title>{spans}</text>'
            )

    parts.append("</svg>\n")
    return "\n".join(parts)


# Labels this short render on one line, as they always have.
SINGLE_LINE_LABEL = 18
# Width available inside a node, and how many lines fit in its height.
LABEL_WIDTH = 76.0
MAX_LABEL_LINES = 3


def _label_lines(label: str) -> list[str]:
    if len(label) <= SINGLE_LINE_LABEL:
        return [label]
    from reportlab.pdfbase.pdfmetrics import stringWidth

    lines: list[str] = []
    cur = ""
    for word in label.split():
        trial = f"{cur} {word}" if cur else word
        if stringWidth(trial, "Helvetica", 10) <= LABEL_WIDTH or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) > MAX_LABEL_LINES or any(stringWidth(line, "Helvetica", 10) > LABEL_WIDTH * 1.25 for line in lines):
        from export.patchbook.design.engine import PreflightFailed

        raise PreflightFailed(
            "PATCH_PAGE_DIAGRAM_OVERFLOW",
            f"Module label {label!r} does not fit its diagram node. Remediation: give the "
            "module a shorter display name.",
        )
    return lines


def _hex_points(cx: float, cy: float, r: float) -> str:
    pts: list[str] = []
    for i in range(6):
        # Pointy-top hex; fixed angles for determinism
        angle = math.pi / 6 + i * math.pi / 3
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        pts.append(f"{px:.1f},{py:.1f}")
    return " ".join(pts)


def diagram_manifest_entry(path: str, svg_text: str) -> dict[str, Any]:
    from canon.contracts import canonical_sha256

    return {
        "path": path,
        "byte_length": len(svg_text.encode("utf-8")),
        "sha256": canonical_sha256(svg_text),
    }
