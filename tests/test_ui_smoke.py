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


def test_manual_merge_dialog_and_remerge(window):
    from PyQt6.QtWidgets import QAbstractItemView

    window._on_loaded(make_spec(), 1, True)
    assert window.filter_list.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    names = [t.name for t in window.tabs]
    assert names[:2] == ["Bord", "Informatiebord"]
    window.filter_list.item(0).setSelected(True)
    window.filter_list.item(2).setSelected(True)
    assert len(window.filter_list.selectedItems()) == 2 and window.current_tab() is not None
    dialog = window._merge_dialog_for(["Bord", "Paal"])
    assert dialog is not None and dialog.info.groups_differ and not dialog.group_warning.isHidden()
    assert dialog.cancel_button.isDefault() and not dialog.ok_button.isEnabled()
    dialog.name_edit.setText("")
    dialog.confirm_check.setChecked(True)
    assert not dialog.ok_button.isEnabled()
    dialog.name_edit.setText("Informatiebord")  # bestaat al / already exists
    assert not dialog.ok_button.isEnabled()
    dialog.name_edit.setText("Mix")
    assert dialog.ok_button.isEnabled()
    dialog.confirm_check.setChecked(False)
    assert not dialog.ok_button.isEnabled()
    dialog.confirm_check.setChecked(True)
    window._apply_manual_merge(dialog.merge_name(), ["Bord", "Paal"])
    merged = next(t for t in window.tabs if t.name == "Mix")
    assert merged.merged_from == ["Bord", "Paal"]
    assert window.applied_merges == [("Mix", ["Bord", "Paal"])]

    again = window._merge_dialog_for(["Mix", "Informatiebord"])
    assert again is not None and again.info.members == ["Bord", "Paal", "Informatiebord"]
    again.name_edit.setText("Alles")
    window._apply_manual_merge("Alles", ["Mix", "Informatiebord"])
    assert window.applied_merges == [("Alles", ["Bord", "Paal", "Informatiebord"])]
    assert [t.name for t in window.tabs][0] == "Alles"
    window.reset_merges()
    assert [t.name for t in window.tabs] == names


# --- 0.4.0: ID-controle, import, vergelijking, annotaties / ID check, import, cross-reference, annotations ----------


def wait_for_jobs() -> None:
    """Wacht tot achtergrondtaken klaar zijn en lever hun signalen af. / Wait for background jobs, deliver signals."""
    from PyQt6.QtCore import QThreadPool

    pool = QThreadPool.globalInstance()
    assert pool is not None
    for _ in range(3):  # een afgeronde taak kan een volgende starten / a finished job may start another
        pool.waitForDone()
        QApplication.processEvents()


@pytest.fixture
def exported_file(window, tmp_path, monkeypatch):
    path = tmp_path / "design.xlsx"
    monkeypatch.setattr(window, "_save_path", lambda *_a, **_k: str(path))
    window.export_excel()
    assert path.exists()
    return path


def crossref_texts(window) -> list[str]:
    tree = window.crossref_panel.tree
    texts: list[str] = []
    for index in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(index)
        texts.append(top.text(0))
        texts += [top.child(i).text(0) for i in range(top.childCount())]
    return texts


def test_export_passes_spec_for_reference_sheets(window, exported_file, tmp_path, monkeypatch):
    from openpyxl import load_workbook

    names = load_workbook(exported_file).sheetnames
    assert "Bron Objecttypen" in names and "Bron Attributen" in names and "_designer" in names
    per_type = tmp_path / "per_type.xlsx"
    monkeypatch.setattr(window, "_save_path", lambda *_a, **_k: str(per_type))
    window.export_excel_per_type()
    assert "Bron Objecttypen" in load_workbook(per_type).sheetnames


def test_import_round_trip_in_window_has_no_differences(window, exported_file):
    original = [t.name for t in window.tabs]
    window.load_refined(str(exported_file))
    wait_for_jobs()
    assert window.imported is not None and not window._busy
    assert [t.name for t in window.tabs] == original and window.filter_list.count() == len(original)
    assert window.back_action.isEnabled() and "design.xlsx" in window.windowTitle()
    assert all(entry.diff is not None and entry.diff.is_empty for entry in window.imported_sheets)
    assert "No differences" in crossref_texts(window)
    window._set_language("nl")
    assert "Geen verschillen" in crossref_texts(window)
    window._set_language("en")
    # payload blijft werken op geïmporteerde tabs / payload works on imported tabs
    assert "POST /passport-tabs" in window.payload_text.toPlainText()
    window.back_to_generated()
    assert window.imported is None and not window.back_action.isEnabled()
    assert [t.name for t in window.tabs] == original and window.windowTitle() == "iAsset Passport Designer"


