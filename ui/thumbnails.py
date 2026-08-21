from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from data.image_cache import local_path

ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


def load_thumbnail(image_url: str, game_id: str = "", size: int = 48) -> QPixmap | None:
    """Reads an already-downloaded image from the local cache and scales it.
    No network calls happen here -- see data/image_cache.prefetch for that.

    If there's no URL, or it hasn't been cached yet, falls back to that
    game's icon (so banners/events never show a blank box) -- pass
    `game_id` to enable that. Returns None only if even the fallback icon
    is missing."""
    path = local_path(image_url)
    if path is None and game_id:
        fallback = ICONS_DIR / f"{game_id}.png"
        if fallback.exists():
            path = fallback
    if path is None:
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
