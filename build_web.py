"""Builds the static PWA payload in web/.

Runs the existing scrapers, then writes plain JSON + the handful of images
the phone actually needs. Nothing in scrapers/ or data/ is modified -- this
is purely an export step, so the desktop app and the phone app always agree
on where their facts come from.

Run locally with:  .venv\\Scripts\\python.exe build_web.py
In CI it's run by .github/workflows/update-data.yml on a schedule.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from data.events_cache import load_events
from data.games import GAMES
from data.image_cache import local_path
from data.schema import Period
from scrapers.consensus import build_consensus_for_game
from scrapers.registry import refresh_all
from ui import theme

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
WEB_DATA = WEB / "data"
WEB_IMAGES = WEB / "images"
WEB_GAME_ICONS = WEB / "icons" / "games"
ICONS_SRC = ROOT / "assets" / "icons"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy_game_icons() -> None:
    WEB_GAME_ICONS.mkdir(parents=True, exist_ok=True)
    for game_id in GAMES:
        src = ICONS_SRC / f"{game_id}.png"
        if src.exists():
            shutil.copy2(src, WEB_GAME_ICONS / f"{game_id}.png")


def _export_image(image_url: str) -> str:
    """Copies a cached portrait into web/images and returns its relative
    path. Only banners the phone will actually display get exported, which
    keeps the published payload small instead of shipping the whole
    several-hundred-image cache."""
    if not image_url:
        return ""
    cached = local_path(image_url)
    if cached is None:
        return ""
    WEB_IMAGES.mkdir(parents=True, exist_ok=True)
    dest = WEB_IMAGES / cached.name
    if not dest.exists():
        shutil.copy2(cached, dest)
    return f"images/{cached.name}"


def _event_dict(event) -> dict:
    return {
        "title": event.title,
        "category": event.category,
        "start": event.start.isoformat() if event.start else None,
        "end": event.end.isoformat() if event.end else None,
        "when": event.raw_date_text or "",
        "image": _export_image(event.image_url),
        "source_name": event.source_name,
        "source_url": event.source_url,
    }


def write_games() -> None:
    payload = {
        "generated_at": _now(),
        "games": [
            {
                "id": game.id,
                "name": game.name,
                "accent": theme.game_accent(game.id),
                "icon": f"icons/games/{game.id}.png",
                "reset": {
                    "daily_hour_utc": game.reset.daily_reset_hour_utc,
                    "weekly_weekday": game.reset.weekly_reset_weekday,
                    "weekly_hour_utc": game.reset.weekly_reset_hour_utc,
                    "tz_note": game.reset.tz_note,
                },
                "tasks": [
                    {
                        "id": task.id,
                        "label": task.label,
                        "period": task.period.value,
                        "minutes": task.estimated_minutes,
                        "note": task.note,
                    }
                    for task in game.tasks
                ],
            }
            for game in GAMES.values()
        ],
    }
    (WEB_DATA / "games.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"  games.json      {sum(len(g.tasks) for g in GAMES.values())} tasks")


def _previous(name: str, key: str) -> dict:
    """Last published payload, used as a per-game fallback. CI runs from a
    clean checkout with no local cache, so if a source is down that game
    would otherwise publish as empty and wipe good data off the phone."""
    path = WEB_DATA / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get(key, {}) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def write_events_and_consensus(refresh: bool) -> None:
    cache = refresh_all() if refresh else load_events()
    prev_events = _previous("events.json", "games")
    prev_verdicts = _previous("consensus.json", "verdicts")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events_payload: dict[str, dict] = {}
    consensus_payload: dict[str, dict] = {}

    for game_id in GAMES:
        events = cache.get(game_id, [])
        if not events and prev_events.get(game_id):
            events_payload[game_id] = prev_events[game_id]
            for key, verdict in prev_verdicts.items():
                if key.startswith(f"{game_id}:"):
                    consensus_payload[key] = verdict
            print(f"  {game_id:<14} scrape empty -- keeping last published data")
            continue
        current = sorted((e for e in events if e.is_current(now)), key=lambda e: e.end or datetime.max)
        upcoming = sorted((e for e in events if e.is_upcoming(now)), key=lambda e: e.start)
        events_payload[game_id] = {
            "current": [_event_dict(e) for e in current],
            "upcoming": [_event_dict(e) for e in upcoming],
        }

        banners = [e for e in current + upcoming if e.category == "banner"]
        for key, verdict in build_consensus_for_game(game_id, banners).items():
            consensus_payload[f"{game_id}:{key}"] = {
                "label": verdict.consensus_label,
                "score": verdict.consensus_score,
                "sources": [
                    {
                        "name": s.source_name,
                        "url": s.url,
                        "verdict": s.raw_verdict,
                        "analysis": s.analysis,
                        "pros": s.pros,
                        "cons": s.cons,
                    }
                    for s in verdict.sources
                ],
            }
        print(
            f"  {game_id:<14} {len(current)} live / {len(upcoming)} upcoming"
            f" / {len(banners)} banners analysed"
        )

    (WEB_DATA / "events.json").write_text(
        json.dumps({"generated_at": _now(), "games": events_payload}, indent=1), encoding="utf-8"
    )
    (WEB_DATA / "consensus.json").write_text(
        json.dumps({"generated_at": _now(), "verdicts": consensus_payload}, indent=1),
        encoding="utf-8",
    )


def main(refresh: bool = True) -> None:
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    print("Building web payload...")
    _copy_game_icons()
    write_games()
    write_events_and_consensus(refresh)
    print("Done ->", WEB)


if __name__ == "__main__":
    import sys

    main(refresh="--no-refresh" not in sys.argv)
