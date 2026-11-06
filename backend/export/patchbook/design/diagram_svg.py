"""Deterministic technical diagrams for Design Engine packs (spec 002 FR-011).

One geometry, drawn twice: as the SVG in the pack and on the patch's page in the PDF, so
the two can't disagree. Each module is a box that lists the jacks this patch uses, inputs on
the left and outputs on the right, each with its cable's number. Labels sit inside the box,
so they can't land on a route.

Color is never the sole encoding: dash patterns, route numbers and labels always accompany
stroke color (PATCH_BOOK_GENERATOR diagram rules).
"""

from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from reportlab.pdfbase.pdfmetrics import stringWidth

from canon.compiler import _cycle_edges
from canon.contracts import PatchCompilation

# Stroke color + dash for grayscale discrimination
_SIGNAL_STYLE: dict[str, tuple[str, str, str]] = {
    # color, dasharray, marker label
    "audio": ("#B8730A", "0", "solid"),
    "cv": ("#0A7EA4", "6 3", "dash"),
    "gate": ("#5B3FD9", "2 2", "dot"),
    "trigger": ("#C22B38", "1 3", "dotdash"),
    "clock": ("#00806A", "8 2 2 2", "longdash"),
    "unknown": ("#6B7280", "4 4", "dash"),
}
LEGEND_SIGNALS = ("audio", "cv", "gate", "trigger", "clock")

# The usable width of a US Letter page with one-inch margins. The SVG uses the same coordinates.
DIAGRAM_WIDTH = 468.0
TITLE_FONT, TITLE_SIZE, TITLE_LEADING = "Helvetica-Bold", 8.0, 9.5
JACK_FONT, JACK_SIZE, JACK_LEADING = "Helvetica", 7.0, 9.0
BOX_PAD = 4.0
SIDE_MARGIN = 16.0
COLUMN_GAP = 30.0
ROW_GAP = 16.0
LEGEND_HEIGHT = 14.0
# Pack SVG only: the title and caption above the shared geometry.
SVG_HEADER_HEIGHT = 40.0


@dataclass(frozen=True)
class DiagramJack:
    number: int
    side: Literal["in", "out"]
    lines: tuple[str, ...]
    y: float  # the height the cable meets the box


@dataclass(frozen=True)
class DiagramBox:
    node_id: str
    x: float
    y: float
    width: float
    height: float
    title_lines: tuple[str, ...]
    jacks: tuple[DiagramJack, ...]


@dataclass(frozen=True)
class DiagramRoute:
    edge_id: str
    number: int
    signal: str
    points: tuple[tuple[float, float], ...]
    feedback: bool


@dataclass(frozen=True)
class DiagramLayout:
    width: float
    height: float
    boxes: tuple[DiagramBox, ...]
    routes: tuple[DiagramRoute, ...]


def wrap_to_width(
    text: str, font: str, size: float, max_width: float, rest_width: float | None = None
) -> list[str]:
    """Wrap by measured width; continuation lines may be narrower (``rest_width``). A
    single word wider than its line is split across lines, never cut and never given
    extra spaces."""
    lines: list[str] = []
    cur = ""

    def limit() -> float:
        return max_width if not lines or rest_width is None else rest_width

    for word in text.split():
        trial = f"{cur} {word}" if cur else word
        if stringWidth(trial, font, size) <= limit():
            cur = trial
            continue
        if cur:
            lines.append(cur)
            cur = ""
        while stringWidth(word, font, size) > limit():
            cut = len(word)
            while cut > 1 and stringWidth(word[:cut], font, size) > limit():
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


def numbered_edges(edges: Any) -> list[tuple[int, Any]]:
    """Each cable's number, shared by the routes and the page's connection list (FR-011).
    ``edge-10`` comes after ``edge-2``."""

    def key(edge: Any) -> tuple[int, str]:
        match = re.search(r"(\d+)$", edge.edge_id)
        return (int(match.group(1)) if match else 0, edge.edge_id)

    return list(enumerate(sorted(edges, key=key), start=1))


