"""Tests voor het hernoemen van paspoorttabbladen (0.5.1). Alles offline, offscreen.
Tests for renaming passport tabs (0.5.1). Everything offline, offscreen."""

from __future__ import annotations

import os
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from conftest import make_spec  # noqa: E402
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMenu  # noqa: E402

from passport_designer.i18n import TRANSLATIONS  # noqa: E402
from passport_designer.layout_engine import LayoutEngine, LayoutOptions  # noqa: E402
from passport_designer.layout_overrides import TabOverride  # noqa: E402
from passport_designer.renaming import apply_renames, sheet_name_adjusted, validate_rename  # noqa: E402
from passport_designer.settings import AppSettings  # noqa: E402
from passport_designer.ui.main_window import MainWindow  # noqa: E402

# --- zuivere logica / pure logic ---------------------------------------------------------------------------


def test_validate_rename_rejects_empty_name():
    assert validate_rename("  ", "Bord", {"Paal"}) == "merge.name_empty"


def test_validate_rename_rejects_too_long_name():
    assert validate_rename("x" * 51, "Bord", set()) == "merge.name_too_long"


def test_validate_rename_rejects_duplicate_case_insensitive():
    assert validate_rename("paal", "Bord", {"Paal"}) == "merge.name_duplicate"


def test_validate_rename_allows_unchanged_name_and_case_change():
    assert validate_rename("Bord", "Bord", {"Bord", "Paal"}) is None
    assert validate_rename("BORD", "Bord", {"Bord", "Paal"}) is None


def test_sheet_name_adjusted_flags_long_names_and_forbidden_characters():
    assert not sheet_name_adjusted("Borden")
    assert sheet_name_adjusted("x" * 32)
    assert sheet_name_adjusted("Borden/Palen")


def test_apply_renames_renames_only_listed_tabs_and_keeps_original_name():
    spec = make_spec()
    engine = LayoutEngine(spec, LayoutOptions(only_flagged=False))
    base = engine.build_all()
    result = apply_renames(engine, base, {"Bord": "Verkeersborden"})
    assert [t.name for t in result][0] == "Verkeersborden"
    assert result[0].original_name == "Bord"
    assert [t.name for t in result][1:] == [t.name for t in base][1:]
    assert all(not t.original_name for t in result[1:])
    assert [o.name for o in result[0].object_types] == [o.name for o in base[0].object_types]


def test_apply_renames_ignores_unknown_originals_and_merged_tabs():
    spec = make_spec()
    engine = LayoutEngine(spec, LayoutOptions(only_flagged=False))
    base = engine.build_all()
    assert [t.name for t in apply_renames(engine, base, {"Bestaat niet": "X"})] == [t.name for t in base]


# --- UI / UI ------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path):
    settings = AppSettings(QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat))
    settings.set("ui/language", "en")
    win = MainWindow(settings)
    win._on_loaded(make_spec(), 1, True)
    yield win
    win.close()


def _answer(window, monkeypatch, text: str | None):
    """Vervang het tonen van dialogen: typ ``text`` en klik OK (None = annuleren). / Replace dialog showing: type
    ``text`` and click OK (None = cancel)."""
    seen: list[Any] = []

    def fake(dialog):
        seen.append(dialog)
        if text is None:
            return QDialog.DialogCode.Rejected
        dialog.name_edit.setText(text)
        if not dialog.ok_button.isEnabled():
            return QDialog.DialogCode.Rejected
        dialog.ok_button.click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(window, "_exec_dialog", fake)
    return seen


def _names(window) -> list[str]:
    return [t.name for t in window.tabs]


def _select_only(window, row: int) -> None:
    window.filter_list.clearSelection()
    window.filter_list.setCurrentRow(row)
    window.filter_list.item(row).setSelected(True)


def test_rename_action_is_enabled_only_for_one_selected_passport(window):
    _select_only(window, 0)
    assert window.rename_action.isEnabled()
    window.filter_list.item(1).setSelected(True)
    assert not window.rename_action.isEnabled()
    window.filter_list.clearSelection()
    assert not window.rename_action.isEnabled()


def test_edit_menu_has_rename_with_f2_and_tools_menu_has_checks(window):
    assert window.rename_action.shortcut().toString() == "F2"
    assert window.rename_action in window.edit_menu.actions()
    assert window.merge_selected_action in window.edit_menu.actions()
    assert window.merge_selected_action not in window.file_menu.actions()
    assert window.check_ids_action in window.tools_menu.actions()
    assert window.annotations_action in window.tools_menu.actions()
    assert window.check_ids_action not in window.file_menu.actions()
    edit = window.edit_menu.actions()
    assert edit.index(window.undo_action) < edit.index(window.mark_action) < edit.index(window.rename_action)


