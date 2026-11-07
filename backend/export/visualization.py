"""
Patch and rack visualization generator.
Creates SVG diagrams showing module layouts and patch connections.
"""

import html
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from cases.models import Case
from modules.models import Module
from racks.layout import rack_row_widths
from racks.models import Rack, RackModule


def generate_rack_layout_svg(db: Session, rack: Rack, width: int = 1200, hp_width: int = 10) -> str:
    """
    Generate an SVG visualization of the rack layout.

    Args:
        db: Database session
        rack: Rack to visualize
        width: Total SVG width
        hp_width: Pixels per HP unit

    Returns:
        SVG string
    """
    # Get case and rack modules; a Rig with no Case (spec 009) is as wide as its Modules.
    case = db.query(Case).filter(Case.id == rack.case_id).first()
    rack_modules = db.query(RackModule).filter(RackModule.rack_id == rack.id).all()
    rows = rack_row_widths(db, case, rack_modules)
    if not rows:
        return "<svg></svg>"
    case_label = f"{case.brand} {case.name}" if case else "No Case"

    # Calculate dimensions
    module_h = 120
    row_gap = 60
    row_height = module_h + row_gap
    total_height = row_height * len(rows) + 40

    # Build SVG
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{total_height}" xmlns="http://www.w3.org/2000/svg">
  <!-- Background -->
  <rect width="{width}" height="{total_height}" fill="#1a1a1a"/>

  <!-- Title -->
  <text x="20" y="25" fill="#fff" font-family="Arial, sans-serif" font-size="18" font-weight="bold">{html.escape(rack.name)}</text>
  <text x="20" y="45" fill="#888" font-family="Arial, sans-serif" font-size="12">{html.escape(case_label)}</text>
"""

    # Draw each row
    for row_idx, row_hp in enumerate(rows):
        row_y = 60 + row_idx * row_height

        # Row background
        svg += f"""
  <!-- Row {row_idx} -->
  <rect x="20" y="{row_y}" width="{row_hp * hp_width}" height="{module_h}" fill="#2a2a2a" stroke="#444" stroke-width="2" rx="4"/>
"""

        # HP markers (every 10HP)
        for hp in range(0, row_hp + 1, 10):
            x = 20 + hp * hp_width
            svg += f"""
  <line x1="{x}" y1="{row_y}" x2="{x}" y2="{row_y + module_h}" stroke="#333" stroke-width="1"/>
  <text x="{x + 2}" y="{row_y + module_h - 5}" fill="#666" font-family="monospace" font-size="10">{hp}</text>
"""

        # Draw modules in this row
        for rm in rack_modules:
            if rm.row_index != row_idx:
                continue

            module = db.query(Module).filter(Module.id == rm.module_id).first()
            if not module:
                continue

            module_x = 20 + rm.start_hp * hp_width
            module_width = module.hp * hp_width

            # Module rectangle
            # Color based on type
            color = get_module_color(module.module_type)

            svg += f"""
  <!-- Module {module.id} -->
  <rect x="{module_x}" y="{row_y + 5}" width="{module_width - 2}" height="{module_h - 10}" fill="{color}" stroke="#555" stroke-width="1" rx="2"/>
  <text x="{module_x + module_width / 2}" y="{row_y + module_h / 2 - 10}" fill="#fff" font-family="Arial, sans-serif" font-size="10" text-anchor="middle" font-weight="bold">{html.escape(module.brand)}</text>
  <text x="{module_x + module_width / 2}" y="{row_y + module_h / 2 + 5}" fill="#fff" font-family="Arial, sans-serif" font-size="9" text-anchor="middle">{html.escape(module.name[:15])}</text>
  <text x="{module_x + module_width / 2}" y="{row_y + module_h / 2 + 20}" fill="#ccc" font-family="monospace" font-size="8" text-anchor="middle">{module.hp}HP</text>
"""

    svg += """