def test_import_without_spec_and_with_changes(window, exported_file, wave1_spec):
    window.spec = None
    window.engine = None
    result = window.read_refined_with_diff(str(exported_file))
    assert result.diffs is None
    window.apply_import(result)
    assert "Load the specification" in window.crossref_panel.summary_label.text()
    assert window.imported_sheets[0].diff is None
    window.spec = wave1_spec
    window._rebuild_designs()  # nieuwe specificatie/instelling: terug naar gegenereerd / back to generated
    assert window.imported is None


def test_import_marks_removed_added_fields_in_panel(window, tmp_path, exported_file):
    from openpyxl import load_workbook

    workbook = load_workbook(exported_file)
    sheet = workbook["Bord"]
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value == "bordcode":
                cell.value = "bordcode extra"
    changed = tmp_path / "changed.xlsx"
    workbook.save(changed)
    window.apply_import(window.read_refined_with_diff(str(changed)))
    texts = crossref_texts(window)
    assert any(t.startswith("Bord (") and "No differences" not in t for t in texts)
    kinds = {t for t in texts if t in {"Renamed", "Added", "Removed", "Not in spec"}}
    assert kinds


def test_highlight_toggle_default_off_and_png_clean(window, exported_file):
    from passport_designer.crossref import DiffEntry, TabDiff

    assert not window.highlight_action.isChecked()
    window.apply_import(window.read_refined_with_diff(str(exported_file)))
    entry = window.imported_sheets[0]
    entry.diff = TabDiff(entries=[DiffEntry("bordcode", "added"), DiffEntry("hoogte", "moved")])
    window._refresh_views()
    assert window.current_highlights() == {} and window.mockup._highlights == {}
    assert not window.mockup.render_pixmap().isNull()
    window.highlight_action.setChecked(True)
    window._on_highlight_toggled()
    assert window.settings.boolean("view/highlight_changes", False)
    assert window.mockup._highlights == {"bordcode": "added", "hoogte": "moved"}
    assert not window.mockup.render_pixmap().isNull()
    window.highlight_action.setChecked(False)
    window._on_highlight_toggled()
    assert window.mockup._highlights == {}


def test_imported_tab_uses_excel_widths_for_grid_columns(window, exported_file):
    window.apply_import(window.read_refined_with_diff(str(exported_file)))
    widths = window.imported_sheets[0].sheet.column_widths
    assert widths
    from PyQt6.QtWidgets import QWidget

    rows = [w for w in window.mockup.findChildren(QWidget, "mockRow") if w.layout() is not None]
    assert rows
    grid = rows[0].layout()
    sheet = window.imported_sheets[0].sheet
    first = next(i for i, w in enumerate(window.mockup.findChildren(QWidget, "mockRow")) if w.layout() is not None)
    count = grid.count() // 2
    columns = [sheet.positions[(0, first, i)][1] for i in range(count)]
    assert [grid.columnStretch(i) for i in range(count)] == [max(1, round(widths[c - 1] * 10)) for c in columns]


def test_id_check_dialog_from_synthetic_catalog(window, tmp_path):
    from openpyxl import load_workbook

    from passport_designer.field_catalog import FieldCatalog, FieldInfo

    catalog = FieldCatalog(source="t.xlsx")
    catalog.entries = {
        5: FieldInfo(5, "bordcode", "pulldown", "select"), 6: FieldInfo(6, "Hoogte", "cijferveld", "numeric"),
    }
    dialog = window.id_check_dialog_for(catalog)
    total = len(dialog.findings)
    assert total > 2 and dialog.table.rowCount() == total
    header = dialog.table.horizontalHeaderItem(2)
    assert header is not None and header.text() == "Label" and dialog.table.isSortingEnabled()
    assert "fields checked" in dialog.summary_label.text()
    assert dialog.table.columnCount() == 7
    ids = {dialog.table.item(r, 3).text() for r in range(dialog.table.rowCount())}
    assert "5" in ids
    status = next(s for s in dialog.findings if s.status != "ok").status
    dialog.status_combo.setCurrentIndex(dialog.status_combo.findData(status))
    assert dialog.table.rowCount() == sum(1 for f in dialog.findings if f.status == status) < total
    dialog.status_combo.setCurrentIndex(0)
    dialog.severity_combo.setCurrentIndex(dialog.severity_combo.findData("error"))
    assert dialog.table.rowCount() == sum(1 for f in dialog.findings if f.severity == "error")
    out = tmp_path / "report.xlsx"
    dialog.export_to(out)
    assert load_workbook(out).worksheets[0].max_row == total + 1


