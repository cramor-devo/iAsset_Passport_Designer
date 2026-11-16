"""UI-tests voor slepen en neerzetten (offscreen). / UI tests for drag and drop (offscreen)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QByteArray, QMimeData, QPointF, QSettings, Qt  # noqa: E402
from PyQt6.QtGui import QDropEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication, QInputDialog  # noqa: E402

from passport_designer.layout_overrides import CellRef  # noqa: E402
from passport_designer.settings import AppSettings  # noqa: E402
from passport_designer.ui.main_window import MainWindow  # noqa: E402
from passport_designer.ui.sheet_preview import CELL_MIME  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make(tmp_path, spec) -> MainWindow:
    settings = AppSettings(QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat))
    settings.set("ui/language", "en")
    win = MainWindow(settings)
    win._on_loaded(spec, 1, True)
    win.filter_list.setCurrentRow(0)
    return win


@pytest.fixture
def window(app, wave1_spec, tmp_path):
    win = _make(tmp_path, wave1_spec)
    yield win
    win.close()


def _drop(win: MainWindow, source: CellRef, target_cell: tuple[int, int]) -> None:
    """Een echte drop-gebeurtenis op een cel. / A real drop event on a cell."""
    sheet = win.sheet_preview
    mime = QMimeData()
    mime.setData(CELL_MIME, QByteArray(f"{source.section},{source.row},{source.col}".encode()))
    rect = sheet.visualRect(sheet.indexFromItem(sheet.item(*target_cell)))
    event = QDropEvent(
        QPointF(rect.center()), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    sheet.dropEvent(event)


def _first_two(win: MainWindow) -> tuple[tuple[CellRef, tuple[int, int], str], tuple[CellRef, tuple[int, int], str]]:
    cells = sorted(win.sheet_preview._refs.items())
    (p1, r1), (p2, r2) = cells[0], cells[1]
    sheet = win.sheet_preview
    return (r1, p1, sheet.text_at(p1[0] + 1, p1[1] + 1)), (r2, p2, sheet.text_at(p2[0] + 1, p2[1] + 1))


def test_drop_reorders_then_undo_and_redo(window):
    (ref_a, pos_a, text_a), (ref_b, pos_b, text_b) = _first_two(window)
    _drop(window, ref_b, pos_a)  # b voor a / b before a
    sheet = window.sheet_preview
    assert text_a in {sheet.text_at(r + 1, c + 1) for (r, c) in sheet._refs}
    assert window.undo_action.isEnabled()
    changed = sorted((p, sheet.text_at(p[0] + 1, p[1] + 1)) for p in sheet._refs)
    window.undo_override()
    undone = sorted((p, sheet.text_at(p[0] + 1, p[1] + 1)) for p in sheet._refs)
    assert undone != changed and window.redo_action.isEnabled()
    window.redo_override()
    assert sorted((p, sheet.text_at(p[0] + 1, p[1] + 1)) for p in sheet._refs) == changed
    assert text_b


def test_context_menu_inserts_blank_row_and_reset_restores(window):
    sheet = window.sheet_preview
    original = {(p, sheet.text_at(p[0] + 1, p[1] + 1)) for p in sheet._refs}
    ref = min(sheet._refs.values(), key=lambda r: (r.section, r.row, r.col))
    menu = sheet.context_menu([], ref)
    action = next(a for a in menu.actions() if a.text() == "Insert empty row below")
    assert action.isEnabled()
    action.trigger()
    assert window.undo_action.isEnabled()
    reset = next(a for a in sheet.context_menu([], ref).actions() if a.text().startswith("Reset"))
    reset.trigger()
    assert {(p, sheet.text_at(p[0] + 1, p[1] + 1)) for p in sheet._refs} == original


def test_new_section_via_dialog_and_persisted_after_restart(app, wave1_spec, tmp_path, monkeypatch):
    win = _make(tmp_path, wave1_spec)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Mijn sectie", True)))
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: (a[3][0], True)))  # type: ignore[index]
    win._on_add_section(0)
    (_, _, text), _ = _first_two(win)
    texts = {win.sheet_preview.text_at(r, c) for r in range(1, win.sheet_preview.rowCount() + 1)
             for c in range(1, win.sheet_preview.columnCount() + 1)}
    assert "Mijn sectie" in texts and text
    win.close()  # bewaart de indeling / saves the layout
    again = _make(tmp_path, wave1_spec)
    texts = {again.sheet_preview.text_at(r, c) for r in range(1, again.sheet_preview.rowCount() + 1)
             for c in range(1, again.sheet_preview.columnCount() + 1)}
    assert "Mijn sectie" in texts
    again.close()


def test_drag_is_disabled_for_single_object_type(window):
    window.type_combo.setCurrentIndex(1)
    assert window.sheet_preview.editable is False
    window.type_combo.setCurrentIndex(0)
    assert window.sheet_preview.editable is True


