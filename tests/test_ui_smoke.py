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
    assert window.type_combo.count() == 3  # "All object types" + 2 object types
    assert window.type_combo.itemText(0) == "All object types"
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
    assert window.type_combo.currentText() == "All object types"
    assert window.type_combo.itemText(1) == "Asfaltverharding"
    translator.set_language("en")


def test_filter_column_selector_regroups_passports(window, wave2_file):
    from passport_designer.spec_reader import read_spec

    window._on_loaded(read_spec(wave2_file), 1, True)
    assert [window.column_combo.itemText(i) for i in range(window.column_combo.count())][:3] == [
        "Organisatie", "Filter", "Systeem",
    ]
    assert window.column_combo.currentText() == "Filter"
    assert [t.name for t in window.tabs] == ["RD-Obsurv", "RD-Ultimo"]
    window.column_combo.setCurrentText("Fase")
    assert [t.name for t in window.tabs] == ["Put", "Stuw"]
    assert window.settings.string("design/filter_column", "") == "Fase"
    window._on_loaded(read_spec(wave2_file), 1, True)  # keuze blijft bewaard / choice is remembered
    assert [t.name for t in window.tabs] == ["Put", "Stuw"]


def sheet_texts(window) -> set[str]:
    sheet = window.sheet_preview
    return {sheet.text_at(r, c) for r in range(1, sheet.rowCount() + 1) for c in range(1, sheet.columnCount() + 1)}


def test_single_object_type_hides_unassigned_fields(window):
    window.filter_list.setCurrentRow(0)  # Bord: APV-bord + Verkeersbord
    sheet = window.sheet_preview
    assert any(t.startswith("APV-verordening (") for t in sheet_texts(window))
    window.type_combo.setCurrentText("Verkeersbord")
    assert not any(t.startswith("APV-verordening") for t in sheet_texts(window))
    assert sheet.text_at(1, 1) == "Bord" and sheet.text_at(2, 1) == "Objecttypes: Verkeersbord"
    window.type_combo.setCurrentText("APV-bord")
    assert "APV-verordening" in sheet_texts(window)  # geen voetnoot meer / no footnote any more


def test_application_icon_renders(app):
    from passport_designer.ui.branding import application_icon

    assert not application_icon().pixmap(32, 32).isNull()