def test_rename_via_edit_menu_updates_list_payload_and_status(window, monkeypatch):
    _answer(window, monkeypatch, "Verkeersborden")
    _select_only(window, 0)
    window.rename_action.trigger()
    assert _names(window)[0] == "Verkeersborden"
    assert window.filter_list.item(0).text().startswith("Verkeersborden (")
    assert window.filter_list.item(0).text().endswith("✎")
    assert window.current_tab().name == "Verkeersborden"
    assert "Verkeersborden" in window.payload_text.toPlainText()
    assert "Renamed" in window.statusBar().currentMessage()
    assert "Bord" in window.filter_list.item(0).toolTip()  # origineel in tooltip / original in tooltip


def test_rename_cancel_changes_nothing(window, monkeypatch):
    _answer(window, monkeypatch, None)
    before = _names(window)
    _select_only(window, 0)
    window.rename_action.trigger()
    assert _names(window) == before and not window.undo_action.isEnabled()


def test_rename_to_duplicate_is_blocked_in_dialog_and_in_logic(window, monkeypatch):
    seen = _answer(window, monkeypatch, "informatiebord")
    before = _names(window)
    _select_only(window, 0)
    window.rename_action.trigger()
    assert _names(window) == before
    assert seen[0].error_label.text() == "A passport with this name already exists."
    assert not seen[0].ok_button.isEnabled()
    assert window.rename_tab("Bord", "Paal") is False
    assert _names(window) == before and not window.renames


def test_rename_keeps_marks_and_layout_and_undo_restores(window, monkeypatch):
    window.overrides["Bord"] = TabOverride(verify=frozenset({"breedte"}))
    _answer(window, monkeypatch, "Verkeersborden")
    _select_only(window, 0)
    window.rename_action.trigger()
    assert "Bord" not in window.overrides
    assert window.overrides["Verkeersborden"].verify == {"breedte"}
    assert window.undo_action.isEnabled() and "rename" in window.undo_action.text()
    window.undo_action.trigger()
    assert _names(window)[0] == "Bord" and window.overrides["Bord"].verify == {"breedte"}
    assert "Verkeersborden" not in window.overrides and not window.renames
    assert window.current_tab().name == "Bord"
    assert window.redo_action.isEnabled()
    window.redo_action.trigger()
    assert _names(window)[0] == "Verkeersborden" and "Verkeersborden" in window.overrides


def test_layout_store_uses_generated_name_so_it_survives_a_new_session(window):
    window.overrides["Bord"] = TabOverride(verify=frozenset({"breedte"}))
    assert window.rename_tab("Bord", "Verkeersborden")
    store = window._collect_store()
    assert window._layout_key("Bord") in store and window._layout_key("Verkeersborden") not in store
    window._layout_store = store
    window._apply_store()  # zelfde sessie: hernoeming blijft / same session: rename stays
    assert window.overrides["Verkeersborden"].verify == {"breedte"}
    window.renames.clear()  # nieuwe sessie: terug onder de gegenereerde naam / new session: generated name
    window._apply_store()
    assert window.overrides["Bord"].verify == {"breedte"}


def test_rename_survives_rebuild_and_reset_name_restores(window):
    window.rename_tab("Bord", "Verkeersborden")
    window._rebuild_designs()
    assert _names(window)[0] == "Verkeersborden"
    window.only_included_check.click()  # herbouwt de ontwerpen / rebuilds the designs
    assert _names(window)[0] == "Verkeersborden"
    assert window.rename_tab("Verkeersborden", "Bord")
    assert _names(window)[0] == "Bord" and not window.renames
    assert "reset" in window.statusBar().currentMessage()


def test_context_menu_offers_rename_and_reset_for_renamed_tab(window, monkeypatch):
    captured: list[list[str]] = []
    monkeypatch.setattr(QMenu, "exec", lambda self, *a: captured.append([a.text() for a in self.actions()]))
    rect = window.filter_list.visualItemRect(window.filter_list.item(0))
    window._show_filter_menu(rect.center())
    assert "&Rename passport…" in captured[0] and "Reset passport name" not in captured[0]
    window.rename_tab("Bord", "Verkeersborden")
    window._show_filter_menu(window.filter_list.visualItemRect(window.filter_list.item(0)).center())
    assert "Reset passport name" in captured[1]
    assert any("Merge" in text for text in captured[1])


def test_context_menu_rename_action_opens_dialog_and_renames(window, monkeypatch):
    _answer(window, monkeypatch, "Palen")
    actions: list[Any] = []
    monkeypatch.setattr(QMenu, "exec", lambda self, *a: actions.extend(self.actions()))
    window._show_filter_menu(window.filter_list.visualItemRect(window.filter_list.item(2)).center())
    rename = next(a for a in actions if "Rename" in a.text())
    rename.trigger()
    assert "Palen" in _names(window)


def test_double_click_on_passport_opens_rename(window, monkeypatch):
    seen = _answer(window, monkeypatch, "Dubbel")
    window.filter_list.itemDoubleClicked.emit(window.filter_list.item(1))
    assert seen and "Dubbel" in _names(window)


