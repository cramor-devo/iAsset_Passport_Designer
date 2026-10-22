"""Kleurpaletten van de mockup (donker = zoals het iAsset-paspoort, licht = alternatief).
Mockup colour palettes (dark = like the iAsset passport, light = alternative)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    window: str
    frame: str
    title_bar: str
    body: str
    header_band: str
    input_bg: str
    text: str
    muted: str
    accent: str
    semantic: str
    border: str
    button_bg: str
    panel_bg: str


DARK = Palette(
    name="dark", window="#2b2b2f", frame="#3c3c40", title_bar="#4a4a4f", body="#6b6b6d", header_band="#38383d",
    input_bg="#58585c", text="#ffffff", muted="#c9c9cd", accent="#4da3ff", semantic="#d4c8f2", border="#8a8a8e",
    button_bg="#d9d9dc", panel_bg="#3a3a3f",
)
LIGHT = Palette(
    name="light", window="#eef0f4", frame="#dfe3ea", title_bar="#ffffff", body="#f5f6f8", header_band="#dde2ea",
    input_bg="#ffffff", text="#1d2433", muted="#556070", accent="#1a73e8", semantic="#5b3fa0", border="#c4cad6",
    button_bg="#e8ebf1", panel_bg="#ffffff",
)

PALETTES: dict[str, Palette] = {DARK.name: DARK, LIGHT.name: LIGHT}


def app_stylesheet(p: Palette) -> str:
    """Stijlblad voor het hele programma, passend bij het gekozen thema. / Stylesheet for the whole app."""
    return f"""
    QMainWindow, QDialog, QWidget#central {{ background: {p.window}; }}
    QWidget {{ color: {p.text}; }}
    QListWidget, QPlainTextEdit, QComboBox, QSpinBox, QTabWidget::pane {{
        background: {p.panel_bg}; border: 1px solid {p.border}; border-radius: 4px; }}
    QListWidget::item:selected {{ background: {p.accent}; color: #ffffff; }}
    QPushButton {{ background: {p.button_bg}; color: #1d2433; border: 1px solid {p.border};
        border-radius: 4px; padding: 5px 12px; }}
    QPushButton:focus, QComboBox:focus, QListWidget:focus, QPlainTextEdit:focus {{ border: 2px solid {p.accent}; }}
    QTabBar::tab {{ padding: 6px 14px; }}
    QTabBar::tab:selected {{ border-bottom: 2px solid {p.accent}; }}
    QMenu {{ background: {p.panel_bg}; }}
    QMenu::item:selected {{ background: {p.accent}; color: #ffffff; }}
    """
