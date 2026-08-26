"""QApplication bootstrap.

HiDPI, font, and theme are all initialised here. The ``run`` entry point
is the only thing ``__main__`` calls.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from srtforge import __app_name__, __org_name__
from srtforge.config.settings import SettingsStore
from srtforge.ui.main_window import MainWindow
from srtforge.ui.theme import apply_theme


def _configure_application(app: QApplication, settings: SettingsStore) -> None:
    app.setApplicationName(__app_name__)
    app.setOrganizationName(__org_name__)
    app.setApplicationDisplayName(__app_name__)

    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

    font = QFont()
    font.setPointSize(10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)

    apply_theme(app, settings.data.theme)


def run(argv: list[str]) -> int:
    app = QApplication(argv)
    settings = SettingsStore.load()
    _configure_application(app, settings)

    window = MainWindow(settings)
    window.show()
    return app.exec()