</svg>"""

    return svg


def generate_patch_diagram_svg(
    db: Session,
    rack: Rack,
    connections: List[Dict[str, Any]],
    width: int = 1200,
    hp_width: int = 10,
    colorize_cables: bool = True,
) -> str:
    """
    Generate an SVG visualization of a patch (connections between modules).

    Args:
        db: Database session
        rack: Rack containing the modules
        connections: List of connections
        width: Total SVG width
        hp_width: Pixels per HP unit

    Returns:
        SVG string
    """
    # Get case and modules; a Rig with no Case (spec 009) is as wide as its Modules.
    case = db.query(Case).filter(Case.id == rack.case_id).first()
    rack_modules = db.query(RackModule).filter(RackModule.rack_id == rack.id).all()
    rows = rack_row_widths(db, case, rack_modules)
    if not rows:
        return "<svg></svg>"

    # Build module position map
    module_positions: Dict[int, tuple[float, float, int]] = {}
    module_h = 120
    row_gap = 60
    row_height = module_h + row_gap

    for rm in rack_modules:
        module = db.query(Module).filter(Module.id == rm.module_id).first()
        if not module:
            continue

        module_x = 20 + (rm.start_hp + module.hp / 2) * hp_width
        module_y = 60 + rm.row_index * row_height + module_h / 2

        module_positions[module.id] = (module_x, module_y, rm.row_index)

    # Calculate height
    total_height = row_height * len(rows) + 40

    # Start SVG
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{total_height}" xmlns="http://www.w3.org/2000/svg">
  <!-- Background -->
  <rect width="{width}" height="{total_height}" fill="#0a0a0a"/>

  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <polygon points="0 0, 10 3, 0 6" fill="currentColor" />
    </marker>
  </defs>

  <!-- Modules (simplified) -->
"""

    # Draw modules as circles
    for module_id, (x, y, _) in module_positions.items():
        module = db.query(Module).filter(Module.id == module_id).first()
        if not module:
            continue

        color = get_module_color(module.module_type)
        svg += f"""
  <circle cx="{x}" cy="{y}" r="25" fill="{color}" stroke="#fff" stroke-width="2"/>
  <text x="{x}" y="{y + 5}" fill="#fff" font-family="Arial, sans-serif" font-size="10" text-anchor="middle" font-weight="bold">{html.escape(module.module_type)}</text>
"""

    # Draw connections
    svg += "\n  <!-- Connections -->\n"
    for conn in connections:
        from_id = conn.get("from_module_id")
        to_id = conn.get("to_module_id")
        cable_type = conn.get("cable_type", "audio")

        if from_id not in module_positions or to_id not in module_positions:
            continue

        x1, y1, row_from = module_positions[from_id]
        x2, y2, row_to = module_positions[to_id]

        # Cable color based on type
        cable_color = "#000000"
        if colorize_cables:
            cable_color = get_cable_color(cable_type)

        lane_y = min(y1, y2) - (80 + 20 * abs(row_from - row_to))

        svg += f"""
  <path d="M {x1} {y1} L {x1} {lane_y} L {x2} {lane_y} L {x2} {y2}" stroke="{cable_color}" color="{cable_color}" stroke-width="2" fill="none" opacity="0.8" marker-end="url(#arrowhead)"/>
"""

    svg += """
</svg>"""

    return svg


def get_module_color(module_type: str) -> str:
    """Get color for module type."""
    mtype = module_type.upper()
    if "VCO" in mtype or "OSCILLATOR" in mtype:
        return "#ff4444"  # Red
    elif "VCF" in mtype or "FILTER" in mtype:
        return "#4444ff"  # Blue
    elif "VCA" in mtype or "AMPLIFIER" in mtype:
        return "#44ff44"  # Green
    elif "ENV" in mtype or "ENVELOPE" in mtype:
        return "#ffaa44"  # Orange
    elif "LFO" in mtype:
        return "#aa44ff"  # Purple
    elif "SEQ" in mtype:
        return "#44aaff"  # Light blue
    elif "MIX" in mtype:
        return "#ffff44"  # Yellow
    elif "FX" in mtype or "EFFECT" in mtype:
        return "#ff44aa"  # Pink
    else:
        return "#888888"  # Gray


def get_cable_color(cable_type: str) -> str:
    """Get color for cable type."""
    if cable_type == "audio":
        return "#000000"  # Black
    elif cable_type == "cv":
        return "#2b6cff"  # Blue
    elif cable_type == "gate":
        return "#ff9f1c"  # Orange
    elif cable_type == "clock":
        return "#d43f3a"  # Red
    else:
        return "#888888"  # Gray