def test_check_field_ids_uses_loaded_catalog_or_asks(window, tmp_path, monkeypatch):
    shown: list[object] = []
    monkeypatch.setattr(window, "_exec_dialog", lambda dialog: shown.append(dialog) or 0)
    source = tmp_path / "diverse.json"
    source.write_text('[{"id": 7, "label": "bordcode", "type": "select", "themes": []}]', encoding="utf-8")
    from PyQt6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(source), ""))
    window.check_field_ids()  # geen catalogus geladen: vraagt om bestand / no catalog: asks for a file
    wait_for_jobs()
    assert len(shown) == 1
    window.load_ids_file(str(source))
    wait_for_jobs()
    assert window.ids is not None and window.ids.catalog is not None
    assert "1 field IDs loaded" in window.statusBar().currentMessage()
    monkeypatch.setattr(window, "_choose_catalog_source", lambda _catalog: "loaded")
    window.check_field_ids()  # nu direct met de geladen catalogus / now directly with the loaded catalog
    wait_for_jobs()
    assert len(shown) == 2


def test_check_field_ids_can_use_separate_comparison_catalog(window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    from passport_designer.field_catalog import FieldCatalog, FieldInfo

    shown: list[object] = []
    seen: list[FieldCatalog] = []
    monkeypatch.setattr(window, "_exec_dialog", lambda dialog: shown.append(dialog) or 0)
    real_check = window.show_id_check
    monkeypatch.setattr(window, "show_id_check", lambda catalog: seen.append(catalog) or real_check(catalog))
    source = tmp_path / "diverse.json"
    source.write_text('[{"id": 7, "label": "bordcode", "type": "select", "themes": []}]', encoding="utf-8")
    window.load_ids_file(str(source))
    wait_for_jobs()
    loaded = window.ids.catalog
    assert loaded is not None
    loaded.subtheme_names = {1: "Bord"}
    other = FieldCatalog(source="gui.xlsx")
    other.entries = {7: FieldInfo(7, "bordcode", "cijferveld", "numeric")}
    monkeypatch.setattr("passport_designer.ui.main_window.load_catalog", lambda _p: other)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(source), ""))

    monkeypatch.setattr(window, "_choose_catalog_source", lambda _catalog: "")
    window.check_field_ids()  # annuleren / cancel
    wait_for_jobs()
    assert not seen

    monkeypatch.setattr(window, "_choose_catalog_source", lambda _catalog: "other")
    window.check_field_ids()
    wait_for_jobs()
    assert len(seen) == 1 and seen[0] is not loaded and seen[0].entries is other.entries
    assert seen[0].subtheme_names == {1: "Bord"} and other.subtheme_names == {}  # namen samengevoegd / names merged
    assert window.ids.catalog is loaded  # de ID-map blijft behouden / the ID map is retained
    assert len(shown) == 1


