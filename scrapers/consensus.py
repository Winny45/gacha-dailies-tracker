"""Multi-source pull-verdict consensus.

This is deliberately separate from the main events/banners refresh
(scrapers/registry.py): it fetches extra tier-list pages per game that
aren't needed for the regular checklist/date view, so it only runs when the
user explicitly asks for it via the Banner Guide's "Refresh Analysis"
button -- not on every lightweight date/event refresh.

There's no AI/LLM involved. For each current/upcoming banner character,
this pulls from 1-3 independent community sources per game, normalizes
every source's tier/verdict onto a common 0-5 scale, and averages them into
a single consensus label. Sources that don't map to a known tier still show
up with their raw text, they just don't count toward the numeric average.

Every SourceOpinion is attributed to where the verdict/analysis actually
came from -- NOT to the wiki a banner's dates/image were scraped from,
which is a different site for Blue Archive and Limbus Company.

Prydwen is used for NIKKE and Limbus Company (the only two of the four it
covers -- it has no Blue Archive or Brown Dust 2 section). Its two pages
need different techniques: the NIKKE tier list is server-rendered HTML,
while the Limbus one is client-rendered and its data has to be lifted out
of the Next.js flight payload instead. See prydwen_nikke_tiers() and
prydwen_limbus_ratings() below.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from data.schema import Event
from scrapers import blue_archive, limbus
from scrapers.base import (
    extract_json_array,
    fetch_html,
    fetch_json,
    fuzzy_match_name,
    longest_contained_match,
    normalize_name,
    parse_pockettactics_tiers,
    prydwen_payload,
    token_set_match,
)

_TIER_SCORES = {
    "SS": 5.0, "SS-TIER": 5.0,
    "S": 4.5, "S-TIER": 4.5,
    "A": 4.0, "A-TIER": 4.0,
    "B": 3.0, "B-TIER": 3.0,
    "C": 2.0, "C-TIER": 2.0,
    "D": 1.0, "D-TIER": 1.0,
    "F": 0.0, "F-TIER": 0.0,
    "RECOMMENDED": 4.5,
    "SKIP": 1.0,
}


# Prydwen's NIKKE tier list runs SSS..F (a wider spread than the SS..D
# scales the other sites use), so it gets its own mapping rather than being
# squeezed into _TIER_SCORES.
_PRYDWEN_TIER_SCORES = {
    "sss": 5.0,
    "ss": 4.7,
    "s": 4.4,
    "a": 3.9,
    "b": 3.1,
    "c": 2.3,
    "d": 1.5,
    "e": 0.8,
    "f": 0.0,
}


def score_for(verdict_text: str) -> float | None:
    return _TIER_SCORES.get(verdict_text.strip().upper())


def label_for(score: float) -> str:
    if score >= 4.3:
        return "Strong Pull"
    if score >= 3.4:
        return "Good Pull"
    if score >= 2.3:
        return "Situational"
    return "Low Priority / Skip"


@dataclass
class SourceOpinion:
    source_name: str
    url: str
    raw_verdict: str
    analysis: str
    score: float | None
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "url": self.url,
            "raw_verdict": self.raw_verdict,
            "analysis": self.analysis,
            "score": self.score,
            "pros": self.pros,
            "cons": self.cons,
        }

    @staticmethod
    def from_dict(d: dict) -> "SourceOpinion":
        # tolerate caches written before pros/cons existed rather than
        # blowing up on a missing key
        return SourceOpinion(
            source_name=d.get("source_name", ""),
            url=d.get("url", ""),
            raw_verdict=d.get("raw_verdict", ""),
            analysis=d.get("analysis", ""),
            score=d.get("score"),
            pros=d.get("pros") or [],
            cons=d.get("cons") or [],
        )


@dataclass
class ConsensusVerdict:
    game_id: str
    character_key: str
    display_name: str
    sources: list[SourceOpinion]
    consensus_label: str
    consensus_score: float | None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "character_key": self.character_key,
            "display_name": self.display_name,
            "sources": [s.to_dict() for s in self.sources],
            "consensus_label": self.consensus_label,
            "consensus_score": self.consensus_score,
            "fetched_at": self.fetched_at.isoformat(),
        }

    @staticmethod
    def from_dict(d: dict) -> "ConsensusVerdict":
        return ConsensusVerdict(
            game_id=d["game_id"],
            character_key=d["character_key"],
            display_name=d["display_name"],
            sources=[SourceOpinion.from_dict(s) for s in d["sources"]],
            consensus_label=d["consensus_label"],
            consensus_score=d.get("consensus_score"),
            fetched_at=datetime.fromisoformat(d["fetched_at"]),
        )


def _compute(sources: list[SourceOpinion]) -> tuple[str, float | None]:
    scores = [s.score for s in sources if s.score is not None]
    if not scores:
        return ("No consensus data", None)
    avg = sum(scores) / len(scores)
    return (label_for(avg), avg)


# ---------------------------------------------------------------------------
# Per-game source gathering. Each returns list[SourceOpinion] for one banner
# title, pulling from that game's known-good tier-list/review sites.
# ---------------------------------------------------------------------------

NIKKE_TIER_URL = "https://www.pockettactics.com/nikke/tier-list"
BLUE_ARCHIVE_TIER_URL = "https://www.pockettactics.com/blue-archive/tier-list"
BROWN_DUST_2_TIER_URL = "https://www.pocketgamer.com/brown-dust-2/tier-list/"
PRYDWEN_NIKKE_URL = "https://www.prydwen.gg/nikke/tier-list"
PRYDWEN_LIMBUS_URL = "https://www.prydwen.gg/limbus-company/tier-list"


def prydwen_nikke_tiers() -> dict[str, str]:
    """Prydwen's NIKKE tier list IS server-rendered: each tier is a
    `div.custom-tier` carrying a `tier-<letter>` class, holding
    `div.avatar-card`s whose `<img alt>` is the character name.
    Returns normalize_name(character) -> tier letter."""
    soup = fetch_html(PRYDWEN_NIKKE_URL)
    if soup is None:
        return {}
    index: dict[str, str] = {}
    for tier_div in soup.select("div.custom-tier"):
        classes = tier_div.get("class") or []
        tier = next((c[len("tier-"):] for c in classes if c.startswith("tier-")), "")
        if not tier:
            continue
        for card in tier_div.select("div.avatar-card"):
            img = card.find("img")
            alt = (img.get("alt") or "").strip() if img else ""
            if alt:
                index[normalize_name(alt)] = tier
    return index


def prydwen_limbus_ratings() -> dict[str, str]:
    """Prydwen's Limbus tier list is client-rendered (its tier divs come
    down empty), but the underlying data ships in the Next.js flight
    payload as `allIdentities`, each with a numeric `data.ratings.end`
    score on a 0-10 scale. Returns normalize_name(identity) -> score text."""
    soup = fetch_html(PRYDWEN_LIMBUS_URL)
    if soup is None:
        return {}
    identities = extract_json_array(prydwen_payload(soup), "allIdentities")
    if not identities:
        return {}
    index: dict[str, str] = {}
    for entry in identities:
        name = entry.get("name") or ""
        rating = ((entry.get("data") or {}).get("ratings") or {}).get("end")
        if name and rating:
            index[normalize_name(name)] = str(rating)
    return index


def _prydwen_tier_opinion(tier: str, url: str) -> SourceOpinion:
    return SourceOpinion(
        "Prydwen", url, tier.upper(), "", _PRYDWEN_TIER_SCORES.get(tier.lower())
    )


def _prydwen_rating_opinion(rating: str, url: str) -> SourceOpinion:
    try:
        score = float(rating) / 2.0  # Prydwen rates 0-10; our scale is 0-5
    except ValueError:
        score = None
    return SourceOpinion("Prydwen", url, f"{rating}/10", "", score)


def _nikke_sources(
    title: str,
    event: Event,
    pockettactics_index: dict[str, str],
    prydwen_index: dict[str, str],
) -> list[SourceOpinion]:
    sources = []
    if event.analysis or event.verdict:
        sources.append(SourceOpinion(event.source_name, event.source_url, event.verdict, event.analysis, score_for(event.verdict) if event.verdict else None))
    tier = fuzzy_match_name(title, pockettactics_index)
    if tier:
        sources.append(SourceOpinion("Pocket Tactics", NIKKE_TIER_URL, tier, "", score_for(tier)))
    # NIKKE banner titles wrap the character in collab/event words Prydwen
    # doesn't use, so match by containment rather than surname anchoring
    prydwen_tier = longest_contained_match(title, prydwen_index)
    if prydwen_tier:
        sources.append(_prydwen_tier_opinion(prydwen_tier, PRYDWEN_NIKKE_URL))
    return sources


def _blue_archive_sources(
    title: str,
    tier_index: dict[str, str],
    analysis_index: dict[str, str],
    pockettactics_index: dict[str, str],
) -> list[SourceOpinion]:
    base = blue_archive._base_name(title)
    sources = []
    tier = tier_index.get(base, "")
    if tier:
        sources.append(SourceOpinion("Pocket Gamer", blue_archive.TIER_URL, tier, "", score_for(tier)))
    analysis = analysis_index.get(base, "")
    if analysis:
        sources.append(SourceOpinion("Game.Guide", blue_archive.ANALYSIS_URL, "", analysis, None))
    # use the cleaned base name (no "rerun"/"new" suffix) for the fuzzy
    # match too -- fuzzy_match_name anchors on the last token, and "rerun"
    # isn't part of any character's actual name on the tier-list site
    pt_tier = fuzzy_match_name(base, pockettactics_index)
    if pt_tier:
        sources.append(SourceOpinion("Pocket Tactics", BLUE_ARCHIVE_TIER_URL, pt_tier, "", score_for(pt_tier)))
    return sources


def _limbus_sources(
    title: str,
    pockettactics_index: dict[str, str],
    prydwen_index: dict[str, str],
) -> list[SourceOpinion]:
    sources = []
    tier = fuzzy_match_name(title, pockettactics_index)
    if tier:
        sources.append(SourceOpinion("Pocket Tactics", limbus.TIER_URL, tier, "", score_for(tier)))
    rating = fuzzy_match_name(title, prydwen_index)
    if rating:
        sources.append(_prydwen_rating_opinion(rating, PRYDWEN_LIMBUS_URL))
    return sources


BD2_RECOMMENDATION_URL = "https://zormolo.github.io/BD2-Banner-Recommendation/"
BD2_DATA_JSON = BD2_RECOMMENDATION_URL + "public/json/data.json"
BD2_UTILS_JSON = BD2_RECOMMENDATION_URL + "public/json/utils.json"

# the site's own pullPriority codes, in its own words (utils.json supplies
# the display labels; these are the numeric weights for our 0-5 average)
_BD2_PRIORITY_SCORES = {"ur": 5.0, "sr": 4.0, "r": 2.5, "n": 1.0}
_BD2_PRIORITY_FALLBACK_LABELS = {
    "ur": "Yes (Must)",
    "sr": "Yes (Recommended)",
    "r": "Situational",
    "n": "No (Skip)",
}


def _clean(text: str) -> str:
    """This source stores display HTML in its JSON (e.g. '6 &rarr; 9')."""
    return html.unescape(text or "").strip()


def bd2_recommendation_index() -> dict[str, dict]:
    """The BD2 Banner Recommendation site is client-rendered, but it serves
    its data as a plain JSON file -- far more reliable than scraping. Each
    banner entry carries a pullPriority code, a prose pullReason, explicit
    pros/cons lists, and per-game-mode ratings.

    Returns normalize_name("<charName> <costumeName>") -> entry, keyed to
    match how gamependium titles read ("Helena -- Sunny Inn Hand")."""
    data = fetch_json(BD2_DATA_JSON)
    if not isinstance(data, dict):
        return {}
    banners = data.get("banner")
    if not isinstance(banners, list):
        return {}
    index: dict[str, dict] = {}
    for entry in banners:
        char = (entry.get("charName") or "").strip()
        costume = (entry.get("costumeName") or "").strip()
        if not char or not costume:
            continue
        index[normalize_name(f"{char} {costume}")] = entry
    return index


def bd2_priority_labels() -> dict[str, str]:
    utils = fetch_json(BD2_UTILS_JSON)
    if isinstance(utils, dict):
        labels = utils.get("pullPriority")
        if isinstance(labels, dict) and labels:
            return {k: _clean(v).rstrip(".") for k, v in labels.items()}
    return dict(_BD2_PRIORITY_FALLBACK_LABELS)


def _bd2_recommendation_opinion(entry: dict, labels: dict[str, str]) -> SourceOpinion:
    code = (entry.get("pullPriority") or "").strip().lower()
    verdict = labels.get(code, code.upper())
    reason = _clean(entry.get("pullReason") or "")
    modes = entry.get("modes") or {}
    rated = [f"{k.upper()}: {v}" for k, v in modes.items() if v]
    if rated:
        reason = (reason + "\n\nBy mode -- " + ", ".join(rated)).strip()
    return SourceOpinion(
        source_name="BD2 Banner Recommendation",
        url=BD2_RECOMMENDATION_URL,
        raw_verdict=verdict,
        analysis=reason,
        score=_BD2_PRIORITY_SCORES.get(code),
        pros=[_clean(p) for p in (entry.get("pros") or []) if _clean(p)],
        cons=[_clean(c) for c in (entry.get("cons") or []) if _clean(c)],
    )


def _brown_dust_2_sources(
    title: str,
    event: Event,
    pocketgamer_index: dict[str, tuple[str, str]],
    recommendation_index: dict[str, dict],
    priority_labels: dict[str, str],
) -> list[SourceOpinion]:
    sources = []
    if event.verdict or event.analysis:
        sources.append(SourceOpinion(event.source_name, event.source_url, event.verdict, event.analysis, score_for(event.verdict) if event.verdict else None))
    # BD2 sources put the costume name before the character; the banner
    # tracker puts it after -- so match on token set, not word order
    match = token_set_match(title, pocketgamer_index)
    if match:
        heading, explanation = match
        label, pg_score = parse_pocketgamer_tier(heading)
        sources.append(SourceOpinion("Pocket Gamer", BROWN_DUST_2_TIER_URL, label, explanation, pg_score))
    key = normalize_name(title)
    entry = recommendation_index.get(key) or token_set_match(title, recommendation_index)
    if entry:
        sources.append(_bd2_recommendation_opinion(entry, priority_labels))
    return sources


# Pocket Gamer writes its BD2 tiers as prose headings rather than bare
# letters -- "1S Tier - the Proteges", "3B/C tier - the Commoners and
# Outcasts", "Honourable mention tier/A- tier". Pull the grade back out.
_PG_TIER_RE = re.compile(r"([sabcdf])\s*([+-])?\s*(?:/\s*([sabcdf])\s*([+-])?)?\s*tier", re.I)
_PG_LETTER_SCORES = {"s": 4.5, "a": 4.0, "b": 3.0, "c": 2.0, "d": 1.0, "f": 0.0}


def parse_pocketgamer_tier(heading: str) -> tuple[str, float | None]:
    """Returns (clean label, score). A split grade like "B/C" averages its
    two letters; a "+"/"-" modifier nudges by 0.3."""
    match = _PG_TIER_RE.search(heading or "")
    if not match:
        return (heading.strip(), None)
    grades: list[tuple[str, str]] = [(match.group(1), match.group(2) or "")]
    if match.group(3):
        grades.append((match.group(3), match.group(4) or ""))
    scores = []
    for letter, modifier in grades:
        base = _PG_LETTER_SCORES.get(letter.lower())
        if base is None:
            continue
        scores.append(base + (0.3 if modifier == "+" else -0.3 if modifier == "-" else 0.0))
    label = "/".join(f"{l.upper()}{m}" for l, m in grades) + " Tier"
    return (label, sum(scores) / len(scores) if scores else None)


def _brown_dust_2_pocketgamer_index() -> dict[str, tuple[str, str]]:
    soup = fetch_html(BROWN_DUST_2_TIER_URL)
    if soup is None:
        return {}
    index: dict[str, tuple[str, str]] = {}
    for table in soup.select("table"):
        heading = table.find_previous(["h2", "h3"])
        tier_text = heading.get_text(strip=True) if heading else ""
        for row in table.select("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            name = cells[0].get_text(strip=True)
            explanation = cells[-1].get_text(" ", strip=True)
            if name:
                index[normalize_name(name)] = (tier_text, explanation)
    return index


def build_consensus_for_game(game_id: str, banners: list[Event]) -> dict[str, ConsensusVerdict]:
    """banners should already be filtered to current/upcoming -- there's no
    reason to fetch tier lists for hundreds of expired historical banners."""
    results: dict[str, ConsensusVerdict] = {}

    if game_id == "nikke":
        pt_index = parse_pockettactics_tiers(NIKKE_TIER_URL)
        prydwen_index = prydwen_nikke_tiers()
        for event in banners:
            key = normalize_name(event.title)
            if key in results:
                continue
            sources = _nikke_sources(event.title, event, pt_index, prydwen_index)
            label, score = _compute(sources)
            results[key] = ConsensusVerdict(game_id, key, event.title, sources, label, score)

    elif game_id == "blue_archive":
        tier_index = blue_archive._scrape_tiers()
        analysis_index = blue_archive._scrape_analysis()
        pt_index = parse_pockettactics_tiers(BLUE_ARCHIVE_TIER_URL)
        for event in banners:
            key = normalize_name(event.title)
            if key in results:
                continue
            sources = _blue_archive_sources(event.title, tier_index, analysis_index, pt_index)
            label, score = _compute(sources)
            results[key] = ConsensusVerdict(game_id, key, event.title, sources, label, score)

    elif game_id == "limbus":
        pt_index = parse_pockettactics_tiers(limbus.TIER_URL)
        prydwen_index = prydwen_limbus_ratings()
        for event in banners:
            key = normalize_name(event.title)
            if key in results:
                continue
            sources = _limbus_sources(event.title, pt_index, prydwen_index)
            label, score = _compute(sources)
            results[key] = ConsensusVerdict(game_id, key, event.title, sources, label, score)

    elif game_id == "brown_dust_2":
        pg_index = _brown_dust_2_pocketgamer_index()
        rec_index = bd2_recommendation_index()
        labels = bd2_priority_labels()
        for event in banners:
            key = normalize_name(event.title)
            if key in results:
                continue
            sources = _brown_dust_2_sources(event.title, event, pg_index, rec_index, labels)
            label, score = _compute(sources)
            results[key] = ConsensusVerdict(game_id, key, event.title, sources, label, score)

    return results
