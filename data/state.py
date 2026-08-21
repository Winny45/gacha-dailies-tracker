"""Persists which checklist items the user has completed, and figures out
when each one goes back to "not done" based on the game's reset schedule."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data.schema import Period, ResetSchedule

STATE_PATH = Path(__file__).resolve().parent.parent / "user_data" / "checklist_state.json"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def last_daily_reset(schedule: ResetSchedule, now: datetime | None = None) -> datetime:
    now = now or _utcnow()
    candidate = now.replace(hour=schedule.daily_reset_hour_utc, minute=0, second=0, microsecond=0)
    if candidate > now:
        candidate -= timedelta(days=1)
    return candidate


def last_weekly_reset(schedule: ResetSchedule, now: datetime | None = None) -> datetime:
    now = now or _utcnow()
    candidate = now.replace(
        hour=schedule.weekly_reset_hour_utc, minute=0, second=0, microsecond=0
    )
    days_since = (candidate.weekday() - schedule.weekly_reset_weekday) % 7
    candidate -= timedelta(days=days_since)
    if candidate > now:
        candidate -= timedelta(days=7)
    return candidate


class ChecklistState:
    """task_id -> ISO timestamp of when it was last marked complete."""

    def __init__(self, path: Path = STATE_PATH):
        self._path = path
        self._data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def is_done(self, task_id: str, schedule: ResetSchedule, period: Period) -> bool:
        stamp = self._data.get(task_id)
        if not stamp:
            return False
        completed_at = datetime.fromisoformat(stamp)
        boundary = (
            last_daily_reset(schedule)
            if period == Period.DAILY
            else last_weekly_reset(schedule)
        )
        return completed_at >= boundary

    def set_done(self, task_id: str, done: bool) -> None:
        if done:
            self._data[task_id] = _utcnow().isoformat()
        else:
            self._data.pop(task_id, None)
        self._save()
