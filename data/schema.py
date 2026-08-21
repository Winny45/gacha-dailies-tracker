"""Shared data types for tasks (dailies/weeklies) and events/banners."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Period(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass(frozen=True)
class Task:
    """A single recurring checklist item for one game (e.g. 'Simulation Room')."""
    id: str
    game_id: str
    label: str
    period: Period
    estimated_minutes: int = 5
    note: str = ""


@dataclass(frozen=True)
class ResetSchedule:
    """When a game's daily/weekly counters reset, in UTC."""
    daily_reset_hour_utc: int
    weekly_reset_weekday: int  # Monday=0 .. Sunday=6
    weekly_reset_hour_utc: int
    tz_note: str = ""


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    """Scrapers parse dates from many sites; some yield tz-aware datetimes,
    some naive. Normalize to naive UTC so events from different games can be
    sorted/compared together without TypeError."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=None)


@dataclass
class Event:
    """A banner, event, or other time-limited thing to plan around."""
    game_id: str
    title: str
    category: str  # e.g. "banner", "event", "maintenance"
    start: datetime | None
    end: datetime | None
    source_url: str
    source_name: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_date_text: str = ""  # fallback if dates couldn't be parsed precisely
    image_url: str = ""  # character portrait / banner art, if the source has one
    verdict: str = ""  # short pull recommendation, e.g. "Recommended", "Skip"
    analysis: str = ""  # pros/cons blurb backing the verdict, if the source has one

    def __post_init__(self) -> None:
        self.start = _to_naive_utc(self.start)
        self.end = _to_naive_utc(self.end)

    def is_current(self, now: datetime) -> bool:
        """Already started, and not confirmed ended."""
        started = self.start is None or self.start <= now
        not_ended = self.end is None or self.end >= now
        return started and not_ended

    def is_upcoming(self, now: datetime) -> bool:
        return self.start is not None and self.start > now

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "title": self.title,
            "category": self.category,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "fetched_at": self.fetched_at.isoformat(),
            "raw_date_text": self.raw_date_text,
            "image_url": self.image_url,
            "verdict": self.verdict,
            "analysis": self.analysis,
        }

    @staticmethod
    def from_dict(d: dict) -> "Event":
        return Event(
            game_id=d["game_id"],
            title=d["title"],
            category=d["category"],
            start=datetime.fromisoformat(d["start"]) if d.get("start") else None,
            end=datetime.fromisoformat(d["end"]) if d.get("end") else None,
            source_url=d["source_url"],
            source_name=d["source_name"],
            fetched_at=datetime.fromisoformat(d["fetched_at"]),
            raw_date_text=d.get("raw_date_text", ""),
            image_url=d.get("image_url", ""),
            verdict=d.get("verdict", ""),
            analysis=d.get("analysis", ""),
        )
