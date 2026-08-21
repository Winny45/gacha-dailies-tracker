"""Shared HTTP helpers for per-game scrapers."""
from __future__ import annotations

import json
import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "GachaDailiesTracker/1.0 (personal use, non-commercial)"
)

TIMEOUT_SECONDS = 15


def fetch_html(url: str) -> BeautifulSoup | None:
    """GETs a URL and returns a parsed soup, or None on any failure.
    Scrapers should never raise -- one dead source shouldn't break a refresh."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("fetch failed for %s: %s", url, exc)
        return None
    return BeautifulSoup(resp.text, "lxml")


def fetch_json(url: str) -> dict | list | None:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("fetch_json failed for %s: %s", url, exc)
        return None


def normalize_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def fuzzy_match_name(title: str, index: dict[str, "T"]):  # type: ignore[name-defined]
    """Token-overlap match against a name->value index, requiring the last
    token (surname) to match -- these are often long compound titles across
    fantasy-game wikis/tier lists, and different sites abbreviate them
    differently, so exact-string matching misses too much while a bare
    substring check risks matching the wrong character in the same series.
    Returns None if nothing scores >= 0.5 overlap."""
    title_tokens = normalize_name(title).split()
    if not title_tokens:
        return None
    title_set = set(title_tokens)
    best_val, best_score = None, 0.0
    for name, val in index.items():
        name_tokens = name.split()
        if not name_tokens or name_tokens[-1] != title_tokens[-1]:
            continue
        name_set = set(name_tokens)
        score = len(title_set & name_set) / max(len(title_set), len(name_set))
        if score > best_score:
            best_score, best_val = score, val
    return best_val if best_score >= 0.5 else None


def token_set_match(title: str, index: dict[str, "T"], threshold: float = 0.75):  # type: ignore[name-defined]
    """Order-insensitive match on token overlap. Use when two sites list the
    same thing with the words rearranged -- Brown Dust 2 sources write
    "Sunny Inn Hand Helena" (costume first) where the banner tracker writes
    "Helena -- Sunny Inn Hand" (character first), so the surname anchoring
    in fuzzy_match_name never fires."""
    title_set = set(normalize_name(title).split())
    if not title_set:
        return None
    best_val, best_score = None, 0.0
    for name, val in index.items():
        name_set = set(name.split())
        if not name_set:
            continue
        score = len(title_set & name_set) / max(len(title_set), len(name_set))
        if score > best_score:
            best_score, best_val = score, val
    return best_val if best_score >= threshold else None


def longest_contained_match(title: str, index: dict[str, "T"]):  # type: ignore[name-defined]
    """Finds the longest index key that appears as a whole-word substring of
    `title`. Use this (rather than fuzzy_match_name) when the banner title
    wraps the character name in extra words the other site doesn't use --
    e.g. NIKKE's "Persona Collab: Queen (Makoto Nijima)" vs Prydwen's
    "Queen (Makoto)". Longest wins so "Anis: Star" beats a bare "Anis"."""
    norm_title = normalize_name(title)
    best_val, best_len = None, 0
    for name, val in index.items():
        if len(name) <= best_len:
            continue
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", norm_title):
            best_val, best_len = val, len(name)
    return best_val


PRYDWEN_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,(".*")\]\)', re.S)


def prydwen_payload(soup) -> str:
    """Prydwen is a Next.js app-router site: page data arrives as escaped
    JSON string chunks inside `self.__next_f.push([1,"..."])` script tags
    rather than in the server-rendered DOM. Concatenating the decoded chunks
    reconstructs the full payload."""
    chunks = []
    for script in soup.find_all("script"):
        text = script.get_text() or ""
        match = PRYDWEN_PUSH_RE.search(text)
        if not match:
            continue
        try:
            chunks.append(json.loads(match.group(1)))
        except ValueError:
            continue
    return "".join(chunks)


def extract_json_array(payload: str, key: str):
    """Pulls the JSON array assigned to `"<key>":` out of a larger blob by
    bracket-matching (the payload as a whole isn't valid JSON)."""
    i = payload.find(f'"{key}":')
    if i < 0:
        return None
    try:
        start = payload.index("[", i)
    except ValueError:
        return None
    depth = 0
    for j in range(start, len(payload)):
        if payload[j] == "[":
            depth += 1
        elif payload[j] == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(payload[start : j + 1])
                except ValueError:
                    return None
    return None


def parse_pockettactics_tiers(url: str) -> dict[str, str]:
    """Parses pockettactics.com's tier-list table format, used across
    several of their game tier-list pages: <table><tr><td>Tier</td>
    <td>comma, separated, names</td></tr>...</table>. Returns
    normalize_name(character) -> tier label (e.g. 'SS', 'A')."""
    soup = fetch_html(url)
    if soup is None:
        return {}
    index: dict[str, str] = {}
    for table in soup.select("table"):
        for row in table.select("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            tier = cells[0].get_text(strip=True)
            names = cells[1].get_text(",", strip=True)
            for name in names.split(","):
                name = name.strip()
                if name:
                    index[normalize_name(name)] = tier
    return index
