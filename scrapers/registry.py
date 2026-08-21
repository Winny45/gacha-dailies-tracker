"""Runs all per-game scrapers and merges results into the local cache.
Each scraper is isolated -- one throwing or timing out doesn't block the rest."""
from __future__ import annotations

import logging

from data.events_cache import load_events, save_events
from data.image_cache import prefetch as prefetch_images
from data.schema import Event
from scrapers import blue_archive, brown_dust_2, limbus, nikke

logger = logging.getLogger(__name__)

SCRAPERS: dict[str, callable] = {
    "limbus": limbus.scrape,
    "blue_archive": blue_archive.scrape,
    "nikke": nikke.scrape,
    "brown_dust_2": brown_dust_2.scrape,
}


def refresh_game(game_id: str) -> list[Event]:
    scraper = SCRAPERS.get(game_id)
    if scraper is None:
        return []
    try:
        return scraper()
    except Exception:
        logger.exception("scraper for %s crashed", game_id)
        return []


def refresh_all(game_ids: list[str] | None = None) -> dict[str, list[Event]]:
    cache = load_events()
    targets = game_ids or list(SCRAPERS.keys())
    for game_id in targets:
        fresh = refresh_game(game_id)
        if fresh:
            cache[game_id] = fresh
    save_events(cache)
    image_urls = {e.image_url for events in cache.values() for e in events if e.image_url}
    prefetch_images(image_urls)
    return cache
