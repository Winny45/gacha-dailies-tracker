"""Blue Archive events/banners scraper.

Sources:
- https://bluearchive.wiki/wiki/Banner_List_(Global) -- rows tagged
  `data-server="gl"` (Global) or `"jp"` (Japan; skipped). Each row has a
  `td.image` with a banner art `<img>` (protocol-relative src, needs
  "https:" prepended), a character-name `<a>`, and a period cell using an
  em dash separator ("2026/09/01 11:00 — 2026/09/08 10:59") -- NOT a
  hyphen or en dash, which is why earlier regex versions matched nothing.
  Rows are also tagged `data-type`; "select*" types (selectpickupgacha,
  selectpickuplimitedgacha, selectpickupfesgacha) are the standard
  recruitment pool where you choose 1 of 10+ students -- not a real
  character banner, so those are filtered out.
- https://bluearchive.wiki/wiki/Events -- tabbed JP/Global tables with
  Name (EN) / Name (JP) / Start date / End date / Notes. No image column.
- https://www.game.guide/blue-archive-tier-list -- per-student write-ups:
  `<p class="has-medium-font-size"><strong>Name</strong></p>` followed by a
  `<figure>` then a `<p>` with the pros/cons blurb.
- https://www.pocketgamer.com/blue-archive/tier-list/ -- a `<table>` with
  tier-header rows ("S-Tier", "A-Tier", ...) followed by
  `<tr><td>Student</td><td>Position</td><td>Class</td></tr>` data rows.

`_scrape_analysis()`/`_scrape_tiers()` below are NOT called by scrape() --
this module only ever attributes verdict/analysis to their real source, and
bluearchive.wiki itself has neither. They're kept here (rather than moved
out) because the fetch/parse logic and normalized names belong with the URLs
they're parsing; scrapers/consensus.py imports and calls them directly to
build correctly-attributed source opinions for the Banner Guide.
"""
from __future__ import annotations

import re

from dateutil import parser as dateparser

from data.schema import Event
from scrapers.base import fetch_html

BANNERS_URL = "https://bluearchive.wiki/wiki/Banner_List_(Global)"
EVENTS_URL = "https://bluearchive.wiki/wiki/Events"
ANALYSIS_URL = "https://www.game.guide/blue-archive-tier-list"
TIER_URL = "https://www.pocketgamer.com/blue-archive/tier-list/"

GAME_ID = "blue_archive"

# "select*" gacha types are the 10+ character recruitment pool, not a banner
_EXCLUDED_TYPES = {"selectpickupgacha", "selectpickuplimitedgacha", "selectpickupfesgacha"}

# hyphen, en dash, em dash -- sites are inconsistent about which they use
_SLASH_RANGE_RE = re.compile(
    r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})\s*[-–—]\s*(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})"
)


def _try_parse(text: str):
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
        return "https://bluearchive.wiki" + src
    return src


def _normalize(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _base_name(title: str) -> str:
    """'Sumire (Part-Timer) rerun' -> 'sumire' -- tier-list sites usually
    grade the base student, not each costume variant."""
    title = re.sub(r"\b(rerun|new)\b", "", title, flags=re.IGNORECASE)
    title = title.split("(")[0]
    return _normalize(title)


def _scrape_analysis() -> dict[str, str]:
    soup = fetch_html(ANALYSIS_URL)
    if soup is None:
        return {}
    index: dict[str, str] = {}
    for name_p in soup.select("p.has-medium-font-size"):
        strong = name_p.find("strong")
        if strong is None:
            continue
        name = _normalize(strong.get_text(strip=True))
        if not name:
            continue
        sib = name_p.find_next_sibling()
        while sib is not None and sib.name != "p":
            sib = sib.find_next_sibling()
        if sib is not None:
            index[name] = sib.get_text(" ", strip=True)
    return index


def _scrape_tiers() -> dict[str, str]:
    soup = fetch_html(TIER_URL)
    if soup is None:
        return {}
    index: dict[str, str] = {}
    current_tier = ""
    for table in soup.select("table"):
        for row in table.select("tr"):
            cells = row.find_all("td")
            row_text = row.get_text(strip=True)
            if re.fullmatch(r"[SABCD]-Tier", row_text):
                current_tier = row_text
                continue
            if not cells or not current_tier:
                continue
            name = cells[0].get_text(strip=True)
            if not name or name.lower() == "student":
                continue
            index[_normalize(name)] = current_tier
    return index


def _scrape_banners() -> list[Event]:
    soup = fetch_html(BANNERS_URL)
    if soup is None:
        return []
    events: list[Event] = []
    for row in soup.select("table tr"):
        if row.get("data-server") != "gl":
            continue
        if row.get("data-type") in _EXCLUDED_TYPES:
            continue
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        row_text = row.get_text(" ", strip=True)
        match = _SLASH_RANGE_RE.search(row_text)
        if not match:
            continue

        name_cell = cells[1]
        title = name_cell.get_text(" ", strip=True)
        if not title:
            continue

        image_cell = cells[0]
        img = image_cell.find("img")
        image_url = _resolve_image(img["src"]) if img and img.get("src") else ""

        events.append(
            Event(
                game_id=GAME_ID,
                title=title,
                category="banner",
                start=_try_parse(match.group(1)),
                end=_try_parse(match.group(2)),
                source_url=BANNERS_URL,
                source_name="bluearchive.wiki",
                raw_date_text=match.group(0),
                image_url=image_url,
            )
        )
    return events


def _scrape_events() -> list[Event]:
    soup = fetch_html(EVENTS_URL)
    if soup is None:
        return []
    events: list[Event] = []
    for table in soup.select("table"):
        headers = [th.get_text(strip=True).lower() for th in table.select("tr th")]
        if not headers or not any("start" in h for h in headers):
            continue
        col_index = {name: i for i, name in enumerate(headers)}
        name_col = next((i for h, i in col_index.items() if "name" in h and "jp" not in h), 0)
        start_col = col_index.get("start date", col_index.get("start"))
        end_col = col_index.get("end date", col_index.get("end"))
        for row in table.select("tr")[1:]:
            cells = row.find_all("td")
            if not cells or len(cells) <= max(name_col, start_col or 0):
                continue
            title = cells[name_col].get_text(strip=True)
            if not title:
                continue
            start_text = cells[start_col].get_text(" ", strip=True) if start_col is not None and start_col < len(cells) else ""
            end_text = cells[end_col].get_text(" ", strip=True) if end_col is not None and end_col < len(cells) else ""
            events.append(
                Event(
                    game_id=GAME_ID,
                    title=title,
                    category="event",
                    start=_try_parse(start_text),
                    end=_try_parse(end_text),
                    source_url=EVENTS_URL,
                    source_name="bluearchive.wiki",
                    raw_date_text=f"{start_text} - {end_text}".strip(" -"),
                )
            )
    return events


def scrape() -> list[Event]:
    return _scrape_banners() + _scrape_events()