def test_choose_catalog_source_defaults_to_cancel(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from passport_designer.field_catalog import FieldCatalog

    boxes: list[QMessageBox] = []
    monkeypatch.setattr(window, "_exec_dialog", lambda box: boxes.append(box) or 0)
    assert window._choose_catalog_source(FieldCatalog(source="x.json")) == ""  # niets gekozen / nothing chosen
    box = boxes[0]
    assert box.defaultButton() is box.button(QMessageBox.StandardButton.Cancel)
    assert len(box.buttons()) == 3


def test_annotation_dialog_with_report_and_fix(window, exported_file, monkeypatch):
    pytest.importorskip("passport_designer.annotations")
    from passport_designer.annotations import AnnotationIssue, AnnotationReport, FixResult
    from passport_designer.ui.annotation_dialog import AnnotationDialog

    report = AnnotationReport(
        exported_file, [AnnotationIssue("Bord", "A5", "stale-number", "warning", "(2) should be (1)")], ["Bord"],
    )
    after = AnnotationReport(exported_file, [], ["Bord"])
    result = FixResult(exported_file.with_name("design_fixed.xlsx"), ["Bord!A5: (2) → (1)"], after)
    dialog = AnnotationDialog(report, window.spec is not None, lambda: result, window)
    detail = dialog.table.item(0, 4)
    assert dialog.table.rowCount() == 1 and detail is not None and detail.text() == "(2) should be (1)"
    assert dialog.info_label.isHidden() and dialog.fix_button.isEnabled()
    dialog.run_fix()
    wait_for_jobs()
    assert not dialog.result_box.isHidden() and "design_fixed.xlsx" in dialog.result_box.toPlainText()
    assert dialog.table.rowCount() == 0
    assert not AnnotationDialog(report, False, None, window).info_label.isHidden()

    shown: list[object] = []
    monkeypatch.setattr(window, "_exec_dialog", lambda d: shown.append(d) or 0)
    window.run_annotation_check(str(exported_file))
    wait_for_jobs()
    assert len(shown) == 1 and isinstance(shown[0], AnnotationDialog)


def test_merge_is_disabled_for_imported_design(window, exported_file):
    assert window.merge_selected_action.isEnabled() and window.apply_button.isEnabled()
    window.apply_import(window.read_refined_with_diff(str(exported_file)))
    for widget in (window.merge_selected_action, window.merge_selected_button, window.apply_button,
                   window.reset_button):
        assert not widget.isEnabled()
    assert "generated design" in window.merge_selected_button.toolTip()
    tabs = list(window.tabs)
    window.merge_selected()
    window.apply_selected_merge()
    window.reset_merges()
    assert window.imported is not None and window.tabs == tabs
    window.back_to_generated()
    assert window.merge_selected_action.isEnabled() and window.merge_selected_button.isEnabled()
    assert window.apply_button.isEnabled() and window.reset_button.isEnabled()


def test_manual_merge_reports_when_nothing_was_merged(window):
    window._apply_manual_merge("Spook", ["Bord", "Bestaat niet"])
    assert "not applied" in window.statusBar().currentMessage()
    assert window.applied_merges == [] and not any(t.merged_from for t in window.tabs)
    window._apply_manual_merge("Mix", ["Bord", "Verharding"])
    assert window.statusBar().currentMessage() == "Merged into Mix."


def test_id_check_and_annotation_fix_run_in_background(window, monkeypatch):
    from passport_designer.field_catalog import FieldCatalog, FieldInfo
    from passport_designer.ui.id_check_dialog import IdCheckDialog

    shown: list[object] = []
    monkeypatch.setattr(window, "_exec_dialog", lambda dialog: shown.append(dialog) or 0)
    catalog = FieldCatalog(source="t.xlsx")
    catalog.entries = {5: FieldInfo(5, "bordcode", "pulldown", "select")}
    window.show_id_check(catalog)
    assert shown == [] and window._busy  # nog niet klaar: loopt op een werkthread / runs on a worker thread
    wait_for_jobs()
    assert len(shown) == 1 and isinstance(shown[0], IdCheckDialog) and not window._busy

    warned: list[str] = []
    monkeypatch.setattr(window, "_warn", warned.append)

    def boom(*_a):
        raise RuntimeError("kapot")

    monkeypatch.setattr("passport_designer.ui.main_window.check_ids", boom)
    window.show_id_check(catalog)
    wait_for_jobs()
    assert len(shown) == 1 and not window._busy and "kapot" in warned[0]


def test_annotation_fix_runs_in_job_and_shows_warnings(window, exported_file, monkeypatch):
    from passport_designer.annotations import AnnotationReport, FixResult
    from passport_designer.ui import annotation_dialog
    from passport_designer.ui.annotation_dialog import AnnotationDialog

    report = AnnotationReport(exported_file, [], ["Bord"])
    result = FixResult(exported_file.with_name("x_fixed.xlsx"), [], report, ["tekeningen gaan verloren"])
    dialog = AnnotationDialog(report, True, lambda: result, window)
    dialog.run_fix()
    assert dialog.result_box.isHidden() and not dialog.fix_button.isEnabled()
    wait_for_jobs()
    assert "tekeningen gaan verloren" in dialog.result_box.toPlainText() and dialog.fix_button.isEnabled()

    errors: list[str] = []
    monkeypatch.setattr(annotation_dialog.QMessageBox, "warning", lambda *a: errors.append(a[2]))

    def boom():
        raise ValueError("nee")

    failing = AnnotationDialog(report, True, boom, window)
    failing.run_fix()
    wait_for_jobs()
    assert errors and "nee" in errors[0] and failing.fix_button.isEnabled()
