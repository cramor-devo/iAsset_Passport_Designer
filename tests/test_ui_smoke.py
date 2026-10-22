"""Rooktest van de UI zonder scherm (offscreen). / Smoke test of the UI without a display (offscreen)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from conftest import make_spec  # noqa: E402
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from passport_designer.i18n import TRANSLATIONS, translator  # noqa: E402
from passport_designer.settings import AppSettings  # noqa: E402
from passport_designer.ui.main_window import MainWindow  # noqa: E402
from passport_designer.ui.theme import DARK, LIGHT  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, wave1_spec, tmp_path):
    settings = AppSettings(QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat))
    settings.set("ui/language", "en")
    win = MainWindow(settings)
    win._on_loaded(wave1_spec, 1, True)
    yield win
    win.close()


def test_loading_fills_filters_and_views(window):
    assert window.filter_list.count() == 2
    assert window.type_combo.count() == 2
    assert "POST /passport-tabs" in window.payload_text.toPlainText()
    assert window.validation_list.count() >= 1


def test_mockup_renders_to_image_in_both_themes(window):
    for palette in (DARK, LIGHT):
        window.mockup.show_tab(window.current_tab(), "APV-bord", palette)
        pixmap = window.mockup.render_pixmap()
        assert not pixmap.isNull() and pixmap.width() >= 1000 and pixmap.height() > 300


def test_language_switch_changes_texts(window):
    window._set_language("nl")
    assert window.filter_label.text() == TRANSLATIONS["panel.filters"]["nl"]
    window._set_language("en")
    assert window.filter_label.text() == TRANSLATIONS["panel.filters"]["en"]


def test_merge_suggestions_apply_and_reset_in_ui(window):
    window._on_loaded(make_spec(), 1, True)
    window.threshold_spin.setValue(60)
    assert window.merge_tree.topLevelItemCount() == len(window.suggestions) == 1
    base_count = window.filter_list.count()
    window.merge_tree.setCurrentItem(window.merge_tree.topLevelItem(0))
    window.preview_merge()
    assert window.current_tab() is window.suggestions[0].tab
    window.apply_selected_merge()
    assert window.filter_list.count() == base_count - 1
    assert window.filter_list.item(0).text().endswith("⧉")
    assert window.merge_tree.topLevelItemCount() == 0
    window.reset_merges()
    assert window.filter_list.count() == base_count
    assert window.merge_tree.topLevelItemCount() == 1


def test_every_translation_has_both_languages():
    for key, entry in TRANSLATIONS.items():
        assert entry.get("en") and entry.get("nl"), key


def test_filter_and_object_type_switch_updates_payload(window):
    window.filter_list.setCurrentRow(1)
    assert "Verharding" in window.payload_text.toPlainText()
    assert window.type_combo.currentText() == "Asfaltverharding"
    translator.set_language("en")
