"""Tabblad Bulkexport: kies paspoorten en objecttypen, mappen en opties en schrijf alle PNG's in één keer.
Bulk export tab: choose passports and object types, folders and options, and write all PNGs in one go."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..bulk_export import ExportJob, plan_jobs
from ..i18n import tr
from ..models import PassportTab
from .bulk_exporter import ExportReport

KIND_ROLE = Qt.ItemDataRole.UserRole


@dataclass(frozen=True)
class BulkOptions:
    """Opties van één run; los van de toestand van het venster. / Options of one run, independent of window state."""

    dark: bool
    only_included: bool
    minimal: bool
    verify: bool
    extra_tabs: bool


class BulkExportPanel(QWidget):
    """Boom met paspoorten (-> paspoort-PNG) en hun objecttypen (-> objecttype-PNG), mappen, opties en voortgang.
    Tree of passports (-> passport PNG) and their object types (-> object type PNG), folders, options and progress."""

    export_requested = pyqtSignal(object, object)  # (list[ExportJob], BulkOptions)
    cancel_requested = pyqtSignal()
    folders_changed = pyqtSignal(str, str)  # (paspoortmap, typemap) / (passport folder, type folder)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        self.filter_edit = QLineEdit()
        self.filter_edit.textChanged.connect(self._apply_filter)
        root.addWidget(self.filter_edit)
        buttons = QHBoxLayout()
        self.select_all_button = QPushButton()
        self.select_none_button = QPushButton()
        self.expand_button = QPushButton()
        self.select_all_button.clicked.connect(lambda: self._check_all(True))
        self.select_none_button.clicked.connect(lambda: self._check_all(False))
        self.expand_button.clicked.connect(lambda: self.tree.expandAll())
        for button in (self.select_all_button, self.select_none_button, self.expand_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        root.addLayout(buttons)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemChanged.connect(self._update_count)
        root.addWidget(self.tree, 1)

        self.options_box = QGroupBox()
        grid = QGridLayout(self.options_box)
        self.dark_check = QCheckBox()
        self.only_check = QCheckBox()
        self.minimal_check = QCheckBox()
        self.verify_check = QCheckBox()
        self.extra_check = QCheckBox()
        for index, check in enumerate(
            (self.dark_check, self.only_check, self.minimal_check, self.verify_check, self.extra_check),
        ):
            grid.addWidget(check, index // 2, index % 2)
        root.addWidget(self.options_box)

        self.folders_box = QGroupBox()
        folders = QGridLayout(self.folders_box)
        self.tab_folder_button = QPushButton()
        self.type_folder_button = QPushButton()
        self.tab_folder_edit = QLineEdit()
        self.type_folder_edit = QLineEdit()
        for edit in (self.tab_folder_edit, self.type_folder_edit):
            edit.setReadOnly(True)
            edit.textChanged.connect(self._update_count)
        self.tab_folder_button.clicked.connect(lambda: self._browse(self.tab_folder_edit, "bulk.tab_folder"))
        self.type_folder_button.clicked.connect(lambda: self._browse(self.type_folder_edit, "bulk.type_folder"))
        folders.addWidget(self.tab_folder_button, 0, 0)
        folders.addWidget(self.tab_folder_edit, 0, 1)
        folders.addWidget(self.type_folder_button, 1, 0)
        folders.addWidget(self.type_folder_edit, 1, 1)
        root.addWidget(self.folders_box)

        run = QHBoxLayout()
        self.export_button = QPushButton()
        self.export_button.clicked.connect(self._request)
        self.cancel_button = QPushButton()
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        run.addWidget(self.export_button)
        run.addWidget(self.cancel_button)
        run.addStretch(1)
        root.addLayout(run)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress_label = QLabel()
        self.report_label = QLabel()
        self.report_label.setWordWrap(True)
        self.details = QListWidget()
        self.details.setVisible(False)
        self.open_button = QPushButton()
        self.open_button.setVisible(False)
        self.open_button.clicked.connect(self._open_folder)
        for widget in (self.progress, self.progress_label, self.report_label, self.details, self.open_button):
            root.addWidget(widget)
        self._tabs: list[PassportTab] = []
        self._count = 0
        self._running = False
        self._report_folder = ""
        self.retranslate()

    # --- vullen / filling --------------------------------------------------------------------------------------

    def set_tabs(self, tabs: list[PassportTab]) -> None:
        """Vul de boom; aangevinkte paspoorten en typen blijven aangevinkt (op naam). / Fill the tree; checked
        passports and types stay checked (by name)."""
        keep = self.selection()
        self.tree.blockSignals(True)
        self.tree.clear()
        self._tabs = list(tabs)
        for tab in tabs:
            top = QTreeWidgetItem([f"{tab.name} ({len(tab.object_types)})"])
            top.setFlags(top.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            top.setData(0, KIND_ROLE, tab.name)
            wanted = None in keep.get(tab.name, set())
            top.setCheckState(0, Qt.CheckState.Checked if wanted else Qt.CheckState.Unchecked)
            for object_type in tab.object_types:
                child = QTreeWidgetItem([object_type.name])
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setData(0, KIND_ROLE, object_type.name)
                on = object_type.name in keep.get(tab.name, set())
                child.setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
                top.addChild(child)
            self.tree.addTopLevelItem(top)
        self.tree.blockSignals(False)
        self._apply_filter(self.filter_edit.text())
        self._update_count()

    def set_options(
        self, *, dark: bool, only_included: bool, minimal: bool, minimal_available: bool, verify: bool,
        extra_tabs: bool,
    ) -> None:
        """Zet de standaardwaarden uit de huidige weergave. / Set the defaults from the current view."""
        self.dark_check.setChecked(dark)
        self.only_check.setChecked(only_included)
        self.minimal_check.setChecked(minimal and minimal_available)
        self.minimal_check.setEnabled(minimal_available)
        self.verify_check.setChecked(verify)
        self.extra_check.setChecked(extra_tabs)

    def set_folders(self, tab_folder: str, type_folder: str) -> None:
        self.tab_folder_edit.setText(tab_folder)
        self.type_folder_edit.setText(type_folder)

    def options(self) -> BulkOptions:
        return BulkOptions(
            self.dark_check.isChecked(), self.only_check.isChecked(), self.minimal_check.isChecked(),
            self.verify_check.isChecked(), self.extra_check.isChecked(),
        )

    # --- selectie / selection ----------------------------------------------------------------------------------

    def selection(self) -> dict[str, set[str | None]]:
        """Paspoortnaam -> {None (paspoort) en/of typen}. / Passport name -> {None (passport) and/or types}."""
        result: dict[str, set[str | None]] = {}
        for index in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(index)
            if top is None:
                continue
            kinds: set[str | None] = set()
            if top.checkState(0) == Qt.CheckState.Checked:
                kinds.add(None)
            for child_index in range(top.childCount()):
                child = top.child(child_index)
                if child is not None and child.checkState(0) == Qt.CheckState.Checked:
                    kinds.add(str(child.data(0, KIND_ROLE)))
            if kinds:
                result[str(top.data(0, KIND_ROLE))] = kinds
        return result

    def _check_all(self, on: bool) -> None:
        state = Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
        self.tree.blockSignals(True)
        for index in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(index)
            if top is None or top.isHidden():
                continue
            top.setCheckState(0, state)
            for child_index in range(top.childCount()):
                child = top.child(child_index)
                if child is not None and not child.isHidden():
                    child.setCheckState(0, state)
        self.tree.blockSignals(False)
        self._update_count()

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().casefold()
        for index in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(index)
            if top is None:
                continue
            top_match = not needle or needle in str(top.data(0, KIND_ROLE)).casefold()
            any_child = False
            for child_index in range(top.childCount()):
                child = top.child(child_index)
                if child is None:
                    continue
                match = top_match or needle in str(child.data(0, KIND_ROLE)).casefold()
                child.setHidden(not match)
                any_child = any_child or match
            top.setHidden(not (top_match or any_child))
            if needle and any_child:
                top.setExpanded(True)

    def count(self) -> int:
        return sum(len(kinds) for kinds in self.selection().values())

    def _folders(self) -> tuple[Path | None, Path | None]:
        tab = self.tab_folder_edit.text().strip()
        kind = self.type_folder_edit.text().strip()
        return (Path(tab) if tab else None, Path(kind) if kind else None)

    def planned_jobs(self) -> list[ExportJob]:
        tab_folder, type_folder = self._folders()
        return plan_jobs(selection=self.selection(), tab_folder=tab_folder, type_folder=type_folder)

    def _ready(self) -> bool:
        selection = self.selection()
        tab_folder, type_folder = self._folders()
        needs_tab = any(None in kinds for kinds in selection.values())
        needs_type = any(k is not None for kinds in selection.values() for k in kinds)
        return bool(selection) and (tab_folder is not None or not needs_tab) and (
            type_folder is not None or not needs_type
        )

    def _update_count(self, *_args: object) -> None:
        self._count = self.count()
        self.export_button.setText(tr("bulk.export_n", count=self._count))
        self.export_button.setEnabled(self._ready() and not self._running)

    # --- mappen en starten / folders and start -----------------------------------------------------------------

    def _browse(self, edit: QLineEdit, title_key: str) -> None:
        start = edit.text() or self.tab_folder_edit.text() or self.type_folder_edit.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, tr(title_key), start)
        if not folder:
            return
        edit.setText(folder)
        if not self.type_folder_edit.text() and edit is self.tab_folder_edit:
            self.type_folder_edit.setText(folder)  # standaard dezelfde map / same folder by default
        self.folders_changed.emit(self.tab_folder_edit.text(), self.type_folder_edit.text())

    def _request(self) -> None:
        if not self._ready():
            return
        self.export_requested.emit(self.planned_jobs(), self.options())

    # --- voortgang en verslag / progress and report ------------------------------------------------------------

    def set_running(self, running: bool) -> None:
        """Tijdens de run staat alles uit behalve Annuleren. / During the run everything is off except Cancel."""
        self._running = running
        for widget in (self.tree, self.options_box, self.folders_box, self.filter_edit, self.select_all_button,
                       self.select_none_button, self.expand_button):
            widget.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.progress.setVisible(running)
        if running:
            self.report_label.clear()
            self.details.clear()
            self.details.setVisible(False)
            self.open_button.setVisible(False)
        self._update_count()

    def show_progress(self, number: int, total: int, name: str) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(number - 1)
        self.progress_label.setText(tr("bulk.progress", number=number, total=total, name=name))

    def show_report(self, report: ExportReport, folder: str) -> None:
        self.progress_label.clear()
        key = "bulk.cancelled" if report.cancelled else "bulk.done"
        text = tr(key, exported=report.exported, total=report.total, failed=len(report.failed))
        if report.skipped:
            text += " " + tr("bulk.skipped", count=report.skipped)
        self.report_label.setText(text)
        self.details.clear()
        for job, message in report.failed:
            self.details.addItem(f"{job.path.name}: {message}")
        self.details.setVisible(bool(report.failed))
        self._report_folder = folder
        self.open_button.setVisible(bool(folder))

    def _open_folder(self) -> None:
        if self._report_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._report_folder))

    def retranslate(self) -> None:
        self.filter_edit.setPlaceholderText(tr("bulk.filter"))
        self.select_all_button.setText(tr("bulk.select_all"))
        self.select_none_button.setText(tr("bulk.select_none"))
        self.expand_button.setText(tr("bulk.expand_all"))
        self.options_box.setTitle(tr("bulk.options"))
        self.dark_check.setText(tr("bulk.dark"))
        self.only_check.setText(tr("bulk.only_included"))
        self.minimal_check.setText(tr("bulk.minimal"))
        self.verify_check.setText(tr("bulk.verify"))
        self.extra_check.setText(tr("bulk.extra_tabs"))
        self.folders_box.setTitle(tr("bulk.folders"))
        self.tab_folder_button.setText(tr("bulk.tab_folder"))
        self.type_folder_button.setText(tr("bulk.type_folder"))
        self.cancel_button.setText(tr("bulk.cancel"))
        self.open_button.setText(tr("bulk.open_folder"))
        self._update_count()
