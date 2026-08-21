"""Local cache of computed multi-source consensus verdicts, keyed by
'{game_id}:{normalized_character_name}'. Populated only when the user
clicks "Refresh Analysis" in the Banner Guide -- persists across restarts
until the next explicit refresh."""
from __future__ import annotations

import json
from pathlib import Path

from scrapers.consensus import ConsensusVerdict

CACHE_PATH = Path(__file__).resolve().parent.parent / "user_data" / "consensus_cache.json"


def load_consensus() -> dict[str, ConsensusVerdict]:
    if not CACHE_PATH.exists():
        return {}
    try:
        raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {key: ConsensusVerdict.from_dict(d) for key, d in raw.items()}


def save_consensus(verdicts: dict[str, ConsensusVerdict]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = {key: v.to_dict() for key, v in verdicts.items()}
    CACHE_PATH.write_text(json.dumps(raw, indent=2), encoding="utf-8")


def update_game_consensus(game_id: str, new_verdicts: dict[str, ConsensusVerdict]) -> dict[str, ConsensusVerdict]:
    """Merges in new_verdicts (all for one game) without touching other games' cached entries."""
    all_verdicts = load_consensus()
    all_verdicts = {k: v for k, v in all_verdicts.items() if v.game_id != game_id}
    for key, verdict in new_verdicts.items():
        all_verdicts[f"{game_id}:{key}"] = verdict
    save_consensus(all_verdicts)
    return all_verdicts
