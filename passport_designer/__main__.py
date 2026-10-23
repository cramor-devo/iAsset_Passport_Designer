"""Startpunt: python -m passport_designer. / Entry point: python -m passport_designer."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from . import APP_NAME
from .settings import setup_logging
from .ui.branding import configure_application_icon, set_windows_app_id
from .ui.main_window import MainWindow


def main() -> int:
    setup_logging()
    set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    configure_application_icon(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
