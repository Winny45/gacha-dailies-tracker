from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from data.events_cache import load_events
from data.games import GAMES
from data.schema import Period
from data.state import ChecklistState
from ui import theme
from ui.components import Badge, Card, ProgressRow, SectionCard, StatTile, divider, pretty_title

ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"

SHOWN_TODO_LIMIT = 14


def _format_minutes(total: int) -> str:
    if total < 60:
        return f"{total} min"
    hours, minutes = divmod(total, 60)
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


class DashboardTab(QWidget):
    """Cross-game 'what's due / what's coming' overview.

    Rebuilds its content on every tab switch (see MainWindow) rather than
    just once at construction, so checking off a task on another tab is
    reflected here without a full app refresh.
    """

    def __init__(self, state: ChecklistState, parent: QWidget | None = None):
        super().__init__(parent)
        self.state = state
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._outer.addWidget(self._scroll)
        self.refresh()

    def refresh(self) -> None:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        remaining, total, tasks_done, tasks_total = self._totals()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cache = load_events()
        current_pairs, upcoming_pairs = self._event_pairs(cache, now)

        layout.addLayout(
            self._build_stats(remaining, total, tasks_done, tasks_total, len(current_pairs))
        )
        layout.addWidget(self._build_progress_card())
        layout.addWidget(self._build_todo_card())
        layout.addWidget(
            self._build_events_card("Live now", current_pairs, "No events running — or hit Refresh.")
        )
        layout.addWidget(
            self._build_events_card("Coming up", upcoming_pairs, "Nothing announced yet.")
        )
        layout.addStretch()
        self._scroll.setWidget(content)

    # ---------------------------------------------------------------- data
    def _totals(self) -> tuple[int, int, int, int]:
        remaining = total = tasks_done = tasks_total = 0
        for game in GAMES.values():
            for task in game.tasks:
                total += task.estimated_minutes
                tasks_total += 1
                if self.state.is_done(task.id, game.reset, task.period):
                    tasks_done += 1
                else:
                    remaining += task.estimated_minutes
        return remaining, total, tasks_done, tasks_total

    def _event_pairs(self, cache, now):
        current, upcoming = [], []
        for game_id, events in cache.items():
            name = GAMES[game_id].name if game_id in GAMES else game_id
            for e in events:
                if e.is_current(now):
                    current.append((game_id, name, e))
                elif e.is_upcoming(now):
                    upcoming.append((game_id, name, e))
        current.sort(key=lambda t: t[2].end or datetime.max)
        upcoming.sort(key=lambda t: t[2].start)
        return current, upcoming

    # ----------------------------------------------------------------- UI
    def _build_stats(self, remaining, total, tasks_done, tasks_total, live_count) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        done_colour = theme.GREEN if remaining == 0 else theme.TEXT
        row.addWidget(StatTile("time left today", _format_minutes(remaining), done_colour))
        row.addWidget(StatTile("tasks done", f"{tasks_done}/{tasks_total}", theme.ACCENT))
        row.addWidget(StatTile("events live", str(live_count), theme.BLUE))
        row.addWidget(StatTile("games tracked", str(len(GAMES)), theme.AMBER))
        return row

    def _build_progress_card(self) -> SectionCard:
        card = SectionCard("Progress by game", accent=theme.ACCENT)
        for i, game in enumerate(GAMES.values()):
            if i:
                card.add(divider())
            done = [t for t in game.tasks if self.state.is_done(t.id, game.reset, t.period)]
            left = sum(
                t.estimated_minutes
                for t in game.tasks
                if not self.state.is_done(t.id, game.reset, t.period)
            )
            bar = ProgressRow(accent=theme.game_accent(game.id))
            bar.set_progress(
                len(done),
                len(game.tasks),
                f"{game.name} — {len(done)}/{len(game.tasks)} tasks",
                "done" if left == 0 else f"{_format_minutes(left)} left",
            )
            card.add(bar)
        return card

    def _build_todo_card(self) -> SectionCard:
        pending: list[tuple] = []
        for game in GAMES.values():
            for task in game.tasks:
                if not self.state.is_done(task.id, game.reset, task.period):
                    pending.append((game, task))
        card = SectionCard("Still to do", f"{len(pending)}", accent=theme.AMBER)
        if not pending:
            card.add_empty("Everything's checked off. Nice work.")
            return card

        # the full list runs to 40+ items across four games, which buries
        # everything below it -- show a workable slice and point at the tabs
        shown = pending[:SHOWN_TODO_LIMIT]
        current_game = None
        for game, task in shown:
            if game is not current_game:
                current_game = game
                header = QLabel(game.name)
                header.setStyleSheet(
                    f"color: {theme.game_accent(game.id)}; font-weight: 700; margin-top: 6px;"
                )
                card.add(header)
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(4, 1, 0, 1)
            layout.setSpacing(8)
            tag = "D" if task.period == Period.DAILY else "W"
            layout.addWidget(
                Badge(tag, theme.ACCENT if task.period == Period.DAILY else theme.BLUE)
            )
            label = QLabel(task.label)
            label.setWordWrap(True)
            layout.addWidget(label, stretch=1)
            mins = QLabel(f"~{task.estimated_minutes}m")
            mins.setObjectName("faint")
            layout.addWidget(mins)
            card.add(row)
        if len(pending) > len(shown):
            more = QLabel(f"+{len(pending) - len(shown)} more — see the game tabs")
            more.setObjectName("faint")
            more.setStyleSheet("margin-top: 6px;")
            card.add(more)
        return card

    def _build_events_card(self, title: str, pairs: list[tuple], empty_msg: str) -> SectionCard:
        shown = pairs[:12]
        card = SectionCard(title, f"{len(pairs)}", accent=theme.BLUE)
        if not pairs:
            card.add_empty(empty_msg)
            return card
        for i, (game_id, game_name, event) in enumerate(shown):
            if i:
                card.add(divider())
            card.add(self._build_event_row(game_id, game_name, event))
        if len(pairs) > len(shown):
            more = QLabel(f"+{len(pairs) - len(shown)} more on the game tabs")
            more.setObjectName("faint")
            card.add(more)
        return card

    def _build_event_row(self, game_id: str, game_name: str, event) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(10)

        icon_path = ICONS_DIR / f"{game_id}.png"
        icon = QLabel()
        if icon_path.exists():
            icon.setPixmap(
                QPixmap(str(icon_path)).scaled(26, 26, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        icon.setFixedSize(26, 26)
        icon.setToolTip(game_name)
        layout.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(1)
        title = QLabel(html.escape(pretty_title(event.title)))
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 600;")
        col.addWidget(title)
        when = QLabel(event.raw_date_text or "date to be confirmed")
        when.setObjectName("faint")
        when.setWordWrap(True)
        col.addWidget(when)
        layout.addLayout(col, stretch=1)

        is_banner = event.category == "banner"
        layout.addWidget(
            Badge(
                "BANNER" if is_banner else "EVENT",
                theme.game_accent(game_id) if is_banner else theme.TEXT_FAINT,
            ),
            alignment=Qt.AlignTop,
        )
        return row