def test_rename_merged_passport_updates_applied_merge(window):
    window.threshold_spin.setValue(60)
    window.merge_tree.setCurrentItem(window.merge_tree.topLevelItem(0))
    window.apply_selected_merge()
    merged = window.tabs[0]
    assert merged.merged_from
    members = list(merged.merged_from)
    assert window.rename_tab(merged.name, "Alle borden")
    assert window.applied_merges[-1] == ("Alle borden", members)
    assert window.tabs[0].name == "Alle borden" and window.tabs[0].merged_from == members
    assert not window.renames
    window.undo_action.trigger()
    assert window.tabs[0].name == merged.name


def test_merging_a_renamed_passport_uses_its_generated_name(window, monkeypatch):
    window.rename_tab("Bord", "Verkeersborden")
    assert window._expand_members(["Verkeersborden", "Paal"]) == ["Bord", "Paal"]
    window.threshold_spin.setValue(60)
    window.merge_tree.setCurrentItem(window.merge_tree.topLevelItem(0))
    window.apply_selected_merge()
    assert "Bord" not in window.renames
    assert window.tabs[0].merged_from


def test_rename_suggestion_before_apply_gives_merge_that_name(window, monkeypatch):
    window.threshold_spin.setValue(60)
    window.merge_tree.setCurrentItem(window.merge_tree.topLevelItem(0))
    _answer(window, monkeypatch, "Mijn borden")
    window.rename_suggestion_button.click()
    assert window.merge_tree.topLevelItem(0).text(0) == "Mijn borden"
    assert window.suggestions[0].name == "Mijn borden" and window.suggestions[0].tab.name == "Mijn borden"
    window.update()
    window.apply_button.click()
    assert window.tabs[0].name == "Mijn borden" and window.tabs[0].merged_from


def test_suggestion_name_is_kept_until_the_threshold_changes(window, monkeypatch):
    window.threshold_spin.setValue(60)
    generated = window.suggestions[0].name
    assert window.set_suggestion_name(window.suggestions[0], "Mijn borden")
    window._update_suggestions()
    assert window.suggestions[0].name == "Mijn borden"
    window.threshold_spin.setValue(61)
    assert window.suggestions[0].name == generated


def test_suggestion_rename_to_duplicate_is_blocked(window):
    window.threshold_spin.setValue(60)
    assert window.set_suggestion_name(window.suggestions[0], "Paal") is False
    assert window.suggestions[0].name != "Paal"


def test_merge_context_menu_has_preview_rename_apply(window, monkeypatch):
    window.threshold_spin.setValue(60)
    captured: list[Any] = []
    monkeypatch.setattr(QMenu, "exec", lambda self, *a: captured.extend(self.actions()))
    rect = window.merge_tree.visualItemRect(window.merge_tree.topLevelItem(0))
    window._show_merge_menu(rect.center())
    assert [a.text() for a in captured] == ["Preview", "Rename suggestion…", "Apply"]


def test_excel_export_and_bulk_use_the_new_name(window, monkeypatch, tmp_path):
    from openpyxl import load_workbook

    window.rename_tab("Bord", "Verkeersborden")
    path = tmp_path / "x.xlsx"
    monkeypatch.setattr(window, "_save_path", lambda *_a, **_k: str(path))
    window.export_excel()
    names = load_workbook(path).sheetnames
    assert "Verkeersborden" in names and "Bord" not in names
    assert "Verkeersborden" in [t.name for t in window._compose_tabs(window.spec, window.engine)]


def test_new_spec_clears_renames(window):
    window.rename_tab("Bord", "Verkeersborden")
    window._on_loaded(make_spec(), 1, True)
    assert not window.renames and _names(window)[0] == "Bord"


def test_search_box_hides_non_matching_passports_and_tooltip_shows_full_name(window):
    window.filter_search.setText("paal")
    hidden = [window.filter_list.item(i).isHidden() for i in range(window.filter_list.count())]
    assert hidden.count(False) == 1
    assert "Paal" in window.filter_list.item(_names(window).index("Paal")).toolTip()
    window.filter_search.setText("")
    assert not any(window.filter_list.item(i).isHidden() for i in range(window.filter_list.count()))


def test_rename_is_blocked_for_imported_design(window):
    window.imported = object()  # type: ignore[assignment]
    window._update_rename_state()
    assert not window.rename_action.isEnabled()
    assert window.rename_tab("Bord", "X") is False
    assert "generated design" in window.statusBar().currentMessage()
    window.imported = None


def test_dutch_labels_and_every_new_key_has_both_languages(window):
    window._set_language("nl")
    assert window.rename_action.text() == "Paspoort &hernoemen…"
    assert window.tools_menu.title() == "&Controle"
    window._set_language("en")
    for key in TRANSLATIONS:
        if key.startswith(("rename.", "undo.", "redo.")) or key in ("menu.tools", "action.rename_tab"):
            assert TRANSLATIONS[key].get("en") and TRANSLATIONS[key].get("nl"), key
