"""Schematic renderer for PatchBook exports."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from cases.models import Case
from modules.models import Module
from racks.layout import placed_spans, row_widths
from racks.models import Rack, RackModule

from .models import PatchSchematic, WiringConnection


def _cable_style(cable_type: str) -> tuple[str, str]:
    cable_type = (cable_type or "").lower()
    if cable_type in {"gate", "trigger", "clock"}:
        return "#111111", "4,2"
    if cable_type == "cv":
        return "#444444", "2,2"
    return "#000000", ""


def _module_label(module: Module) -> str:
    return module.module_type or module.name


def build_wiring_list(connections: list[dict[str, Any]], modules: dict[int, Module]) -> list[WiringConnection]:
    wiring = []
    for conn in connections:
        from_id = conn.get("from_module_id")
        to_id = conn.get("to_module_id")
        if from_id not in modules or to_id not in modules:
            continue
        wiring.append(
            WiringConnection(
                from_module=modules[from_id].name,
                from_port=conn.get("from_port", ""),
                to_module=modules[to_id].name,
                to_port=conn.get("to_port", ""),
                cable_type=conn.get("cable_type", "audio"),
            )
        )
    return sorted(
        wiring,
        key=lambda item: (
            item.from_module,
            item.from_port,
            item.to_module,
            item.to_port,
            item.cable_type,
        ),
    )


def render_patch_schematic(
    db: Session,
    rack: Rack,
    connections: list[dict[str, Any]],
) -> PatchSchematic:
    """Render schematic diagram SVG and wiring list."""
    rack_modules = (
        db.query(RackModule)
        .filter(RackModule.rack_id == rack.id)
        .order_by(RackModule.row_index.asc(), RackModule.start_hp.asc(), RackModule.module_id.asc())
        .all()
    )
    modules = {
        rm.module_id: db.query(Module).filter(Module.id == rm.module_id).first()
        for rm in rack_modules
    }
    modules = {module_id: module for module_id, module in modules.items() if module}

    wiring_list = build_wiring_list(connections, modules)

    # A Rig with no Case (spec 009) is drawn as wide as its Modules.
    case = db.query(Case).filter(Case.id == rack.case_id).first()
    rows = row_widths(case, placed_spans(rack_modules, modules))
    if not rows or not rack_modules:
        return PatchSchematic(diagram_svg=None, wiring_list=wiring_list)

    module_h = 80
    row_gap = 40
    row_height = module_h + row_gap
    hp_width = 8
    width = max(rows) * hp_width + 80
    height = row_height * len(rows) + 40

    module_positions: dict[int, tuple[float, float]] = {}
    for rm in rack_modules:
        module = modules.get(rm.module_id)
        if not module:
            continue
        x = 40 + (rm.start_hp + module.hp / 2) * hp_width
        y = 40 + rm.row_index * row_height + module_h / 2
        module_positions[module.id] = (x, y)

    svg_parts = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        f"<svg width=\"{width}\" height=\"{height}\" xmlns=\"http://www.w3.org/2000/svg\">",
        f"<rect width=\"{width}\" height=\"{height}\" fill=\"#ffffff\"/>",
    ]

    for module_id, (x, y) in module_positions.items():
        module = modules.get(module_id)
        if not module:
            continue
        label = _module_label(module)
        svg_parts.append(
            f"<circle cx=\"{x}\" cy=\"{y}\" r=\"22\" fill=\"#f3f4f6\" stroke=\"#111827\" stroke-width=\"2\"/>"
        )
        svg_parts.append(
            f"<text x=\"{x}\" y=\"{y + 4}\" font-family=\"Helvetica\" font-size=\"8\" text-anchor=\"middle\" fill=\"#111827\">{label}</text>"
        )

    sorted_connections = sorted(
        connections,
        key=lambda item: (
            item.get("from_module_id", 0),
            item.get("to_module_id", 0),
            item.get("from_port", ""),
            item.get("to_port", ""),
        ),
    )

    for conn in sorted_connections:
        from_id = conn.get("from_module_id")
        to_id = conn.get("to_module_id")
        if from_id not in module_positions or to_id not in module_positions:
            continue
        x1, y1 = module_positions[from_id]
        x2, y2 = module_positions[to_id]
        stroke, dash = _cable_style(conn.get("cable_type", "audio"))
        dash_attr = f" stroke-dasharray=\"{dash}\"" if dash else ""
        svg_parts.append(
            f"<line x1=\"{x1}\" y1=\"{y1}\" x2=\"{x2}\" y2=\"{y2}\" stroke=\"{stroke}\" stroke-width=\"1.5\"{dash_attr}/>"
        )

    svg_parts.append("</svg>")

    return PatchSchematic(diagram_svg="".join(svg_parts), wiring_list=wiring_list)
