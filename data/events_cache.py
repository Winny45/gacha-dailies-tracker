"""Local cache of scraped events/banners, so the app has something to show
immediately on launch and only hits the network on refresh."""
from __future__ import annotations

import json
from pathlib import Path

from data.schema import Event

CACHE_PATH = Path(__file__).resolve().parent.parent / "user_data" / "events_cache.json"


def load_events() -> dict[str, list[Event]]:
    """Returns game_id -> list[Event]."""
    if not CACHE_PATH.exists():
        return {}
    try:
        raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        game_id: [Event.from_dict(e) for e in events]
        for game_id, events in raw.items()
    }


def save_events(events_by_game: dict[str, list[Event]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        game_id: [e.to_dict() for e in events]
        for game_id, events in events_by_game.items()
    }
    CACHE_PATH.write_text(json.dumps(raw, indent=2), encoding="utf-8")
