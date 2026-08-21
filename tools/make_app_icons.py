"""One-off generator for the PWA's home-screen icons.

Android masks icons to various shapes, so the mark is kept well inside a
safe area and the background is drawn edge-to-edge ("maskable").
Run:  .venv\\Scripts\\python.exe tools\\make_app_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPolygonF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "web" / "icons"

BG_TOP = "#191d2b"
BG_BOTTOM = "#0d0f16"
MARK_TOP = "#9b8cff"
MARK_BOTTOM = "#6a55ff"


def draw(size: int) -> QImage:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)

    bg = QLinearGradient(0, 0, 0, size)
    bg.setColorAt(0.0, QColor(BG_TOP))
    bg.setColorAt(1.0, QColor(BG_BOTTOM))
    p.setPen(Qt.NoPen)
    p.setBrush(bg)
    p.drawRect(0, 0, size, size)

    # diamond mark, kept inside the maskable safe area (~60% of the canvas)
    c = size / 2
    r = size * 0.26
    mark = QLinearGradient(c - r, c - r, c + r, c + r)
    mark.setColorAt(0.0, QColor(MARK_TOP))
    mark.setColorAt(1.0, QColor(MARK_BOTTOM))
    p.setBrush(mark)
    p.drawPolygon(
        QPolygonF(
            [
                QPointF(c, c - r),
                QPointF(c + r * 0.78, c),
                QPointF(c, c + r),
                QPointF(c - r * 0.78, c),
            ]
        )
    )

    # small orbiting dot, so it reads as more than a plain shape
    p.setBrush(QColor("#ff6b9d"))
    d = size * 0.055
    p.drawEllipse(QPointF(c + r * 0.72, c - r * 0.62), d, d)

    p.end()
    return image


def main() -> None:
    app = QApplication([])  # noqa: F841 -- QImage/QPainter need an app instance
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        path = OUT / f"icon-{size}.png"
        draw(size).save(str(path))
        print("wrote", path)
    draw(180).save(str(OUT / "apple-touch-icon.png"))
    print("wrote", OUT / "apple-touch-icon.png")


if __name__ == "__main__":
    main()
