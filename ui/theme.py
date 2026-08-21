"""Central visual theme: palette, per-game accent colours, and the global
Qt stylesheet.

Everything visual lives here so the individual tabs stay about behaviour.
Widgets opt into styling by objectName (e.g. `setObjectName("card")`)
rather than carrying their own inline setStyleSheet calls.
"""
from __future__ import annotations

from pathlib import Path

ASSETS_UI = Path(__file__).resolve().parent.parent / "assets" / "ui"

# ---------------------------------------------------------------------------
# Palette -- a dark "midnight" base with a violet accent
# ---------------------------------------------------------------------------
BG = "#0e1017"
SURFACE = "#161923"
SURFACE_ALT = "#1c202c"
SURFACE_HOVER = "#222736"
BORDER = "#282d3d"
BORDER_SOFT = "#20242f"
TRACK = "#272d3d"  # progress-bar groove; needs to read against SURFACE

TEXT = "#e9ecf5"
TEXT_DIM = "#a2aac2"
TEXT_FAINT = "#6f7891"

ACCENT = "#7c6cff"
ACCENT_HOVER = "#8f81ff"
ACCENT_SOFT = "#2a2650"

GREEN = "#35d399"
AMBER = "#f5b544"
RED = "#ff5f6d"
BLUE = "#4da3ff"

# Per-game accent, used for the tab hero bar and progress fill so each game
# feels distinct without needing four separate themes.
GAME_ACCENTS = {
    "nikke": "#ff4d6d",
    "blue_archive": "#4da3ff",
    "limbus": "#f5c518",
    "brown_dust_2": "#c084fc",
}


def game_accent(game_id: str) -> str:
    return GAME_ACCENTS.get(game_id, ACCENT)


def verdict_color(label: str) -> str:
    """Shared colour logic for pull-verdict badges."""
    upper = (label or "").upper()
    if "STRONG" in upper:
        return GREEN
    if "GOOD" in upper:
        return "#5cc98d"
    if "SITUATIONAL" in upper:
        return AMBER
    if "SKIP" in upper or "LOW PRIORITY" in upper:
        return RED
    return TEXT_FAINT


# ---------------------------------------------------------------------------
# Generated assets
# ---------------------------------------------------------------------------
CHECK_PNG = ASSETS_UI / "check.png"

# Qt stylesheets have no way to draw a tick, and `image: url(...)` renders
# at the file's native size with no scaling -- so the mark is painted once
# at exactly the size the indicator's inner area needs. (An SVG here does
# not reliably render through the stylesheet, hence the PNG.)
_CHECK_PX = 12


def ensure_assets() -> None:
    ASSETS_UI.mkdir(parents=True, exist_ok=True)
    if CHECK_PNG.exists():
        return
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

    image = QImage(_CHECK_PX, _CHECK_PX, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#ffffff"))
    pen.setWidthF(2.0)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.drawPolyline(
        QPolygonF([QPointF(2.4, 6.2), QPointF(4.9, 8.8), QPointF(9.6, 3.4)])
    )
    painter.end()
    image.save(str(CHECK_PNG))


def _qss_path(path: Path) -> str:
    # Qt stylesheets want forward slashes even on Windows
    return str(path).replace("\\", "/")


def stylesheet() -> str:
    ensure_assets()
    check_url = _qss_path(CHECK_PNG)
    return f"""
    /* NOTE: deliberately no background-color on the universal QWidget rule.
       Setting one there makes every child QLabel paint the window colour
       over its parent card, which shows up as dark rectangles inside the
       panels. Only real surfaces get a background. */
    QWidget {{
        color: {TEXT};
        font-family: "Segoe UI", "Inter", sans-serif;
        font-size: 13px;
    }}
    QMainWindow, QDialog {{ background-color: {BG}; }}
    QLabel, QCheckBox {{ background: transparent; }}

    /* ---------- app header ---------- */
    #appHeader {{
        background-color: {SURFACE};
        border-bottom: 1px solid {BORDER};
    }}
    #appTitle {{
        font-size: 17px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }}
    #appSubtitle {{ color: {TEXT_FAINT}; font-size: 12px; }}

    /* ---------- cards & sections ---------- */
    #card {{
        background-color: {SURFACE};
        border: 1px solid {BORDER_SOFT};
        border-radius: 12px;
    }}
    #cardFlat {{
        background-color: {SURFACE_ALT};
        border: 1px solid {BORDER_SOFT};
        border-radius: 10px;
    }}
    #sectionTitle {{
        font-size: 13px;
        font-weight: 700;
        color: {TEXT};
        letter-spacing: 0.4px;
    }}
    #sectionCount {{
        color: {TEXT_FAINT};
        font-size: 12px;
    }}
    #heroName {{ font-size: 21px; font-weight: 800; letter-spacing: 0.2px; }}
    #muted {{ color: {TEXT_DIM}; }}
    #faint {{ color: {TEXT_FAINT}; font-size: 12px; }}
    #empty {{ color: {TEXT_FAINT}; font-style: italic; }}
    #statValue {{ font-size: 20px; font-weight: 800; }}
    #statLabel {{ color: {TEXT_FAINT}; font-size: 11px; letter-spacing: 0.6px; }}

    /* ---------- buttons ---------- */
    QPushButton {{
        background-color: {SURFACE_ALT};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 9px;
        padding: 9px 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: {SURFACE_HOVER}; border-color: {ACCENT}; }}
    QPushButton:pressed {{ background-color: {ACCENT_SOFT}; }}
    QPushButton:disabled {{ color: {TEXT_FAINT}; border-color: {BORDER_SOFT}; }}

    QPushButton#primary {{
        background-color: {ACCENT};
        border: 1px solid {ACCENT};
        color: #ffffff;
    }}
    QPushButton#primary:hover {{ background-color: {ACCENT_HOVER}; }}
    QPushButton#primary:disabled {{ background-color: {ACCENT_SOFT}; color: {TEXT_FAINT}; }}

    /* ---------- tabs ---------- */
    QTabWidget::pane {{
        border: none;
        background: {BG};
        top: -1px;
    }}
    QTabBar {{ qproperty-drawBase: 0; }}
    QTabBar::tab {{
        background: transparent;
        color: {TEXT_FAINT};
        padding: 9px 16px;
        margin-right: 4px;
        border: 1px solid transparent;
        border-radius: 9px;
        font-weight: 600;
    }}
    QTabBar::tab:hover {{ color: {TEXT}; background: {SURFACE}; }}
    QTabBar::tab:selected {{
        color: {TEXT};
        background: {SURFACE_ALT};
        border-color: {BORDER};
    }}

    /* ---------- checkboxes ---------- */
    QCheckBox {{
        spacing: 10px;
        padding: 6px 4px;
        color: {TEXT};
    }}
    QCheckBox:hover {{ color: #ffffff; }}
    QCheckBox::indicator {{
        width: 17px; height: 17px;
        border-radius: 5px;
        border: 2px solid #39405a;
        background: {SURFACE_ALT};
    }}
    QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
        image: url("{check_url}");
    }}
    QCheckBox:checked {{ color: {TEXT_FAINT}; }}

    /* ---------- progress ---------- */
    QProgressBar {{
        background-color: {TRACK};
        border: none;
        border-radius: 5px;
        height: 8px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{ border-radius: 5px; }}

    /* ---------- scroll ---------- */
    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: #333a4d; border-radius: 5px; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #414a63; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: #333a4d; border-radius: 5px; min-width: 30px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    QToolTip {{
        background-color: {SURFACE_ALT};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 5px 8px;
    }}
    """