def feedback_edge_ids(graph: Any) -> set[str]:
    """Edges in a loop, whether the graph declares them or not."""
    ports_to_nodes = {port.port_id: node.node_id for node in graph.nodes for port in node.ports}
    declared = {edge.edge_id for edge in graph.edges if edge.feedback_cycle_id}
    return declared | _cycle_edges(tuple(graph.edges), ports_to_nodes)


def _flow_order(graph: Any, ports_to_nodes: dict[str, str]) -> list[Any]:
    """Sources first, so most routes run forward. Ties and loops fall back to node id."""
    remaining = {node.node_id: node for node in graph.nodes}
    incoming = {node_id: 0 for node_id in remaining}
    pairs = []
    for edge in graph.edges:
        source, target = ports_to_nodes[edge.source_port_id], ports_to_nodes[edge.target_port_id]
        if source != target:
            pairs.append((source, target))
            incoming[target] += 1
    ordered = []
    while remaining:
        ready = [node_id for node_id in remaining if incoming[node_id] == 0]
        chosen = min(ready or remaining)
        ordered.append(remaining.pop(chosen))
        for source, target in pairs:
            if source == chosen and target in remaining:
                incoming[target] -= 1
    return ordered


def layout_diagram(
    compilation: PatchCompilation, *, module_labels: Mapping[str, str] | None = None
) -> DiagramLayout:
    """The geometry of one patch's diagram, top-down in points. ``module_labels`` holds the
    names to print, by module id; a module not in it shows the label its graph was sealed with."""
    graph = compilation.patch_graph
    labels = module_labels or {}
    ports = {port.port_id: port for node in graph.nodes for port in node.ports}
    ports_to_nodes = {port.port_id: node.node_id for node in graph.nodes for port in node.ports}
    numbered = numbered_edges(graph.edges)
    feedback = feedback_edge_ids(graph)

    nodes = _flow_order(graph, ports_to_nodes)
    columns = max(1, math.ceil(math.sqrt(len(nodes))))
    box_width = (DIAGRAM_WIDTH - 2 * SIDE_MARGIN - (columns - 1) * COLUMN_GAP) / columns
    inner = box_width - 2 * BOX_PAD

    measured = []
    for node in nodes:
        title = wrap_to_width(
            labels.get(node.module_instance_id, node.label), TITLE_FONT, TITLE_SIZE, inner
        )
        jacks: list[tuple[int, Literal["in", "out"], list[str]]] = []
        for number, edge in numbered:
            tag = " FB" if edge.edge_id in feedback else ""
            for port_id, side in ((edge.target_port_id, "in"), (edge.source_port_id, "out")):
                if ports_to_nodes[port_id] != node.node_id:
                    continue
                text = f"{number}{tag} {ports[port_id].label}"
                jacks.append(
                    (number, side, wrap_to_width(text, JACK_FONT, JACK_SIZE, inner))  # type: ignore[arg-type]
                )
        # Inputs above outputs, as the signal reads.
        jacks.sort(key=lambda jack: (jack[1] != "in", jack[0]))
        lines = sum(len(jack[2]) for jack in jacks)
        height = 2 * BOX_PAD + len(title) * TITLE_LEADING + lines * JACK_LEADING
        measured.append((node, title, jacks, height))

    boxes: list[DiagramBox] = []
    row_bottom: dict[int, float] = {}
    row_top: dict[int, float] = {}
    y = 0.0
    for start in range(0, len(measured), columns):
        row = measured[start : start + columns]
        row_index = start // columns
        tallest = max(item[3] for item in row)
        row_top[row_index], row_bottom[row_index] = y, y + tallest
        for column, (node, title, jacks, height) in enumerate(row):
            x = SIDE_MARGIN + column * (box_width + COLUMN_GAP)
            line = y + BOX_PAD + len(title) * TITLE_LEADING
            placed = []
            for number, side, text_lines in jacks:
                placed.append(
                    DiagramJack(number, side, tuple(text_lines), line + JACK_LEADING / 2)
                )
                line += len(text_lines) * JACK_LEADING
            boxes.append(
                DiagramBox(
                    node_id=node.node_id,
                    x=x,
                    y=y,
                    width=box_width,
                    height=height,
                    title_lines=tuple(title),
                    jacks=tuple(placed),
                )
            )
        y += tallest + ROW_GAP

    by_node = {box.node_id: box for box in boxes}
    row_of = {box.node_id: index // columns for index, box in enumerate(boxes)}
    column_of = {box.node_id: index % columns for index, box in enumerate(boxes)}
    routes = []
    for number, edge in numbered:
        source_node = ports_to_nodes[edge.source_port_id]
        target_node = ports_to_nodes[edge.target_port_id]
        source = by_node[source_node]
        target = by_node[target_node]
        start_y = next(j.y for j in source.jacks if j.number == number and j.side == "out")
        end_y = next(j.y for j in target.jacks if j.number == number and j.side == "in")
        start_x = source.x + source.width
        end_x = target.x
        # Lanes keep cables sharing a gap from drawing on top of each other.
        lane = 3.0 + (number % 4) * 3.0
        if column_of[target_node] == column_of[source_node] + 1:
            mid_x = end_x - lane
            points = ((start_x, start_y), (mid_x, start_y), (mid_x, end_y), (end_x, end_y))
        else:
            # Anything else would run behind a box and read as ending there: out into the gap,
            # along the row gap, and in from the left.
            going_up = row_of[target_node] < row_of[source_node]
            row = row_of[source_node]
            bus_y = (
                row_top[row] - ROW_GAP / 2 - (number % 3) * 2.0
                if going_up
                else row_bottom[row] + ROW_GAP / 2 - (number % 3) * 2.0
            )
            out_x, in_x = start_x + lane, end_x - lane
            points = (
                (start_x, start_y),
                (out_x, start_y),
                (out_x, bus_y),
                (in_x, bus_y),
                (in_x, end_y),
                (end_x, end_y),
            )
        routes.append(
            DiagramRoute(
                edge_id=edge.edge_id,
                number=number,
                signal=edge.signal_type,
                points=points,
                feedback=edge.edge_id in feedback,
            )
        )

    total = y + LEGEND_HEIGHT
    return DiagramLayout(
        width=DIAGRAM_WIDTH, height=total, boxes=tuple(boxes), routes=tuple(routes)
    )


def _dash(signal: str) -> tuple[float, ...]:
    _, dash, _ = _SIGNAL_STYLE.get(signal, _SIGNAL_STYLE["unknown"])
    return tuple(float(part) for part in dash.split() if part != "0")


def _chamfered(box: DiagramBox, cut: float = 4.0) -> list[tuple[float, float]]:
    """The hive family's six-cornered cell."""
    x, y, w, h = box.x, box.y, box.width, box.height
    return [(x + cut, y), (x + w - cut, y), (x + w, y + h / 2), (x + w - cut, y + h), (x + cut, y + h), (x, y + h / 2)]


def render_patch_diagram_svg(
    compilation: PatchCompilation,
    *,
    layout_algorithm_id: str = "orthogonal_schematic",
    module_labels: Mapping[str, str] | None = None,
    width: int = 720,
) -> str:
    """Return deterministic SVG for a sealed compilation graph."""
    graph = compilation.patch_graph
    layout = layout_diagram(compilation, module_labels=module_labels)
    title = html.escape(compilation.patch_plan.title)
    view_height = layout.height + SVG_HEADER_HEIGHT
    height = round(view_height * width / layout.width)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {layout.width:.0f} {view_height:.1f}" '
        f'data-layout="{html.escape(layout_algorithm_id)}" '
        f'data-artifact="{html.escape(graph.artifact_id)}">',
        "<defs>",
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#1A1A1A"/>',
        "</marker>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#FAFAFA"/>',
        f'<text x="{SIDE_MARGIN:.0f}" y="16" font-family="Helvetica, sans-serif" font-size="11" '
        f'font-weight="700" fill="#1A1A1A">{title}</text>',
        f'<text x="{SIDE_MARGIN:.0f}" y="30" font-family="Courier, monospace" font-size="7" '
        f'fill="#4B5563">modules={len(graph.nodes)} cables={len(graph.edges)} · '
        "non-color: dash+number+label</text>",
        f'<g transform="translate(0 {SVG_HEADER_HEIGHT:.0f})">',
    ]

    # Routes first (under the boxes)
    for route in layout.routes:
        color, dash, _ = _SIGNAL_STYLE.get(route.signal, _SIGNAL_STYLE["unknown"])
        path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in route.points)
        feedback = ' data-feedback="true"' if route.feedback else ""
        parts.append(
            f'<path d="{path}" fill="none" stroke="{color}" '
            f'stroke-width="{1.6 if route.feedback else 1}" stroke-dasharray="{dash}" '
            f'marker-end="url(#arrow)" data-edge="{html.escape(route.edge_id)}" '
            f'data-route="{route.number}" data-signal="{html.escape(route.signal)}"{feedback}/>'
        )

    # Boxes, with their titles and jacks
    dark = layout_algorithm_id == "brutalist_blocks"
    ink = "#FFFFFF" if dark else "#1A1A1A"
    for box in layout.boxes:
        if layout_algorithm_id == "hex_cell_map":
            corners = " ".join(f"{x:.1f},{y:.1f}" for x, y in _chamfered(box))
            parts.append(f'<polygon points="{corners}" fill="#FFFFFF" stroke="#1A1A1A" stroke-width="1"/>')
        else:
            radius = 0 if dark else 3
            fill = "#1A1A1A" if dark else "#FFFFFF"
            parts.append(
                f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.width:.1f}" '
                f'height="{box.height:.1f}" rx="{radius}" fill="{fill}" stroke="#1A1A1A" stroke-width="1"/>'
            )
        baseline = box.y + BOX_PAD + TITLE_SIZE
        for line in box.title_lines:
            parts.append(
                f'<text x="{box.x + BOX_PAD:.1f}" y="{baseline:.1f}" font-family="Helvetica" '
                f'font-size="{TITLE_SIZE:.0f}" font-weight="700" fill="{ink}">{html.escape(line)}</text>'
            )
            baseline += TITLE_LEADING
        for jack in box.jacks:
            for index, line in enumerate(jack.lines):
                line_y = jack.y + 2.5 + index * JACK_LEADING
                if jack.side == "in":
                    position = f'x="{box.x + BOX_PAD:.1f}"'
                else:
                    position = f'x="{box.x + box.width - BOX_PAD:.1f}" text-anchor="end"'
                parts.append(
                    f'<text {position} y="{line_y:.1f}" font-family="Helvetica" '
                    f'font-size="{JACK_SIZE:.0f}" fill="{ink}">{html.escape(line)}</text>'
                )

    legend_y = layout.height - LEGEND_HEIGHT / 2
    step = (layout.width - 2 * SIDE_MARGIN) / len(LEGEND_SIGNALS)
    for index, signal in enumerate(LEGEND_SIGNALS):
        color, dash, _ = _SIGNAL_STYLE[signal]
        x = SIDE_MARGIN + index * step
        parts.append(
            f'<line x1="{x:.1f}" y1="{legend_y:.1f}" x2="{x + 26:.1f}" y2="{legend_y:.1f}" '
            f'stroke="{color}" stroke-width="1.5" stroke-dasharray="{dash}"/>'
        )
        parts.append(
            f'<text x="{x + 30:.1f}" y="{legend_y + 2.5:.1f}" font-family="Helvetica" '
            f'font-size="7" fill="#1A1A1A">{signal}</text>'
        )

    parts.append("</g>")
    parts.append("</svg>\n")
    return "\n".join(parts)


