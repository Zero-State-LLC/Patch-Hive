"""The rig and patch PDFs wrap long text instead of cutting it (spec 002 FR-003)."""

from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth

from export.pdf import _draw_wrapped


class _Canvas:
    def __init__(self):
        self.lines: list[tuple[float, str]] = []
        self.font = ("Helvetica", 10)

    def setFont(self, name, size):  # noqa: N802 (reportlab API)
        self.font = (name, size)

    def drawString(self, x, y, text):  # noqa: N802
        self.lines.append((y, text))


def test_long_text_is_wrapped_whole_and_within_the_page() -> None:
    text = " ".join(f"word{i}" for i in range(120))  # far past the old 100-character cut
    canvas = _Canvas()
    width = 8.5 * inch - 2 * inch
    end = _draw_wrapped(canvas, text, inch, 700, width=width, font="Helvetica", size=10, leading=13)
    drawn = " ".join(line for _, line in canvas.lines)
    assert drawn.split() == text.split()
    assert len(canvas.lines) > 1
    assert all(stringWidth(line, "Helvetica", 10) <= width for _, line in canvas.lines)
    assert end == 700 - 13 * len(canvas.lines)
