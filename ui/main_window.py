from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from data.games import GAMES
from data.state import ChecklistState
from scrapers.registry import refresh_all
from ui import theme
from ui.dashboard_tab import DashboardTab
from ui.game_tab import GameTab

ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


def _game_icon(game_id: str) -> QIcon:
    path = ICONS_DIR / f"{game_id}.png"
    return QIcon(str(path)) if path.exists() else QIcon()


class RefreshWorker(QThread):
    finished_ok = Signal(int)
    finished_err = Signal(str)

    def run(self) -> None:
        try:
            cache = refresh_all()
            total = sum(len(v) for v in cache.values())
            self.finished_ok.emit(total)
        except Exception as exc:  # scrapers already guard themselves, this is a last resort
            self.finished_err.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gacha Dailies Tracker")
        self.resize(1080, 820)
        self.setMinimumSize(880, 620)

        self.state = ChecklistState()
        self._worker: RefreshWorker | None = None

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.setIconSize(self.tabs.iconSize() * 1.4)
        self.tabs.setDocumentMode(True)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        tab_wrap = QWidget()
        tab_layout = QVBoxLayout(tab_wrap)
        tab_layout.setContentsMargins(14, 10, 14, 0)
        tab_layout.addWidget(self.tabs)
        layout.addWidget(tab_wrap)

        self.game_tabs: dict[str, GameTab] = {}
        self._populate_tabs()

        self.setCentralWidget(central)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._tick)
        self._countdown_timer.start(60_000)

    # --------------------------------------------------------------- header
    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("appHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(14)

        mark = QLabel("◆")
        mark.setStyleSheet(f"color: {theme.ACCENT}; font-size: 20px;")
        layout.addWidget(mark)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title = QLabel("Gacha Dailies Tracker")
        title.setObjectName("appTitle")
        title_col.addWidget(title)
        self.status_label = QLabel("Showing cached data — refresh for the latest.")
        self.status_label.setObjectName("appSubtitle")
        title_col.addWidget(self.status_label)
        layout.addLayout(title_col)

        layout.addStretch()

        self.refresh_button = QPushButton("Refresh events && banners")
        self.refresh_button.setObjectName("primary")
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.setToolTip("Re-scrape event and banner schedules for all four games")
        self.refresh_button.clicked.connect(self.start_refresh)
        layout.addWidget(self.refresh_button)
        return header

    # ----------------------------------------------------------------- tabs
    def _populate_tabs(self) -> None:
        self.dashboard_tab = DashboardTab(self.state)
        self.tabs.addTab(self.dashboard_tab, "  Today  ")
        for game in GAMES.values():
            tab = GameTab(game, self.state)
            self.game_tabs[game.id] = tab
            self.tabs.addTab(tab, _game_icon(game.id), f" {game.name} ")

    def _tick(self) -> None:
        for tab in self.game_tabs.values():
            tab.refresh_countdowns()

    def _on_tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self.dashboard_tab:
            self.dashboard_tab.refresh()

    # -------------------------------------------------------------- refresh
    def start_refresh(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Refreshing…")
        self.status_label.setText("Fetching the latest schedules…")
        self._worker = RefreshWorker()
        self._worker.finished_ok.connect(self._on_refresh_ok)
        self._worker.finished_err.connect(self._on_refresh_err)
        self._worker.start()

    def _reset_button(self) -> None:
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("Refresh events && banners")

    def _on_refresh_ok(self, total_events: int) -> None:
        self._reset_button()
        now = datetime.now(timezone.utc).strftime("%d %b, %H:%M UTC")
        self.status_label.setText(f"Updated {now} · {total_events} events & banners cached")
        self._rebuild_tabs()

    def _on_refresh_err(self, message: str) -> None:
        self._reset_button()
        self.status_label.setText("Refresh failed — still showing cached data.")
        QMessageBox.warning(self, "Refresh failed", message)

    def _rebuild_tabs(self) -> None:
        current_index = self.tabs.currentIndex()
        self.tabs.clear()
        self.game_tabs.clear()
        self._populate_tabs()
        self.tabs.setCurrentIndex(max(0, min(current_index, self.tabs.count() - 1)))
