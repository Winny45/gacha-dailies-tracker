"""Limbus Company events/banners scraper.

Sources (see research notes):
- https://limbuscompany.wiki.gg/wiki/Events -- story/timed events, real <table>s
  with columns Image / Name / Start / End.
- https://limbuscompany.wiki.gg/wiki/Extraction/Banner_History -- 17 tables
  (class "lcbtable2", one per season), each row a `<tr>` with a `th[scope=row]`
  holding the banner art + "YYYY.M.D HH:MM - YYYY.M.D HH:MM" date text (month/day
  are NOT always zero-padded, e.g. "2025.4.30"), and a `td` holding the
  Identity/EGO portrait + name.
TIER_URL (https://www.pockettactics.com/limbus-company/tier-list) is not
fetched here -- pull verdicts are handled entirely by
scrapers/consensus.py, which parses that page with
scrapers.base.parse_pockettactics_tiers() and attributes it correctly to
Pocket Tactics rather than to this wiki.
"""
from __future__ import annotations

import re
from datetime import datetime

from dateutil import parser as dateparser

from data.schema import Event
from scrapers.base import fetch_html

EVENTS_URL = "https://limbuscompany.wiki.gg/wiki/Events"
BANNERS_URL = "https://limbuscompany.wiki.gg/wiki/Extraction/Banner_History"
TIER_URL = "https://www.pockettactics.com/limbus-company/tier-list"

GAME_ID = "limbus"


def _try_parse(text: str) -> datetime | None:
    text = text.strip()
    if not text:
        return None
    try:
        return dateparser.parse(text, fuzzy=True)
    except (ValueError, OverflowError):
        return None


def _resolve_image(src: str) -> str:
    if not src:
        return ""
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        return "https://limbuscompany.wiki.gg" + src
    return src


def _scrape_events() -> list[Event]:
    soup = fetch_html(EVENTS_URL)
    if soup is None:
        return []
    events: list[Event] = []
    for table in soup.select("table"):
        headers = [th.get_text(strip=True).lower() for th in table.select("tr th")]
        if not any("name" in h for h in headers) or not any("start" in h for h in headers):
            continue
        col_index = {name: i for i, name in enumerate(headers)}
        image_col = col_index.get("image")
        for row in table.select("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < len(headers):
                continue
            name = cells[col_index.get("name", 0)].get_text(strip=True)
            if not name:
                continue
            start_text = cells[col_index.get("start", -1)].get_text(" ", strip=True) if "start" in col_index else ""
            end_text = cells[col_index.get("end", -1)].get_text(" ", strip=True) if "end" in col_index else ""

            image_url = ""
            if image_col is not None and image_col < len(cells):
                img = cells[image_col].find("img")
                if img and img.get("src"):
                    image_url = _resolve_image(img["src"])

            events.append(
                Event(
                    game_id=GAME_ID,
                    title=name,
                    category="event",
                    start=_try_parse(start_text),
                    end=_try_parse(end_text),
                    source_url=EVENTS_URL,
                    source_name="limbuscompany.wiki.gg",
                    raw_date_text=f"{start_text} - {end_text}".strip(" -"),
                    image_url=image_url,
                )
            )
    return events


_DATE_RANGE_RE = re.compile(
    r"(\d{4}\.\d{1,2}\.\d{1,2}\s+\d{1,2}:\d{2})\s*-\s*(\d{4}\.\d{1,2}\.\d{1,2}\s+\d{1,2}:\d{2})"
)


def _scrape_banners() -> list[Event]:
    soup = fetch_html(BANNERS_URL)
    if soup is None:
        return []
    events: list[Event] = []
    for row in soup.select("table.lcbtable2 tr"):
        date_cell = row.find("th", attrs={"scope": "row"})
        name_cell = row.find("td")
        if date_cell is None or name_cell is None:
            continue
        match = _DATE_RANGE_RE.search(date_cell.get_text(" ", strip=True))
        if not match:
            continue

        name_link = name_cell.find("a", title=True)
        title = name_link.get("title") if name_link else name_cell.get_text(" ", strip=True)
        if not title:
            continue

        portrait_img = name_cell.find("img")
        image_url = _resolve_image(portrait_img["src"]) if portrait_img and portrait_img.get("src") else ""

        events.append(
            Event(
                game_id=GAME_ID,
                title=title,
                category="banner",
                start=_try_parse(match.group(1)),
                end=_try_parse(match.group(2)),
                source_url=BANNERS_URL,
                source_name="limbuscompany.wiki.gg",
                raw_date_text=match.group(0),
                image_url=image_url,
            )
        )
    return events


def scrape() -> list[Event]:
    return _scrape_events() + _scrape_banners()
