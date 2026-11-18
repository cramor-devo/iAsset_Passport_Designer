"""UI-tests voor relatie- en standaardblokken (offscreen, EN + NL). / UI tests for relation and standard blocks
(offscreen, EN + NL)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QSettings, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QWidget  # noqa: E402

from passport_designer.i18n import tr, translator  # noqa: E402
from passport_designer.settings import AppSettings  # noqa: E402
from passport_designer.ui.main_window import MainWindow  # noqa: E402
from passport_designer.ui.relation_block_dialog import BlockEditor, BlockManagerDialog  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make(tmp_path, spec, language: str = "en") -> MainWindow:
    settings = AppSettings(QSettings(str(tmp_path / f"{language}.ini"), QSettings.Format.IniFormat))
    settings.set("ui/language", language)
    win = MainWindow(settings)
    win._on_loaded(spec, 1, True)
    win.filter_list.setCurrentRow(0)
    return win


@pytest.fixture(params=["en", "nl"])
def window(request, app, wave1_spec, tmp_path):
    win = _make(tmp_path, wave1_spec, request.param)
    yield win
    win.close()
    translator.set_language("en")


def _fill(editor: BlockEditor, name: str, element: int, columns: list[str]) -> None:
    editor.name_edit.setText(name)
    editor.type_combo.setCurrentIndex(editor.type_combo.findData(element))
    for row in range(editor.table.rowCount()):
        item = editor.table.item(row, 0)
        assert item is not None
        item.setText(columns[row] if row < len(columns) else "")


def _run_editor_with(monkeypatch, dialog: BlockManagerDialog, fill) -> None:
    def run(editor: BlockEditor) -> bool:
        fill(editor)
        return bool(editor.ok_button and editor.ok_button.isEnabled())

    monkeypatch.setattr(dialog, "_run_editor", run)


def _titles(win: MainWindow) -> list[str]:
    shown = win._effective(win.current_tab())[0]
    assert shown is not None
    return [s.title for s in shown.sections]


def test_menu_action_and_context_menu_open_the_dialog(window, monkeypatch):
    opened: list[QDialog] = []
    monkeypatch.setattr(window, "_exec_dialog", lambda d: opened.append(d) or 0)
    assert window.relation_blocks_action in window.edit_menu.actions()
    assert window.relation_blocks_action.text() == tr("action.relation_blocks")
    window.relation_blocks_action.trigger()
    ref = min(window.sheet_preview._refs.values(), key=lambda r: (r.section, r.row, r.col))
    menu = window.sheet_preview.context_menu([], ref)
    next(a for a in menu.actions() if a.text() == tr("action.relation_blocks").replace("&", "")).trigger()
    assert len(opened) == 2 and all(isinstance(d, BlockManagerDialog) for d in opened)


def test_add_relation_block_via_dialog_then_undo_and_payload(window, monkeypatch):
    dialog = window.block_manager_for()
    assert dialog.windowTitle() == tr("blocks.title") and dialog.add_button.text() == tr("blocks.add")
    _run_editor_with(monkeypatch, dialog, lambda e: _fill(e, "Bevat (Sem.Rel)", 20, ["Nummer", "Naam"]))
    QTest.mouseClick(dialog.add_button, Qt_LeftButton())
    assert "Bevat (Sem.Rel)" in _titles(window)
    assert window.undo_action.isEnabled()
    assert dialog.list.count() == 5 and "Bevat (Sem.Rel)" in dialog.list.item(4).text()
    window._render_payload_text()
    assert '"field_id": 20' in window.payload_text.toPlainText()
    window.undo_override()
    assert "Bevat (Sem.Rel)" not in _titles(window)
    window.redo_override()
    assert "Bevat (Sem.Rel)" in _titles(window)


def test_rename_standard_block_for_all_passports_and_reset(window, monkeypatch):
    dialog = window.block_manager_for()
    actors_row = next(i for i, e in enumerate(dialog.entries) if e.original_title.startswith("Actoren"))
    dialog.list.setCurrentRow(actors_row)
    assert not dialog.reset_button.isEnabled() and not dialog.delete_button.isEnabled()
    dialog.scope_combo.setCurrentIndex(1)  # alle paspoorten / all passports
    _run_editor_with(monkeypatch, dialog, lambda e: e.name_edit.setText("Betrokkenen"))
    QTest.mouseClick(dialog.edit_button, Qt_LeftButton())
    assert len(window.tabs) > 1
    for tab in window.tabs:
        shown = window._effective(tab)[0]
        assert shown is not None and "Betrokkenen" in [s.title for s in shown.sections]
    assert dialog.reset_button.isEnabled() and "Betrokkenen" in dialog.list.item(actors_row).text()
    QTest.mouseClick(dialog.reset_button, Qt_LeftButton())
    assert all(
        "Actoren en rollen (Sem.Rel)" in [s.title for s in (window._effective(t)[0] or t).sections]
        for t in window.tabs
    )
    assert window.overrides == {}


def test_editor_rejects_duplicate_name_and_disables_ok(window):
    dialog = window.block_manager_for()
    editor = dialog._editor(None)
    editor.name_edit.setText("Memo (Sem.Rel)")
    assert not editor.ok_button.isEnabled() and editor.error_label.text() == tr("merge.name_duplicate")
    editor.name_edit.setText("Eigen blok")
    assert editor.ok_button.isEnabled() and editor.error_label.text() == ""
    for row in range(editor.table.rowCount()):
        item = editor.table.item(row, 0)
        assert item is not None
        item.setText("")
    assert not editor.ok_button.isEnabled() and editor.error_label.text() == tr("blocks.columns_needed")


def test_delete_and_move_buttons_follow_selection(window, monkeypatch):
    dialog = window.block_manager_for()
    for name, element in (("A (Sem.Rel)", 17), ("B (Sem.Rel)", 18)):
        _run_editor_with(monkeypatch, dialog, lambda e, n=name, x=element: _fill(e, n, x, ["Nummer"]))
        QTest.mouseClick(dialog.add_button, Qt_LeftButton())
    dialog.list.setCurrentRow(dialog.list.count() - 1)
    assert dialog.up_button.isEnabled() and not dialog.down_button.isEnabled()
    QTest.mouseClick(dialog.up_button, Qt_LeftButton())
    assert _titles(window).index("B (Sem.Rel)") < _titles(window).index("A (Sem.Rel)")
    QTest.mouseClick(dialog.delete_button, Qt_LeftButton())
    assert len([t for t in _titles(window) if t in {"A (Sem.Rel)", "B (Sem.Rel)"}]) == 1


def test_blocks_persist_after_restart(app, wave1_spec, tmp_path, monkeypatch):
    win = _make(tmp_path, wave1_spec)
    dialog = win.block_manager_for()
    _run_editor_with(monkeypatch, dialog, lambda e: _fill(e, "Bewaard blok", 19, ["Nummer"]))
    QTest.mouseClick(dialog.add_button, Qt_LeftButton())
    win.close()
    again = _make(tmp_path, wave1_spec)
    assert "Bewaard blok" in _titles(again)
    again.close()


def test_all_passport_scope_skips_passports_with_a_name_clash(window, monkeypatch):
    other = window.tabs[1]
    dialog = window.block_manager_for()
    window.filter_list.setCurrentRow(1)
    _run_editor_with(monkeypatch, dialog, lambda e: _fill(e, "Botst (Sem.Rel)", 17, ["Nummer"]))
    QTest.mouseClick(dialog.add_button, Qt_LeftButton())  # alleen tab 1 / only tab 1
    window.filter_list.setCurrentRow(0)
    dialog.refresh()
    dialog.scope_combo.setCurrentIndex(1)
    QTest.mouseClick(dialog.add_button, Qt_LeftButton())
    for tab in window.tabs:
        blocks = [b for b in window.overrides[tab.name].blocks if b.title == "Botst (Sem.Rel)"]
        assert len(blocks) == 1, tab.name
    assert other.name in window.overrides


class QTest:
    """Klik via het echte widget / click through the real widget (the PyQt6 stubs reject QTest.mouseClick)."""

    @staticmethod
    def mouseClick(widget: QWidget, button: Qt.MouseButton) -> None:  # noqa: N802
        assert button == Qt.MouseButton.LeftButton
        widget.click()  # type: ignore[attr-defined]


def Qt_LeftButton() -> Qt.MouseButton:  # noqa: N802 - kleine helper / small helper
    return Qt.MouseButton.LeftButton