def draw_diagram_on_canvas(
    c: Any, layout: DiagramLayout, *, x: float, top: float, layout_algorithm_id: str
) -> None:
    """Draw the same geometry on a reportlab canvas. The page stays black and gray, so it
    reads the same on a grayscale printer (FR-005)."""

    def px(value: float) -> float:
        return x + value

    def py(value: float) -> float:
        return top - value

    for route in layout.routes:
        c.saveState()
        c.setLineWidth(1.6 if route.feedback else 0.8)
        c.setDash(*([list(_dash(route.signal))] if _dash(route.signal) else [[]]))
        path = c.beginPath()
        first, *rest = route.points
        path.moveTo(px(first[0]), py(first[1]))
        for point in rest:
            path.lineTo(px(point[0]), py(point[1]))
        c.drawPath(path, stroke=1, fill=0)
        c.setDash([])
        end_x, end_y = route.points[-1]
        head = c.beginPath()
        head.moveTo(px(end_x), py(end_y))
        head.lineTo(px(end_x) - 5, py(end_y) + 2.5)
        head.lineTo(px(end_x) - 5, py(end_y) - 2.5)
        head.close()
        c.setFillGray(0)
        c.drawPath(head, stroke=0, fill=1)
        c.restoreState()

    dark = layout_algorithm_id == "brutalist_blocks"
    for box in layout.boxes:
        c.saveState()
        c.setLineWidth(0.9)
        if layout_algorithm_id == "hex_cell_map":
            cell = c.beginPath()
            first, *rest = _chamfered(box)
            cell.moveTo(px(first[0]), py(first[1]))
            for point in rest:
                cell.lineTo(px(point[0]), py(point[1]))
            cell.close()
            c.setFillGray(1)
            c.drawPath(cell, stroke=1, fill=1)
        else:
            c.setFillGray(0.1 if dark else 1)
            c.roundRect(
                px(box.x), py(box.y + box.height), box.width, box.height, 0 if dark else 3, stroke=1, fill=1
            )
        c.setFillGray(1 if dark else 0)
        baseline = box.y + BOX_PAD + TITLE_SIZE
        c.setFont(TITLE_FONT, TITLE_SIZE)
        for line in box.title_lines:
            c.drawString(px(box.x + BOX_PAD), py(baseline), line)
            baseline += TITLE_LEADING
        c.setFont(JACK_FONT, JACK_SIZE)
        for jack in box.jacks:
            for index, line in enumerate(jack.lines):
                line_y = py(jack.y + 2.5 + index * JACK_LEADING)
                if jack.side == "in":
                    c.drawString(px(box.x + BOX_PAD), line_y, line)
                else:
                    c.drawRightString(px(box.x + box.width - BOX_PAD), line_y, line)
        c.restoreState()

    legend_y = layout.height - LEGEND_HEIGHT / 2
    step = (layout.width - 2 * SIDE_MARGIN) / len(LEGEND_SIGNALS)
    c.saveState()
    c.setFont(JACK_FONT, JACK_SIZE)
    for index, signal in enumerate(LEGEND_SIGNALS):
        sample_x = SIDE_MARGIN + index * step
        c.setDash(*([list(_dash(signal))] if _dash(signal) else [[]]))
        c.setLineWidth(1)
        c.line(px(sample_x), py(legend_y), px(sample_x + 26), py(legend_y))
        c.setDash([])
        c.drawString(px(sample_x + 30), py(legend_y + 2.5), signal)
    c.restoreState()


def diagram_manifest_entry(path: str, svg_text: str) -> dict[str, Any]:
    from canon.contracts import canonical_sha256

    return {
        "path": path,
        "byte_length": len(svg_text.encode("utf-8")),
        "sha256": canonical_sha256(svg_text),
    }
