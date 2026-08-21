"""NIKKE events/banners scraper.

Source: https://hostedgg.com/wiki/nikke/banners -- a "Current Banners" /
"Upcoming Banners" card list. Each banner is a `div` whose class list
contains "group/card", with the banner name in an `h3`, a start date
(format YYYY-MM-DD) in a small badge near the top, and a "Should you pull?"
paragraph with a human-written pull verdict -- captured as `analysis`.
Most banners don't list an official end date, so `end` is frequently None.

hostedgg has no character portraits, so those are backfilled from
https://www.prydwen.gg/nikke/characters, which has a full roster with
predictable image URLs and alt text we can fuzzy-match against banner
titles (which often carry a collab/event prefix the character list doesn't).

nikke.gg/events/ was also researched but turned out to be a blog-post index
(event write-ups), not a structured banner/date calendar, so it's not used.
"""
from __future__ import annotations

import re

from dateutil import parser as dateparser

from data.schema import Event
from scrapers.base import fetch_html, longest_contained_match, normalize_name

BANNERS_URL = "https://hostedgg.com/wiki/nikke/banners"
CHARACTERS_URL = "https://www.prydwen.gg/nikke/characters"

GAME_ID = "nikke"

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _try_parse(text: str):
    text = text.strip()
    if not text:
        return None
    try:
        return dateparser.parse(text, fuzzy=True)
    except (ValueError, OverflowError):
        return None


def _build_character_image_index() -> dict[str, str]:
    soup = fetch_html(CHARACTERS_URL)
    if soup is None:
        return {}
    index: dict[str, str] = {}
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        alt = img.get("alt", "")
        if "/characters/" not in src or not alt:
            continue
        normalized = normalize_name(alt)
        if normalized:
            index[normalized] = src
    return index


def _extract_analysis(card) -> str:
    label = card.find(string=lambda s: s and s.strip() == "Should you pull?")
    if label is None:
        return ""
    p = label.find_parent("p")
    if p is None:
        return ""
    text = p.get_text(" ", strip=True)
    return text.replace("Should you pull?", "", 1).strip()


def _scrape_banners(image_index: dict[str, str]) -> list[Event]:
    soup = fetch_html(BANNERS_URL)
    if soup is None:
        return []
    events: list[Event] = []
    cards = [d for d in soup.find_all("div") if d.get("class") and "group/card" in d.get("class")]
    for card in cards:
        h3 = card.find("h3")
        title = h3.get_text(strip=True) if h3 else None
        if not title:
            continue
        date_text = card.find(string=_DATE_RE)
        match = _DATE_RE.search(date_text) if date_text else None
        start_text = match.group(0) if match else ""

        image_url = longest_contained_match(title, image_index) or ""
        analysis = _extract_analysis(card)

        events.append(
            Event(
                game_id=GAME_ID,
                title=title,
                category="banner",
                start=_try_parse(start_text),
                end=None,
                source_url=BANNERS_URL,
                source_name="hostedgg.com",
                raw_date_text=f"Starts {start_text}" if start_text else "no date published",
                image_url=image_url,
                analysis=analysis,
            )
        )
    return events


def scrape() -> list[Event]:
    image_index = _build_character_image_index()
    return _scrape_banners(image_index)
