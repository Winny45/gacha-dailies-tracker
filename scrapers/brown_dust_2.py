"""Brown Dust 2 events/banners scraper.

Source: Gamependium banner tracker -- plain server-rendered HTML tables.
Each banner row has `td.dates` containing two `<time datetime="...">` tags
(machine-readable, far more reliable than parsing the visible text), and
`td.costume` holding the costume name plus the character name in a `<strong>`.
The same row also carries a ready-made pull verdict: `td.draw` holds a short
label ("Recommended"/"Skip"/etc.) and `td.summary` holds the pros/cons
writeup -- captured as `verdict`/`analysis` respectively, no separate
tier-list source needed for this game.

The official site's news/events page is client-rendered React and can't be
scraped with plain requests, so it's skipped here.
"""
from __future__ import annotations

from urllib.parse import urljoin

from dateutil import parser as dateparser

from data.schema import Event
from scrapers.base import fetch_html

BANNERS_URL = "http://cymmina.gamependium.com/browndust2/banners.html"

GAME_ID = "brown_dust_2"


def _try_parse(text: str):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return dateparser.parse(text, fuzzy=True)
    except (ValueError, OverflowError):
        return None


def _scrape_banners() -> list[Event]:
    soup = fetch_html(BANNERS_URL)
    if soup is None:
        return []
    events: list[Event] = []
    for row in soup.select("tr"):
        dates_cell = row.find("td", class_="dates")
        costume_cell = row.find("td", class_="costume")
        portrait_cell = row.find("td", class_="portrait")
        draw_cell = row.find("td", class_="draw")
        summary_cell = row.find("td", class_="summary")
        if dates_cell is None or costume_cell is None:
            continue
        times = dates_cell.find_all("time")
        if not times:
            continue
        start_attr = times[0].get("datetime", times[0].get_text(strip=True))
        end_attr = times[1].get("datetime", times[1].get_text(strip=True)) if len(times) > 1 else ""

        character = costume_cell.find("strong")
        costume_name = costume_cell.contents[0].get_text(strip=True) if costume_cell.contents and hasattr(costume_cell.contents[0], "get_text") else costume_cell.get_text(" ", strip=True)
        title = f"{character.get_text(strip=True)} -- {costume_name}" if character else costume_cell.get_text(" ", strip=True)

        image_url = ""
        if portrait_cell is not None:
            img = portrait_cell.find("img")
            if img and img.get("src"):
                image_url = urljoin(BANNERS_URL, img["src"])

        verdict = draw_cell.get_text(strip=True) if draw_cell else ""
        analysis = summary_cell.get_text(" ", strip=True) if summary_cell else ""

        events.append(
            Event(
                game_id=GAME_ID,
                title=title.strip(),
                category="banner",
                start=_try_parse(start_attr),
                end=_try_parse(end_attr),
                source_url=BANNERS_URL,
                source_name="gamependium.com",
                raw_date_text=dates_cell.get_text(" ", strip=True),
                image_url=image_url,
                verdict=verdict,
                analysis=analysis,
            )
        )
    return events


def scrape() -> list[Event]:
    return _scrape_banners()
