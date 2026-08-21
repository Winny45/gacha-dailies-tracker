from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from data.events_cache import load_events
from data.games import GameConfig
from data.schema import Event, Period, Task
from data.state import ChecklistState, last_daily_reset, last_weekly_reset
from ui import theme
from ui.banner_guide import BannerGuideDialog
from ui.components import Badge, Card, Chip, ProgressRow, SectionCard, divider, pretty_title
from ui.thumbnails import load_thumbnail

ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


def _format_countdown(target: datetime) -> str:
    delta = target - datetime.now(timezone.utc)
    hours, remainder = divmod(max(0, int(delta.total_seconds())), 3600)
    minutes = remainder // 60
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days}d {hours}h"
    return f"{hours}h {minutes}m"


def _format_minutes(total: int) -> str:
    if total < 60:
        return f"{total} min"
    hours, minutes = divmod(total, 60)
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


class GameTab(QWidget):
    def __init__(self, game: GameConfig, state: ChecklistState, parent: QWidget | None = None):
        super().__init__(parent)
        self.game = game
        self.state = state
        self.accent = theme.game_accent(game.id)
        self._checkboxes: list[tuple[Task, QCheckBox]] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        layout.addWidget(self._build_hero())
        layout.addLayout(self._build_task_columns())

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        events = load_events().get(game.id, [])
        current = sorted((e for e in events if e.is_current(now)), key=lambda e: e.end or datetime.max)
        upcoming = sorted((e for e in events if e.is_upcoming(now)), key=lambda e: e.start)

        layout.addWidget(
            self._build_events_card("Live now", current, "Nothing running right now.")
        )
        layout.addWidget(
            self._build_events_card("Coming up", upcoming, "Nothing announced yet.")
        )
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        self.refresh_countdowns()
        self._update_progress()

    # ------------------------------------------------------------------ hero
    def _build_hero(self) -> Card:
        card = Card()
        card.body.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(12)

        icon_path = ICONS_DIR / f"{self.game.id}.png"
        if icon_path.exists():
            icon = QLabel()
            pix = QPixmap(str(icon_path)).scaled(
                44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            icon.setPixmap(pix)
            icon.setFixedSize(44, 44)
            top.addWidget(icon)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        name = QLabel(self.game.name)
        name.setObjectName("heroName")
        name_col.addWidget(name)
        tz = QLabel(self.game.reset.tz_note)
        tz.setObjectName("faint")
        name_col.addWidget(tz)
        top.addLayout(name_col)
        top.addStretch()

        self.guide_button = QPushButton("Banner Guide")
        self.guide_button.setObjectName("primary")
        self.guide_button.setCursor(Qt.PointingHandCursor)
        self.guide_button.setToolTip("Pull recommendations compared across sources")
        self.guide_button.clicked.connect(self._open_banner_guide)
        top.addWidget(self.guide_button, alignment=Qt.AlignVCenter)

        card.body.addLayout(top)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.daily_chip = Chip("")
        self.weekly_chip = Chip("")
        chips.addWidget(self.daily_chip)
        chips.addWidget(self.weekly_chip)
        chips.addStretch()
        card.body.addLayout(chips)

        self.progress = ProgressRow(accent=self.accent)
        card.body.addWidget(self.progress)
        return card

    # ----------------------------------------------------------------- tasks
    def _build_task_columns(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        for period, title in ((Period.DAILY, "Daily"), (Period.WEEKLY, "Weekly")):
            tasks = [t for t in self.game.tasks if t.period == period]
            total = sum(t.estimated_minutes for t in tasks)
            card = SectionCard(
                title, f"{len(tasks)} tasks · ~{_format_minutes(total)}", accent=self.accent
            )
            for task in tasks:
                cb = QCheckBox(f"{task.label}   ~{task.estimated_minutes}m")
                cb.setCursor(Qt.PointingHandCursor)
                if task.note:
                    cb.setToolTip(task.note)
                cb.setChecked(self.state.is_done(task.id, self.game.reset, task.period))
                cb.toggled.connect(lambda checked, t=task: self._on_toggled(t, checked))
                card.add(cb)
                self._checkboxes.append((task, cb))
            # the two columns have different task counts; without this the
            # shorter one centres its rows against the taller one
            card.body.addStretch()
            row.addWidget(card, stretch=1)
        return row

    # ---------------------------------------------------------------- events
    def _build_events_card(self, title: str, events: list[Event], empty_msg: str) -> SectionCard:
        card = SectionCard(title, f"{len(events)}", accent=self.accent)
        if not events:
            card.add_empty(empty_msg)
            return card
        for i, event in enumerate(events):
            if i:
                card.add(divider())
            card.add(self._build_event_row(event))
        return card

    def _build_event_row(self, event: Event) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)

        thumb = QLabel()
        pixmap = load_thumbnail(event.image_url, game_id=event.game_id, size=44)
        if pixmap is not None:
            thumb.setPixmap(pixmap)
        thumb.setFixedSize(44, 44)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet(f"background-color: {theme.SURFACE_ALT}; border-radius: 8px;")
        layout.addWidget(thumb)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel(html.escape(pretty_title(event.title)))
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 600;")
        text_col.addWidget(title)
        when = QLabel(event.raw_date_text or "date to be confirmed")
        when.setObjectName("faint")
        when.setWordWrap(True)
        text_col.addWidget(when)
        layout.addLayout(text_col, stretch=1)

        is_banner = event.category == "banner"
        layout.addWidget(
            Badge("BANNER" if is_banner else "EVENT", self.accent if is_banner else theme.TEXT_FAINT),
            alignment=Qt.AlignTop,
        )
        return row

    # --------------------------------------------------------------- actions
    def _open_banner_guide(self) -> None:
        BannerGuideDialog(self.game, parent=self).exec()

    def _on_toggled(self, task: Task, checked: bool) -> None:
        self.state.set_done(task.id, checked)
        self._update_progress()

    def _update_progress(self) -> None:
        done = [t for t, cb in self._checkboxes if cb.isChecked()]
        remaining = sum(t.estimated_minutes for t, cb in self._checkboxes if not cb.isChecked())
        total_tasks = len(self._checkboxes)
        if remaining == 0 and total_tasks:
            caption = "All done — go enjoy the games."
            value = "0 min left"
        else:
            caption = f"{len(done)} of {total_tasks} tasks done"
            value = f"{_format_minutes(remaining)} left"
        self.progress.set_progress(len(done), total_tasks, caption, value)

    def refresh_countdowns(self) -> None:
        next_daily = last_daily_reset(self.game.reset) + timedelta(days=1)
        next_weekly = last_weekly_reset(self.game.reset) + timedelta(days=7)
        self.daily_chip.setText(f"Daily reset in {_format_countdown(next_daily)}")
        self.weekly_chip.setText(f"Weekly reset in {_format_countdown(next_weekly)}")
