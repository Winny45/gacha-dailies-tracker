"""Disk cache for character portraits / banner art referenced by Event.image_url.

Downloading happens during the background refresh (see prefetch()) so the UI
thread only ever does fast local disk reads when building widgets -- it never
blocks on network while rendering a tab.
"""
from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "user_data" / "image_cache"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "GachaDailiesTracker/1.0 (personal use, non-commercial)"
    )
}


def _cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    suffix = Path(url.split("?")[0]).suffix
    if suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        suffix = ".img"
    return CACHE_DIR / f"{digest}{suffix}"


def local_path(url: str) -> Path | None:
    """Returns the cached file's path if it's already been downloaded."""
    if not url:
        return None
    path = _cache_path(url)
    return path if path.exists() else None


def _download_one(url: str) -> None:
    path = _cache_path(url)
    if path.exists():
        return
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    except requests.RequestException as exc:
        logger.warning("image prefetch failed for %s: %s", url, exc)


def prefetch(urls: set[str], max_workers: int = 12) -> None:
    """Downloads any URLs not already cached, in parallel. Call from a
    background thread -- with hundreds of banner images this would take
    minutes done one at a time."""
    urls = {u for u in urls if u}
    if not urls:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(_download_one, urls))
