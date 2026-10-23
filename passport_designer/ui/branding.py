"""Stelt het schaalbare applicatie-icoon en de Windows-taakbalkidentiteit in.
Configures the scalable application icon and Windows taskbar identity."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

APP_ICON_FILE = Path(__file__).resolve().parents[1] / "assets" / "iasset-passport-designer.svg"
WINDOWS_APP_ID = "cramor-devo.iAssetPassportDesigner"


def set_windows_app_id() -> None:
    """Geeft Windows een vaste identiteit zodat de taakbalk ons icoon toont.
    Gives Windows a stable identity so the taskbar shows our icon."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
    except (AttributeError, OSError):
        pass


def application_icon() -> QIcon:
    """Laadt het applicatie-icoon. / Loads the application icon."""
    if not APP_ICON_FILE.is_file():
        raise FileNotFoundError(f"Application icon is missing: {APP_ICON_FILE}")
    return QIcon(str(APP_ICON_FILE))


def configure_application_icon(app: QApplication) -> None:
    """Laat alle vensters en dialogen hetzelfde icoon erven.
    Makes all windows and dialogs inherit the same icon."""
    app.setWindowIcon(application_icon())
