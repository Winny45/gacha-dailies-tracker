"""Small reusable widgets shared by the tabs. Styling comes from
ui/theme.py via objectName selectors; only genuinely per-instance colours
(badges, progress fills, game accents) are set inline here."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui import theme


class Card(QFrame):
    """Rounded surface panel. `flat=True` for nested/inner panels."""

    def __init__(self, flat: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("cardFlat" if flat else "card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(8)


class SectionCard(Card):
    """A Card with a title row, optional count chip and accent tick."""

    def __init__(
        self,
        title: str,
        count_text: str = "",
        accent: str = theme.ACCENT,
        parent: QWidget | None = None,
    ):
        super().__init__(parent=parent)
        header = QHBoxLayout()
        header.setSpacing(8)

        tick = QFrame()
        tick.setFixedSize(3, 14)
        tick.setStyleSheet(f"background-color: {accent}; border-radius: 1px;")
        header.addWidget(tick)

        label = QLabel(title.upper())
        label.setObjectName("sectionTitle")
        header.addWidget(label)

        if count_text:
            count = QLabel(count_text)
            count.setObjectName("sectionCount")
            header.addWidget(count)

        header.addStretch()
        self.body.addLayout(header)

        self.content = QVBoxLayout()
        self.content.setSpacing(4)
        self.body.addLayout(self.content)

    def add(self, widget: QWidget) -> None:
        self.content.addWidget(widget)

    def add_empty(self, message: str) -> None:
        label = QLabel(message)
        label.setObjectName("empty")
        label.setWordWrap(True)
        self.content.addWidget(label)


class Badge(QLabel):
    """Small coloured pill. Tinted background with a solid text colour reads
    better against the dark surface than a fully saturated fill."""

    def __init__(self, text: str, color: str, solid: bool = False, parent: QWidget | None = None):
        super().__init__(text, parent)
        if solid:
            style = f"background-color: {color}; color: #10121a;"
        else:
            style = f"background-color: {_tint(color)}; color: {color};"
        self.setStyleSheet(
            style
            + " padding: 3px 10px; border-radius: 9px; font-size: 11px; font-weight: 700;"
        )
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)


class Chip(QLabel):
    """Muted informational pill (reset countdowns, timezone notes)."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setStyleSheet(
            f"background-color: {theme.SURFACE_ALT}; color: {theme.TEXT_DIM};"
            f" border: 1px solid {theme.BORDER_SOFT};"
            " padding: 4px 10px; border-radius: 9px; font-size: 12px;"
        )
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)


class StatTile(Card):
    """Big-number tile for the dashboard."""

    def __init__(self, label: str, value: str, color: str = theme.TEXT, parent: QWidget | None = None):
        super().__init__(flat=True, parent=parent)
        self.body.setContentsMargins(14, 12, 14, 12)
        self.body.setSpacing(2)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("statValue")
        self.value_label.setStyleSheet(f"color: {color};")
        self.body.addWidget(self.value_label)

        caption = QLabel(label.upper())
        caption.setObjectName("statLabel")
        self.body.addWidget(caption)


class ProgressRow(QWidget):
    """Labelled progress bar that recolours as it approaches complete."""

    def __init__(self, accent: str = theme.ACCENT, parent: QWidget | None = None):
        super().__init__(parent)
        self.accent = accent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        top = QHBoxLayout()
        self.caption = QLabel("")
        self.caption.setObjectName("muted")
        top.addWidget(self.caption)
        top.addStretch()
        self.value = QLabel("")
        self.value.setStyleSheet("font-weight: 700;")
        top.addWidget(self.value)
        layout.addLayout(top)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        layout.addWidget(self.bar)

    def set_progress(self, done: int, total: int, caption: str, value_text: str) -> None:
        pct = int(round(100 * done / total)) if total else 0
        self.bar.setValue(pct)
        colour = theme.GREEN if total and done >= total else self.accent
        self.bar.setStyleSheet(
            f"QProgressBar {{ background-color: {theme.TRACK}; border: none;"
            " border-radius: 5px; }"
            f" QProgressBar::chunk {{ background-color: {colour}; border-radius: 5px; }}"
        )
        self.caption.setText(caption)
        self.value.setText(value_text)
        self.value.setStyleSheet(
            f"font-weight: 700; color: {theme.GREEN if total and done >= total else theme.TEXT};"
        )


def pretty_title(text: str) -> str:
    """Display-only tidy-up. Some sources join a character and costume with
    a plain double hyphen ("Helena -- Sunny Inn Hand"); an en dash reads
    better. The stored title is left untouched so name matching still works."""
    return (text or "").replace(" -- ", " – ")


def divider() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {theme.BORDER_SOFT};")
    return line


def _tint(hex_color: str) -> str:
    """Blend an accent toward the surface colour for badge backgrounds."""
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
    except (ValueError, IndexError):
        return theme.SURFACE_ALT
    base = (0x1c, 0x20, 0x2c)
    mix = lambda c, b: int(b + (c - b) * 0.22)
    return f"#{mix(r, base[0]):02x}{mix(g, base[1]):02x}{mix(b, base[2]):02x}"
