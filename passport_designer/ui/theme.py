"""Kleurpaletten van de mockup (donker = zoals het iAsset-paspoort, licht = alternatief).
Mockup colour palettes (dark = like the iAsset passport, light = alternative)."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QColor, QPalette


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
    separator: str


DARK = Palette(
    name="dark", window="#2b2b2f", frame="#3c3c40", title_bar="#3c3c40", body="#68686a", header_band="#3c3c40",
    input_bg="#4b4b50", text="#ffffff", muted="#d0d0d4", accent="#4da3ff", semantic="#d4c8f2", border="#8a8a8e",
    button_bg="#e4e4e7", panel_bg="#3a3a3f", separator="#8f9094",
)
LIGHT = Palette(
    name="light", window="#eef0f4", frame="#dfe3ea", title_bar="#ffffff", body="#f5f6f8", header_band="#dde2ea",
    input_bg="#ffffff", text="#1d2433", muted="#556070", accent="#1a73e8", semantic="#5b3fa0", border="#c4cad6",
    button_bg="#e8ebf1", panel_bg="#ffffff", separator="#c4cad6",
)

# Kleur per soort verschil in de mockup (zie crossref). / Colour per kind of difference in the mockup.
KIND_COLOURS: dict[str, str] = {
    "added": "#2fa84f", "moved": "#f0a500", "renamed": "#3b82f6", "not-in-spec": "#e5484d", "removed": "#8a8a8e",
}

# Dekking van de minimale-datasettint in de mockup en rode letters voor "controleren met klant".
# Opacity of the minimal dataset tint in the mockup and red text for "verify with customer".
MINIMAL_ALPHA = 0.35
VERIFY_TEXT = "#e5484d"

PALETTES: dict[str, Palette] = {DARK.name: DARK, LIGHT.name: LIGHT}

# Tekstkleur op knoppen (licht, in beide thema's). / Button text colour (light buttons in both themes).
BUTTON_TEXT = "#1d2433"


def qt_palette(p: Palette) -> QPalette:
    """QPalette voor het hele programma, zodat Windows-donkermodus de kleuren niet overschrijft.
    QPalette for the whole app, so Windows dark mode does not override the chosen colours."""
    palette = QPalette()
    colours = {
        QPalette.ColorRole.Window: p.window,
        QPalette.ColorRole.WindowText: p.text,
        QPalette.ColorRole.Base: p.panel_bg,
        QPalette.ColorRole.AlternateBase: p.frame,
        QPalette.ColorRole.Text: p.text,
        QPalette.ColorRole.Button: p.button_bg,
        QPalette.ColorRole.ButtonText: BUTTON_TEXT,
        QPalette.ColorRole.Highlight: p.accent,
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: p.panel_bg,
        QPalette.ColorRole.ToolTipText: p.text,
        QPalette.ColorRole.PlaceholderText: p.muted,
    }
    for role, colour in colours.items():
        palette.setColor(role, QColor(colour))
    return palette


def app_stylesheet(p: Palette) -> str:
    """Stijlblad voor het hele programma, passend bij het gekozen thema. / Stylesheet for the whole app."""
    return f"""
    QMainWindow, QDialog, QWidget#central {{ background: {p.window}; }}
    QWidget {{ color: {p.text}; }}
    QListWidget, QPlainTextEdit, QComboBox, QSpinBox, QTabWidget::pane {{
        background: {p.panel_bg}; border: 1px solid {p.border}; border-radius: 4px; }}
    QListWidget::item:selected {{ background: {p.accent}; color: #ffffff; }}
    QPushButton {{ background: {p.button_bg}; color: {BUTTON_TEXT}; border: 1px solid {p.border};
        border-radius: 4px; padding: 5px 12px; }}
    QPushButton:focus, QComboBox:focus, QListWidget:focus, QPlainTextEdit:focus {{ border: 2px solid {p.accent}; }}
    QTabBar::tab {{ padding: 6px 14px; background: {p.frame}; color: {p.text}; border: 1px solid {p.border}; }}
    QTabBar::tab:hover {{ background: {p.header_band}; }}
    QTabBar::tab:selected {{ background: {p.panel_bg}; border-bottom: 2px solid {p.accent}; }}
    QHeaderView::section {{ background: {p.frame}; color: {p.text}; border: 1px solid {p.border}; padding: 3px; }}
    QTableWidget {{ background: {p.panel_bg}; color: {p.text}; gridline-color: {p.border}; }}
    QMenuBar {{ background: {p.window}; color: {p.text}; }}
    QMenuBar::item:selected {{ background: {p.accent}; color: #ffffff; }}
    QStatusBar {{ background: {p.window}; color: {p.text}; }}
    QScrollBar:vertical, QScrollBar:horizontal {{ background: {p.frame}; }}
    QMenu {{ background: {p.panel_bg}; }}
    QMenu::item:selected {{ background: {p.accent}; color: #ffffff; }}
    """
