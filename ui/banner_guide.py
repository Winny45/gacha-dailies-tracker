"""'Banner Guide' dialog -- shows just the current/upcoming character banners
for one game. Each card shows whatever single-source verdict the main
scraper already captured (see that game's scrapers/<game>.py docstring),
plus, once "Refresh Analysis" has been run at least once, a full
multi-source comparison (scrapers/consensus.py) with a consensus badge."""
from __future__ import annotations

import html
from datetime import datetime, timezone

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from data.consensus_cache import load_consensus, update_game_consensus
from data.events_cache import load_events
from data.games import GameConfig
from data.schema import Event
from scrapers.base import normalize_name
from scrapers.consensus import ConsensusVerdict, build_consensus_for_game
from ui import theme
from ui.components import Badge, Card, SectionCard, divider, pretty_title
from ui.thumbnails import load_thumbnail


class ConsensusWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, game_id: str, banners: list[Event]):
        super().__init__()
        self.game_id = game_id
        self.banners = banners

    def run(self) -> None:
        try:
            self.finished_ok.emit(build_consensus_for_game(self.game_id, self.banners))
        except Exception as exc:
            self.finished_err.emit(str(exc))


class BannerGuideDialog(QDialog):
    def __init__(self, game: GameConfig, parent: QWidget | None = None):
        super().__init__(parent)
        self.game = game
        self.accent = theme.game_accent(game.id)
        self._worker: ConsensusWorker | None = None
        self.setWindowTitle(f"{game.name} — Banner Guide")
        self.resize(760, 820)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        outer.addWidget(self._build_header())

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll)

        self._rebuild()

    def _build_header(self) -> Card:
        card = Card()
        card.body.setSpacing(8)

        row = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel(f"{self.game.name} — should you pull?")
        title.setObjectName("heroName")
        col.addWidget(title)
        self.status_label = QLabel("Verdicts are averaged across community tier lists.")
        self.status_label.setObjectName("faint")
        col.addWidget(self.status_label)
        row.addLayout(col)
        row.addStretch()

        self.refresh_button = QPushButton("Refresh Analysis")
        self.refresh_button.setObjectName("primary")
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.setToolTip("Re-fetch and compare every source for this game")
        self.refresh_button.clicked.connect(self._start_refresh)
        row.addWidget(self.refresh_button, alignment=Qt.AlignVCenter)

        card.body.addLayout(row)
        return card

    # ----------------------------------------------------------------- data
    def _current_banners(self) -> tuple[list[Event], list[Event]]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        banners = [e for e in load_events().get(self.game.id, []) if e.category == "banner"]
        current = sorted((e for e in banners if e.is_current(now)), key=lambda e: e.end or datetime.max)
        upcoming = sorted((e for e in banners if e.is_upcoming(now)), key=lambda e: e.start)
        return current, upcoming

    def _start_refresh(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        current, upcoming = self._current_banners()
        targets = current + upcoming
        if not targets:
            self.status_label.setText("Nothing to analyse — refresh on the main window first.")
            return
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Comparing…")
        self.status_label.setText(f"Comparing sources for {len(targets)} banner(s)…")
        self._worker = ConsensusWorker(self.game.id, targets)
        self._worker.finished_ok.connect(self._on_refresh_ok)
        self._worker.finished_err.connect(self._on_refresh_err)
        self._worker.start()

    def _reset_button(self) -> None:
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("Refresh Analysis")

    def _on_refresh_ok(self, results: dict[str, ConsensusVerdict]) -> None:
        update_game_consensus(self.game.id, results)
        self._reset_button()
        now = datetime.now(timezone.utc).strftime("%d %b, %H:%M UTC")
        self.status_label.setText(f"Analysis updated {now}")
        self._rebuild()

    def _on_refresh_err(self, message: str) -> None:
        self._reset_button()
        self.status_label.setText(f"Analysis failed: {message}")

    # ------------------------------------------------------------------- UI
    def _rebuild(self) -> None:
        current, upcoming = self._current_banners()
        cache = load_consensus()

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(12)
        layout.addWidget(self._build_section("Current banners", current, cache))
        layout.addWidget(self._build_section("Upcoming banners", upcoming, cache))
        layout.addStretch()
        self.scroll.setWidget(content)

    def _build_section(
        self, title: str, banners: list[Event], cache: dict[str, ConsensusVerdict]
    ) -> SectionCard:
        card = SectionCard(title, f"{len(banners)}", accent=self.accent)
        if not banners:
            card.add_empty("Nothing here — refresh on the main window first.")
            return card
        for i, event in enumerate(banners):
            if i:
                card.add(divider())
            key = f"{self.game.id}:{normalize_name(event.title)}"
            card.add(self._build_card(event, cache.get(key)))
        return card

    def _build_card(self, event: Event, consensus: ConsensusVerdict | None) -> QWidget:
        card = QWidget()
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 8, 0, 8)
        outer.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(12)
        thumb = QLabel()
        pixmap = load_thumbnail(event.image_url, game_id=event.game_id, size=56)
        if pixmap is not None:
            thumb.setPixmap(pixmap)
        thumb.setFixedSize(56, 56)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet(f"background-color: {theme.SURFACE_ALT}; border-radius: 8px;")
        header.addWidget(thumb)

        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel(html.escape(pretty_title(event.title)))
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 700; font-size: 14px;")
        col.addWidget(title)
        when = QLabel(event.raw_date_text or "date to be confirmed")
        when.setObjectName("faint")
        when.setWordWrap(True)
        col.addWidget(when)
        header.addLayout(col, stretch=1)

        badge_text, badge_color = self._badge_for(event, consensus)
        if badge_text:
            header.addWidget(Badge(badge_text, badge_color, solid=True), alignment=Qt.AlignTop)
        outer.addLayout(header)

        if consensus is not None and consensus.sources:
            for source in consensus.sources:
                outer.addWidget(self._build_source_block(source))
        elif event.analysis or event.verdict:
            if event.verdict:
                outer.addWidget(
                    QLabel(f"<b>{html.escape(event.source_name)}: {html.escape(event.verdict)}</b>")
                )
            if event.analysis:
                body = QLabel(event.analysis)
                body.setWordWrap(True)
                body.setTextFormat(Qt.PlainText)
                outer.addWidget(body)
            hint = QLabel('Hit "Refresh Analysis" for a full multi-source comparison.')
            hint.setObjectName("empty")
            outer.addWidget(hint)
        else:
            hint = QLabel('No pull-verdict data yet — hit "Refresh Analysis".')
            hint.setObjectName("empty")
            outer.addWidget(hint)
        return card

    def _build_source_block(self, source) -> QWidget:
        block = Card(flat=True)
        block.body.setContentsMargins(12, 10, 12, 10)
        block.body.setSpacing(6)

        top = QHBoxLayout()
        name = QLabel(html.escape(source.source_name))
        name.setStyleSheet(f"font-weight: 700; color: {theme.TEXT_DIM};")
        top.addWidget(name)
        top.addStretch()
        if source.raw_verdict:
            colour = theme.verdict_color(source.raw_verdict)
            if colour == theme.TEXT_FAINT and source.score is not None:
                colour = theme.verdict_color(_label_for_score(source.score))
            top.addWidget(Badge(html.escape(source.raw_verdict), colour))
        block.body.addLayout(top)

        if source.analysis:
            body = QLabel(source.analysis)
            body.setWordWrap(True)
            body.setTextFormat(Qt.PlainText)
            body.setObjectName("muted")
            block.body.addWidget(body)

        for heading, items, colour in (
            ("PROS", source.pros, theme.GREEN),
            ("CONS", source.cons, theme.RED),
        ):
            if not items:
                continue
            # third-party feed content -- escape before embedding in rich text
            bullets = "<br>".join(f"&bull;&nbsp; {html.escape(i)}" for i in items)
            label = QLabel(
                f"<span style='color:{colour}; font-weight:700; font-size:11px'>{heading}</span>"
                f"<br>{bullets}"
            )
            label.setWordWrap(True)
            label.setTextFormat(Qt.RichText)
            block.body.addWidget(label)

        if source.url:
            link = QLabel(f'<a style="color:{theme.ACCENT}" href="{source.url}">View source →</a>')
            link.setOpenExternalLinks(True)
            link.setStyleSheet("font-size: 12px;")
            block.body.addWidget(link)
        return block

    @staticmethod
    def _badge_for(event: Event, consensus: ConsensusVerdict | None) -> tuple[str, str]:
        if consensus is not None:
            if consensus.consensus_score is not None:
                text = f"{consensus.consensus_label}  {consensus.consensus_score:.1f}/5"
            else:
                text = consensus.consensus_label
            return text, theme.verdict_color(consensus.consensus_label)
        if event.verdict:
            return event.verdict, theme.TEXT_FAINT
        return "", ""


def _label_for_score(score: float) -> str:
    if score >= 4.3:
        return "Strong"
    if score >= 3.4:
        return "Good"
    if score >= 2.3:
        return "Situational"
    return "Skip"
