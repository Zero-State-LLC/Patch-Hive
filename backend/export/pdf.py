"""
PDF export functionality for patch books.
Generates PDFs with rack layouts, patch diagrams, and waveforms.
"""

import io
import os
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from core import settings
from patches.models import Patch
from racks.models import Rack


def _draw_wrapped(c, text: str, x: float, y: float, *, width: float, font: str, size: float, leading: float) -> float:
    """Draw ``text`` wrapped to ``width`` (never cut, spec 002 FR-003); returns the next y."""
    c.setFont(font, size)
    for line in simpleSplit(text, font, size, width):
        c.drawString(x, y, line)
        y -= leading
    return y

from .visualization import generate_patch_diagram_svg, generate_rack_layout_svg
from .waveform import generate_waveform_svg, infer_waveform_params_from_patch


def _load_svg2rlg():
    try:
        from svglib.svglib import svg2rlg
    except ImportError as exc:
        raise RuntimeError("svglib is required for PDF exports") from exc
    return svg2rlg


def generate_patch_pdf(db: Session, patch: Patch, output_path: Optional[str] = None) -> str:
    """
    Generate a PDF for a single patch.

    Args:
        db: Database session
        patch: Patch to export
        output_path: Output file path (generated if not provided)

    Returns:
        Path to generated PDF
    """
    # Generate output path if not provided
    if output_path is None:
        os.makedirs(settings.export_dir, exist_ok=True)
        output_path = os.path.join(
            settings.export_dir, f"patch_{patch.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )

    # Create canvas
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 24)
    c.drawString(inch, height - inch, patch.name)

    # Metadata
    c.setFont("Helvetica", 12)
    y = height - inch - 30
    c.drawString(inch, y, f"Category: {patch.category}")
    y -= 20
    c.drawString(inch, y, f"Generation Seed: {patch.generation_seed}")
    y -= 20
    c.drawString(inch, y, f"Engine Version: {patch.generation_version}")
    y -= 40

    # Description
    if patch.description:
        y = _draw_wrapped(
            c, f"Description: {patch.description}", inch, y,
            width=width - 2 * inch, font="Helvetica", size=10, leading=13,
        )
        y -= 27

    # Get rack
    rack = db.query(Rack).filter(Rack.id == patch.rack_id).first()

    # Rack layout
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Rack Layout")
    y -= 20

    try:
        svg2rlg = _load_svg2rlg()
        rack_svg = generate_rack_layout_svg(db, rack, width=int(width - 2 * inch))
        rack_svg_io = io.StringIO(rack_svg)
        rack_drawing = svg2rlg(rack_svg_io)
        if rack_drawing:
            # Scale to fit
            scale = min((width - 2 * inch) / rack_drawing.width, 200 / rack_drawing.height)
            rack_drawing.scale(scale, scale)
            rack_drawing.drawOn(c, inch, y - rack_drawing.height * scale - 20)
            y -= rack_drawing.height * scale + 40
    except Exception as e:
        c.setFont("Helvetica", 10)
        c.drawString(inch, y, f"[Rack layout could not be rendered: {e}]")
        y -= 40

    # New page for patch diagram
    c.showPage()
    y = height - inch

    # Patch diagram
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Patch Connections")
    y -= 20

    try:
        svg2rlg = _load_svg2rlg()
        patch_svg = generate_patch_diagram_svg(
            db, rack, patch.connections, width=int(width - 2 * inch), colorize_cables=False
        )
        patch_svg_io = io.StringIO(patch_svg)
        patch_drawing = svg2rlg(patch_svg_io)
        if patch_drawing:
            scale = min((width - 2 * inch) / patch_drawing.width, 300 / patch_drawing.height)
            patch_drawing.scale(scale, scale)
            patch_drawing.drawOn(c, inch, y - patch_drawing.height * scale - 20)
            y -= patch_drawing.height * scale + 40
    except Exception as e:
        c.setFont("Helvetica", 10)
        c.drawString(inch, y, f"[Patch diagram could not be rendered: {e}]")
        y -= 40

    # Waveform (if enough space, otherwise new page)
    if y < 300:
        c.showPage()
        y = height - inch

    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Waveform Approximation")
    y -= 20

    try:
        svg2rlg = _load_svg2rlg()
        # Infer waveform params from patch
        has_lfo = any("lfo" in conn.get("from_port", "").lower() for conn in patch.connections)
        has_envelope = any(
            "envelope" in conn.get("from_port", "").lower() for conn in patch.connections
        )
        waveform_params = infer_waveform_params_from_patch(patch.category, has_lfo, has_envelope)

        waveform_svg = generate_waveform_svg(
            waveform_params, width=800, height=200, seed=patch.generation_seed
        )
        waveform_svg_io = io.StringIO(waveform_svg)
        waveform_drawing = svg2rlg(waveform_svg_io)
        if waveform_drawing:
            scale = min((width - 2 * inch) / waveform_drawing.width, 200 / waveform_drawing.height)
            waveform_drawing.scale(scale, scale)
            waveform_drawing.drawOn(c, inch, y - waveform_drawing.height * scale - 20)
    except Exception as e:
        c.setFont("Helvetica", 10)
        c.drawString(inch, y, f"[Waveform could not be rendered: {e}]")

    # Footer
    c.setFont("Helvetica", 8)
    c.drawString(
        inch,
        0.5 * inch,
        f"Generated by PatchHive v{settings.app_version} on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )

    # Save
    c.save()

    return output_path


def generate_rack_pdf(db: Session, rack: Rack, output_path: Optional[str] = None) -> str:
    """
    Generate a PDF for a rack with all its patches.

    Args:
        db: Database session
        rack: Rack to export
        output_path: Output file path (generated if not provided)

    Returns:
        Path to generated PDF
    """
    # Generate output path if not provided
    if output_path is None:
        os.makedirs(settings.export_dir, exist_ok=True)
        output_path = os.path.join(
            settings.export_dir, f"rack_{rack.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )

    # Get all patches for this rack
    patches = db.query(Patch).filter(Patch.rack_id == rack.id).all()

    # Create canvas
    svg2rlg = _load_svg2rlg()
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter

    # Cover page
    c.setFont("Helvetica-Bold", 32)
    c.drawString(inch, height - 2 * inch, rack.name)

    c.setFont("Helvetica", 16)
    c.drawString(inch, height - 2.5 * inch, f"Rack Configuration")
    c.drawString(inch, height - 2.8 * inch, f"{len(patches)} Patches")

    y = height - 3.2 * inch
    if rack.description:
        y = _draw_wrapped(
            c, rack.description, inch, y, width=width - 2 * inch, font="Helvetica", size=12, leading=15,
        )

    c.setFont("Helvetica", 10)
    c.drawString(
        inch,
        y - 0.25 * inch,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )

    c.showPage()

    # For each patch, add pages
    for i, patch in enumerate(patches):
        # Generate patch pages (simplified version)
        y = height - inch
        c.setFont("Helvetica-Bold", 20)
        c.drawString(inch, y, f"{i + 1}. {patch.name}")
        y -= 30

        c.setFont("Helvetica", 12)
        c.drawString(inch, y, f"Category: {patch.category}")
        y -= 20

        if patch.description:
            _draw_wrapped(
                c, patch.description, inch, y, width=width - 2 * inch, font="Helvetica", size=10, leading=13,
            )

        c.showPage()

    # Footer on last page
    c.setFont("Helvetica", 8)
    c.drawString(
        inch,
        0.5 * inch,
        f"Generated by PatchHive v{settings.app_version}",
    )

    c.save()

    return output_path
