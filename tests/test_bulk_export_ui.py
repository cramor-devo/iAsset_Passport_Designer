"""UI-tests voor het tabblad Bulkexport (offscreen). / UI tests for the Bulk export tab (offscreen)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QSettings, Qt  # noqa: E402
from PyQt6.QtGui import QImage, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from passport_designer.i18n import TRANSLATIONS  # noqa: E402
from passport_designer.settings import AppSettings  # noqa: E402
from passport_designer.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, wave1_spec, tmp_path):
    settings = AppSettings(QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat))
    settings.set("ui/language", "en")
    win = MainWindow(settings)
    win._on_loaded(wave1_spec, 1, True)
    win.views.setCurrentWidget(win.bulk_panel)
    yield win
    win.close()


def _check(window, passport: int, type_index: int | None) -> None:
    top = window.bulk_panel.tree.topLevelItem(passport)
    item = top if type_index is None else top.child(type_index)
    item.setCheckState(0, Qt.CheckState.Checked)


def _wait(window, timeout_ms: int = 20000) -> None:
    import time

    end = time.monotonic() + timeout_ms / 1000
    while window._bulk is not None and time.monotonic() < end:
        QApplication.processEvents()
    assert window._bulk is None, "bulk export did not finish"


def _prepare(window, tmp_path):
    panel = window.bulk_panel
    _check(window, 0, None)
    _check(window, 0, 0)
    _check(window, 1, 0)
    panel.set_folders(str(tmp_path / "tabs"), str(tmp_path / "types"))
    return panel


def test_bulk_tab_is_the_seventh_and_translated(window):
    assert window.views.count() == 7 and window.views.tabText(6) == "Bulk export"
    assert all(TRANSLATIONS[k].keys() >= {"en", "nl"} for k in TRANSLATIONS if k.startswith(("bulk.", "tab.bulk")))


def test_button_counts_selection_and_needs_folders(window, tmp_path):
    panel = window.bulk_panel
    assert not panel.export_button.isEnabled() and panel.export_button.text() == "Export 0 images"
    _check(window, 0, None)
    assert panel.export_button.text() == "Export 1 images" and not panel.export_button.isEnabled()  # geen map
    panel.set_folders(str(tmp_path), "")
    assert panel.export_button.isEnabled()
    _check(window, 0, 0)
    assert panel.export_button.text() == "Export 2 images" and not panel.export_button.isEnabled()  # typemap
    panel.set_folders(str(tmp_path), str(tmp_path))
    assert panel.export_button.isEnabled()


def test_filter_hides_non_matching_types(window):
    panel = window.bulk_panel
    panel.filter_edit.setText("zzz-no-match")
    assert all(panel.tree.topLevelItem(i).isHidden() for i in range(panel.tree.topLevelItemCount()))
    panel.filter_edit.setText("")
    assert not panel.tree.topLevelItem(0).isHidden()


def test_full_run_writes_named_pngs_and_reports(window, tmp_path):
    panel = _prepare(window, tmp_path)
    tab0 = window.tabs[0]
    panel.export_button.click()
    assert window._bulk is not None  # bezig / in progress
    assert panel.progress_label.text().startswith("Exporting 1 of 3")
    assert not panel.export_button.isEnabled() and panel.cancel_button.isEnabled() and not panel.tree.isEnabled()
    _wait(window)
    names = sorted(p.name for p in (tmp_path / "tabs").glob("*.png"))
    assert names == [f"{tab0.name}.png"]
    assert len(list((tmp_path / "types").glob("*.png"))) == 2
    assert all(p.stat().st_size > 0 for p in tmp_path.rglob("*.png"))
    assert panel.report_label.text() == "Done: 3 exported, 0 failed"
    assert panel.export_button.isEnabled() and not panel.cancel_button.isEnabled()


def test_cancel_keeps_written_files_and_reports(window, tmp_path):
    panel = _prepare(window, tmp_path)
    panel.export_button.click()
    panel.cancel_button.click()
    _wait(window)
    written = list(tmp_path.rglob("*.png"))
    assert len(written) < 3
    assert panel.report_label.text().startswith(f"Cancelled: {len(written)} of 3 exported")


def test_one_failing_image_does_not_stop_the_run(window, tmp_path, monkeypatch):
    panel = _prepare(window, tmp_path)
    real_save = QPixmap.save
    calls = {"n": 0}

    def flaky(self, path, *args, **kwargs):
        calls["n"] += 1
        return False if calls["n"] == 2 else real_save(self, path, *args, **kwargs)

    monkeypatch.setattr(QPixmap, "save", flaky)
    panel.export_button.click()
    _wait(window)
    assert panel.report_label.text() == "Done: 2 exported, 1 failed"
    assert panel.details.count() == 1 and len(list(tmp_path.rglob("*.png"))) == 2


def _answer(monkeypatch, label: str) -> None:
    def fake_exec(self):
        for button in self.buttons():
            if button.text() == label:
                self._clicked = button
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: getattr(self, "_clicked", None))


def test_existing_files_can_be_skipped_and_stay_untouched(window, tmp_path, monkeypatch):
    panel = _prepare(window, tmp_path)
    (tmp_path / "tabs").mkdir()
    target = tmp_path / "tabs" / f"{window.tabs[0].name}.png"
    target.write_bytes(b"keep")
    _answer(monkeypatch, "Skip existing")
    panel.export_button.click()
    _wait(window)
    assert target.read_bytes() == b"keep"
    assert panel.report_label.text() == "Done: 2 exported, 0 failed (1 existing skipped)"


def test_cancelling_the_overwrite_question_starts_nothing(window, tmp_path, monkeypatch):
    panel = _prepare(window, tmp_path)
    (tmp_path / "tabs").mkdir()
    (tmp_path / "tabs" / f"{window.tabs[0].name}.png").write_bytes(b"keep")
    _answer(monkeypatch, "Cancel")
    panel.export_button.click()
    assert window._bulk is None and not list((tmp_path / "types").glob("*.png"))


def test_bulk_png_equals_single_png_for_same_selection(window, tmp_path):
    panel = window.bulk_panel
    window.filter_list.setCurrentRow(0)
    window.type_combo.setCurrentIndex(0)
    single = window.mockup.render_pixmap().toImage()
    _check(window, 0, None)
    panel.set_folders(str(tmp_path), str(tmp_path))
    window.views.setCurrentWidget(window.bulk_panel)
    panel.export_button.click()
    _wait(window)
    bulk = QImage(str(tmp_path / f"{window.tabs[0].name}.png"))
    assert bulk.size() == single.size() and bulk == single.convertToFormat(bulk.format())


def test_bulk_honours_the_options_without_changing_the_view(window, tmp_path, monkeypatch):
    panel = window.bulk_panel
    _check(window, 0, None)
    panel.set_folders(str(tmp_path), str(tmp_path))
    panel.dark_check.setChecked(False)
    panel.export_button.click()
    _wait(window)
    light = QImage(str(tmp_path / f"{window.tabs[0].name}.png"))
    assert window.theme_name == "dark" and window.only_included_check.isChecked()
    panel.dark_check.setChecked(True)
    _answer(monkeypatch, "Overwrite all")
    panel.export_button.click()
    _wait(window)
    dark = QImage(str(tmp_path / f"{window.tabs[0].name}.png"))
    assert light != dark
