"""Entry point: launches the Gacha Dailies Tracker desktop app."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ui import theme
from ui.main_window import MainWindow

APP_ICON = Path(__file__).resolve().parent / "assets" / "icons" / "nikke.png"


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Gacha Dailies Tracker")
    # Fusion gives a consistent base across Windows themes for the
    # stylesheet to build on
    app.setStyle("Fusion")
    app.setStyleSheet(theme.stylesheet())
    if APP_ICON.exists():
        app.setWindowIcon(QIcon(str(APP_ICON)))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
