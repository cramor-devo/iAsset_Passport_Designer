"""Hoofdvenster: specificaties laden, ontwerp kiezen, mockup bekijken en API-strings/Excel exporteren.
Main window: load specifications, pick a design, view the mockup and export API strings/Excel."""

from __future__ import annotations

import copy
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QAction, QActionGroup, QCloseEvent, QFont, QGuiApplication, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..crossref import TabDiff, changed_labels, diff_workbook
from ..excel_export import export_merge_report, export_workbook
from ..field_catalog import CatalogError, FieldCatalog, load_catalog
from ..field_map import FieldIdMap, FieldMapError
from ..i18n import LANGUAGES, tr, translator
from ..id_check import check_ids
from ..layout_engine import LayoutEngine, LayoutOptions
from ..merge_advisor import DEFAULT_THRESHOLD, MergeSuggestion, apply_merges, manual_merge_info, suggest_merges
from ..models import PassportTab, Severity, SpecModel
from ..payload import (
    ENDPOINT,
    PayloadOptions,
    TabPayload,
    build_tab_payload,
    to_compact_json,
    to_form_lines,
    to_json,
)
from ..profiles import DEFAULT_PROFILE, PROFILES, DesignProfile
from ..refined_import import RefinedSheet, RefinedWorkbook, read_refined
from ..settings import AppSettings, data_dir
from ..spec_reader import SpecError, read_spec
from .annotation_dialog import AnnotationDialog
from .crossref_panel import CrossRefPanel
from .id_check_dialog import IdCheckDialog
from .merge_dialog import MergeDialog
from .mockup import PassportMockup
from .settings_dialog import PayloadSettingsDialog
from .sheet_preview import SheetPreview
from .theme import PALETTES, app_stylesheet
from .workers import Job, run_job

log = logging.getLogger(__name__)

CATALOG_LOADED, CATALOG_OTHER = "loaded", "other"
FORMATS = ("payload.fmt_json", "payload.fmt_compact", "payload.fmt_form")
SEVERITY_MARK = {Severity.INFO: "ℹ", Severity.WARNING: "⚠", Severity.ERROR: "⛔"}
UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\s]+')


@dataclass
class ImportedSheet:
    """Een ingelezen blad met (optioneel) het verschil met de specificatie. / An imported sheet with its diff."""

    sheet: RefinedSheet
    diff: TabDiff | None = None


@dataclass
class ImportResult:
    """Uitkomst van de import op de werkthread. / Result of the import on the worker thread."""

    refined: RefinedWorkbook
    diffs: list[tuple[str, TabDiff]] | None


def safe_filename(name: str) -> str:
    return UNSAFE_FILENAME.sub("_", name).strip("_") or "passport"


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or AppSettings()
        translator.set_language(self.settings.string("ui/language", "en"))
        self.theme_name = self.settings.string("ui/theme", "dark")
        if self.theme_name not in PALETTES:
            self.theme_name = "dark"
        self.options: PayloadOptions = self.settings.payload_options()
        self.profile: DesignProfile = PROFILES.get(self.settings.string("design/profile", ""), DEFAULT_PROFILE)
        self.spec: SpecModel | None = None
        self.tabs: list[PassportTab] = []
        self.ids: FieldIdMap | None = None
        self.payload: TabPayload | None = None
        self.engine: LayoutEngine | None = None
        self.suggestions: list[MergeSuggestion] = []
        self.applied_merges: list[tuple[str, list[str]]] = []
        self._preview: PassportTab | None = None
        self.imported: RefinedWorkbook | None = None
        self.imported_sheets: list[ImportedSheet] = []
        self._busy = False
        self._actions: list[QAction] = []
        self._build_ui()
        self._build_menus()
        self.retranslate()
        self._apply_theme()
        self.resize(1360, 860)

    # --- opbouw / construction -------------------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.column_label = QLabel()
        self.column_combo = QComboBox()
        self.column_label.setBuddy(self.column_combo)
        self.column_combo.currentIndexChanged.connect(self._on_filter_column_changed)
        left_layout.addWidget(self.column_label)
        left_layout.addWidget(self.column_combo)
        self.filter_label = QLabel()
        self.filter_list = QListWidget()
        self.filter_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.filter_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.filter_list.customContextMenuRequested.connect(self._show_filter_menu)
        self.filter_label.setBuddy(self.filter_list)
        self.filter_list.currentRowChanged.connect(self._on_filter_changed)
        self.type_label = QLabel()
        self.type_combo = QComboBox()
        self.type_label.setBuddy(self.type_combo)
        self.type_combo.currentIndexChanged.connect(self._refresh_views)
        self.flagged_check = QCheckBox()
        self.flagged_check.setChecked(self.settings.boolean("design/only_flagged", True))
        self.flagged_check.toggled.connect(self._on_flagged_toggled)
        left_layout.addWidget(self.filter_label)
        left_layout.addWidget(self.filter_list, 1)
        for widget in (self.type_label, self.type_combo, self.flagged_check):
            left_layout.addWidget(widget)
        splitter.addWidget(left)

        self.views = QTabWidget()
        self.mockup = PassportMockup()
        self.mockup.show_extra_tabs = self.settings.boolean("view/extra_tabs", True)
        self.views.addTab(self.mockup, "")
        self.sheet_preview = SheetPreview()
        self.views.addTab(self.sheet_preview, "")
        self.views.addTab(self._build_payload_tab(), "")
        self.validation_list = QListWidget()
        self.validation_list.setWordWrap(True)
        self.views.addTab(self.validation_list, "")
        self.views.addTab(self._build_merge_tab(), "")
        self.crossref_panel = CrossRefPanel()
        self.views.addTab(self.crossref_panel, "")
        splitter.addWidget(self.views)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1040])

    def _build_merge_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.threshold_label = QLabel()
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(30, 100)
        self.threshold_spin.setSuffix(" %")
        self.threshold_spin.setValue(self.settings.integer("merge/threshold", round(DEFAULT_THRESHOLD * 100)))
        self.threshold_label.setBuddy(self.threshold_spin)
        self.same_group_check = QCheckBox()
        self.same_group_check.setChecked(self.settings.boolean("merge/same_group", True))
        self.threshold_spin.valueChanged.connect(self._on_merge_params_changed)
        self.same_group_check.toggled.connect(self._on_merge_params_changed)
        controls.addWidget(self.threshold_label)
        controls.addWidget(self.threshold_spin)
        controls.addWidget(self.same_group_check)
        controls.addStretch(1)
        layout.addLayout(controls)
        self.merge_hint = QLabel()
        self.merge_hint.setWordWrap(True)
        self.merge_summary = QLabel()
        layout.addWidget(self.merge_hint)
        layout.addWidget(self.merge_summary)
        self.merge_tree = QTreeWidget()
        self.merge_tree.setColumnCount(5)
        self.merge_tree.setRootIsDecorated(True)
        self.merge_tree.itemDoubleClicked.connect(lambda *_: self.preview_merge())
        layout.addWidget(self.merge_tree, 1)
        buttons = QHBoxLayout()
        self.preview_button = QPushButton()
        self.preview_button.clicked.connect(self.preview_merge)
        self.apply_button = QPushButton()
        self.apply_button.clicked.connect(self.apply_selected_merge)
        self.reset_button = QPushButton()
        self.reset_button.clicked.connect(self.reset_merges)
        self.merge_selected_button = QPushButton()
        self.merge_selected_button.clicked.connect(self.merge_selected)
        self.merge_export_button = QPushButton()
        self.merge_export_button.clicked.connect(self.export_merge_matrix)
        for button in (self.preview_button, self.apply_button, self.merge_selected_button, self.reset_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.merge_export_button)
        layout.addLayout(buttons)
        return page

    def _build_payload_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.format_label = QLabel()
        self.format_combo = QComboBox()
        self.format_label.setBuddy(self.format_combo)
        self.format_combo.currentIndexChanged.connect(self._render_payload_text)
        self.copy_button = QPushButton()
        self.copy_button.clicked.connect(self._copy_payload)
        self.save_button = QPushButton()
        self.save_button.clicked.connect(self.save_payload)
        controls.addWidget(self.format_label)
        controls.addWidget(self.format_combo)
        controls.addStretch(1)
        controls.addWidget(self.copy_button)
        controls.addWidget(self.save_button)
        layout.addLayout(controls)
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.summary_label = QLabel()
        layout.addWidget(self.hint_label)
        layout.addWidget(self.summary_label)
        self.payload_text = QPlainTextEdit()
        self.payload_text.setReadOnly(True)
        self.payload_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.payload_text.setFont(mono)
        layout.addWidget(self.payload_text, 1)
        return page

    def _action(
        self, key: str, slot: Callable[[], object], shortcut: str | QKeySequence.StandardKey | None = None,
    ) -> QAction:
        action = QAction(self)
        action.setData(key)
        action.triggered.connect(lambda _checked=False: slot())
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        self._actions.append(action)
        return action

    def _build_menus(self) -> None:
        bar = self.menuBar()
        assert bar is not None
        self.file_menu = bar.addMenu("") or QMenu()
        self.view_menu = bar.addMenu("") or QMenu()
        self.settings_menu = bar.addMenu("") or QMenu()
        self.help_menu = bar.addMenu("") or QMenu()
        self.open_action = self._action("action.open", self.open_specs, QKeySequence.StandardKey.Open)
        self.add_action = self._action("action.add", self.add_spec, "Ctrl+Shift+O")
        self.ids_action = self._action("action.load_ids", self.load_ids, "Ctrl+I")
        self.check_ids_action = self._action("action.check_ids", self.check_field_ids, "Ctrl+Shift+D")
        self.import_action = self._action("action.import_refined", self.import_refined, "Ctrl+Shift+I")
        self.back_action = self._action("action.back_generated", self.back_to_generated)
        self.back_action.setEnabled(False)
        self.annotations_action = self._action("action.check_annotations", self.check_annotations, "Ctrl+Shift+A")
        self.excel_action = self._action("action.export_excel", self.export_excel, "Ctrl+E")
        self.excel_types_action = self._action("action.export_excel_types", self.export_excel_per_type, "Ctrl+Shift+E")
        self.png_action = self._action("action.export_png", self.export_png, "Ctrl+P")
        self.payload_action = self._action("action.save_payload", self.save_payload, QKeySequence.StandardKey.Save)
        self.all_payload_action = self._action("action.save_all_payloads", self.save_all_payloads, "Ctrl+Shift+S")
        self.merge_selected_action = self._action("action.merge_selected", self.merge_selected, "Ctrl+M")
        self.quit_action = self._action("action.quit", self.close, QKeySequence.StandardKey.Quit)
        for action in (self.open_action, self.add_action, self.ids_action, self.check_ids_action):
            self.file_menu.addAction(action)
        self.file_menu.addSeparator()
        for action in (self.import_action, self.back_action, self.annotations_action):
            self.file_menu.addAction(action)
        self.file_menu.addSeparator()
        for action in (
            self.excel_action, self.excel_types_action, self.png_action, self.payload_action, self.all_payload_action,
        ):
            self.file_menu.addAction(action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.merge_selected_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.quit_action)

        self.highlight_action = self._action("action.highlight", self._on_highlight_toggled)
        self.highlight_action.setCheckable(True)
        self.highlight_action.setChecked(self.settings.boolean("view/highlight_changes", False))
        self.extra_tabs_action = self._action("action.extra_tabs", self._on_extra_tabs_toggled)
        self.extra_tabs_action.setCheckable(True)
        self.extra_tabs_action.setChecked(self.mockup.show_extra_tabs)
        self.view_menu.addAction(self.highlight_action)
        self.view_menu.addAction(self.extra_tabs_action)
        self.view_menu.addSeparator()
        self.theme_menu = self.view_menu.addMenu("") or QMenu()
        self.language_menu = self.view_menu.addMenu("") or QMenu()
        theme_group = QActionGroup(self)
        self._theme_actions: dict[str, QAction] = {}
        for name in PALETTES:
            action = QAction(self)
            action.setCheckable(True)
            action.setChecked(name == self.theme_name)
            action.triggered.connect(lambda _checked=False, n=name: self._set_theme(n))
            theme_group.addAction(action)
            self.theme_menu.addAction(action)
            self._theme_actions[name] = action
        language_group = QActionGroup(self)
        self._language_actions: dict[str, QAction] = {}
        for code, label in LANGUAGES.items():
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(code == translator.language)
            action.triggered.connect(lambda _checked=False, c=code: self._set_language(c))
            language_group.addAction(action)
            self.language_menu.addAction(action)
            self._language_actions[code] = action

        self.payload_settings_action = self._action("action.payload_settings", self.edit_payload_settings)
        self.settings_menu.addAction(self.payload_settings_action)
        self.profile_menu = self.settings_menu.addMenu("") or QMenu()
        profile_group = QActionGroup(self)
        self._profile_actions: dict[str, QAction] = {}
        for key, profile in PROFILES.items():
            action = QAction(profile.label, self)
            action.setCheckable(True)
            action.setChecked(profile is self.profile)
            action.triggered.connect(lambda _checked=False, k=key: self._set_profile(k))
            profile_group.addAction(action)
            self.profile_menu.addAction(action)
            self._profile_actions[key] = action
        self.about_action = self._action("action.about", self.show_about)
        self.help_menu.addAction(self.about_action)

    def retranslate(self) -> None:
        """Zet alle teksten opnieuw volgens de gekozen taal. / Re-apply all texts for the chosen language."""
        self._update_title()
        for action in self._actions:
            action.setText(tr(str(action.data())))
        self.highlight_action.setToolTip(tr("action.highlight_tip"))
        self.crossref_panel.retranslate()
        self.file_menu.setTitle(tr("menu.file"))
        self.view_menu.setTitle(tr("menu.view"))
        self.settings_menu.setTitle(tr("menu.settings"))
        self.help_menu.setTitle(tr("menu.help"))
        self.theme_menu.setTitle(tr("menu.theme"))
        self.language_menu.setTitle(tr("menu.language"))
        self.profile_menu.setTitle(tr("menu.profile"))
        for name, action in self._theme_actions.items():
            action.setText(tr(f"theme.{name}"))
        self.column_label.setText(tr("panel.filter_column"))
        self.column_combo.setToolTip(tr("panel.filter_column_tip"))
        self.filter_label.setText(tr("panel.filters"))
        self.type_label.setText(tr("panel.object_type"))
        if self.type_combo.count():
            self.type_combo.setItemText(0, tr("panel.all_types"))
        self.flagged_check.setText(tr("panel.only_flagged"))
        self.flagged_check.setToolTip(tr("panel.only_flagged_tip"))
        tab_keys = ("tab.mockup", "tab.sheet", "tab.payload", "tab.validation", "tab.merge", "tab.crossref")
        for index, key in enumerate(tab_keys):
            self.views.setTabText(index, tr(key))
        self.threshold_label.setText(tr("merge.threshold"))
        self.same_group_check.setText(tr("merge.same_group"))
        self.same_group_check.setToolTip(tr("merge.same_group_tip"))
        self.merge_hint.setText(tr("merge.hint"))
        self.preview_button.setText(tr("merge.preview"))
        self.apply_button.setText(tr("merge.apply"))
        self.reset_button.setText(tr("merge.reset"))
        self.merge_selected_button.setText(tr("merge.selected"))
        self._update_merge_state()
        self.merge_export_button.setText(tr("merge.export"))
        columns = ("name", "similarity", "types", "fields", "fit")
        self.merge_tree.setHeaderLabels([tr(f"merge.col.{c}") for c in columns])
        self._fill_merge_tree()
        self.format_label.setText(tr("payload.format"))
        current = self.format_combo.currentIndex()
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        self.format_combo.addItems([tr(key) for key in FORMATS])
        self.format_combo.setCurrentIndex(max(current, 0))
        self.format_combo.blockSignals(False)
        self.copy_button.setText(tr("action.copy"))
        self.save_button.setText(tr("action.save_payload").replace("&", ""))
        self.hint_label.setText(tr("payload.hint"))
        self.statusBar().showMessage(tr("status.ready"))
        self._refresh_views()

    # --- thema en taal / theme and language ------------------------------------------------------------------

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(app_stylesheet(PALETTES[self.theme_name]))

    def _set_theme(self, name: str) -> None:
        self.theme_name = name
        self.settings.set("ui/theme", name)
        self._apply_theme()
        self._refresh_views()

    def _set_profile(self, key: str) -> None:
        self.profile = PROFILES[key]
        self.settings.set("design/profile", key)
        self._rebuild_designs()

    def _set_language(self, code: str) -> None:
        translator.set_language(code)
        self.settings.set("ui/language", code)
        self.retranslate()

    # --- laden / loading -------------------------------------------------------------------------------------

    def _pick_files(self, title_key: str) -> list[str]:
        start = self.settings.string("paths/last", str(Path.home()))
        files, _ = QFileDialog.getOpenFileNames(self, tr(title_key), start, tr("dialog.filter_xlsx"))
        if files:
            self.settings.set("paths/last", str(Path(files[0]).parent))
        return files

    def open_specs(self) -> None:
        files = self._pick_files("dialog.open_spec")
        if files:
            self.load_specs(files, replace=True)

    def add_spec(self) -> None:
        files = self._pick_files("dialog.add_spec")
        if files:
            self.load_specs(files, replace=self.spec is None)

    def load_specs(self, files: list[str], replace: bool) -> None:
        """Lees bestanden op een werkthread en voeg ze samen. / Read files on a worker thread and merge them."""
        if self._busy:
            return
        self._busy = True

        def work(progress: Callable[[str], None]) -> SpecModel:
            merged = SpecModel()
            for path in files:
                progress(tr("status.loading", name=Path(path).name))
                merged.merge(read_spec(path))
            return merged

        job = Job(work)
        job.signals.progress.connect(self.statusBar().showMessage)
        job.signals.finished.connect(lambda result: self._on_loaded(result, len(files), replace))
        job.signals.failed.connect(self._on_load_failed)
        run_job(job)

    def _on_loaded(self, loaded: SpecModel, file_count: int, replace: bool) -> None:
        self._busy = False
        if replace or self.spec is None:
            self.spec = loaded
            self.applied_merges.clear()
        else:
            self.spec.merge(loaded)
        self.spec.filter_column = self.spec.resolve_filter_column(
            self.spec.filter_column or self.settings.string("design/filter_column", ""),
        )
        self._populate_columns()
        self._rebuild_designs()
        self.statusBar().showMessage(
            tr("status.loaded", files=file_count, filters=len(self.tabs), types=len(self.spec.object_types)),
        )

    def _on_load_failed(self, error: object) -> None:
        self._busy = False
        detail = str(error) if isinstance(error, SpecError) else f"{type(error).__name__}: {error}"
        self._warn(tr("error.read_spec", detail=detail))
        self.statusBar().showMessage(tr("status.ready"))

    def load_ids(self) -> None:
        """Kies een veld-ID-bestand (csv, json of iAsset-catalogus xlsx) en lees het op een werkthread.
        Pick a field ID file (csv, json or iAsset catalog xlsx) and read it on a worker thread."""
        start = self.settings.string("paths/last", str(Path.home()))
        file, _ = QFileDialog.getOpenFileName(self, tr("dialog.load_ids"), start, tr("dialog.filter_ids"))
        if file:
            self.load_ids_file(file)

    def load_ids_file(self, path: str) -> None:
        if self._busy:
            return
        self._busy = True
        self.settings.set("paths/last", str(Path(path).parent))
        job = Job(lambda progress: self._read_ids(path, progress))
        job.signals.progress.connect(self.statusBar().showMessage)
        job.signals.finished.connect(self._on_ids_loaded)
        job.signals.failed.connect(self._on_ids_failed)
        run_job(job)

    @staticmethod
    def _read_ids(path: str, progress: Callable[[str], None]) -> FieldIdMap:
        progress(tr("status.loading_ids", name=Path(path).name))
        return FieldIdMap.from_file(path)

    def _on_ids_loaded(self, mapping: object) -> None:
        self._busy = False
        if not isinstance(mapping, FieldIdMap):
            return
        self.ids = mapping
        catalog = mapping.catalog
        if catalog is None:
            message = tr("status.ids_loaded", count=len(mapping), name=mapping.source)
        else:
            message = tr(
                "status.ids_detail", count=len(mapping), name=mapping.source, subthemes=self._subtheme_text(catalog),
            )
        self.statusBar().showMessage(message)
        self._refresh_views()

    @staticmethod
    def _subtheme_text(catalog: FieldCatalog) -> str:
        if catalog.has_subtheme_names:
            return tr("ids.sub_names")
        return tr("ids.sub_ids") if any(info.subthemes for info in catalog.entries.values()) else tr("ids.sub_none")

    def _on_ids_failed(self, error: object) -> None:
        self._busy = False
        log.warning("Field ID file failed: %s", error)
        detail = str(error) if isinstance(error, (FieldMapError, CatalogError)) else f"{type(error).__name__}: {error}"
        self._warn(tr("error.read_ids", detail=detail))
        self.statusBar().showMessage(tr("status.ready"))

    # --- veld-ID-controle / field ID check -------------------------------------------------------------------

    def check_field_ids(self) -> None:
        """Controleer de ontwerpen tegen de geladen catalogus, of vraag om een catalogus-/JSON-bestand.
        Check the designs against the loaded catalog, or ask for a catalog / JSON file."""
        if not self._require_tabs():
            return
        if self.ids is not None and self.ids.catalog is not None:
            choice = self._choose_catalog_source(self.ids.catalog)
            if choice == CATALOG_LOADED:
                self.show_id_check(self.ids.catalog)
            elif choice == CATALOG_OTHER:
                self._pick_comparison_catalog()
            return
        self._pick_comparison_catalog()

    def _choose_catalog_source(self, loaded: FieldCatalog) -> str:
        """Vraag of de geladen catalogus (tegen zichzelf) of een apart vergelijkingsbestand gebruikt wordt; geeft
        ``CATALOG_LOADED``, ``CATALOG_OTHER`` of '' (annuleren). Tests vervangen deze methode.
        Ask whether to use the loaded catalog (against itself) or a separate comparison file; returns
        ``CATALOG_LOADED``, ``CATALOG_OTHER`` or '' (cancel). Tests replace this method."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("idcheck.choose.title"))
        box.setText(tr("idcheck.choose.text", name=loaded.source or "?"))
        use_loaded = box.addButton(tr("idcheck.choose.loaded"), QMessageBox.ButtonRole.AcceptRole)
        other = box.addButton(tr("idcheck.choose.other"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(use_loaded)
        self._exec_dialog(box)
        clicked = box.clickedButton()
        return CATALOG_LOADED if clicked is use_loaded else CATALOG_OTHER if clicked is other else ""

    def _pick_comparison_catalog(self) -> None:
        start = self.settings.string("paths/last", str(Path.home()))
        file, _ = QFileDialog.getOpenFileName(self, tr("dialog.load_ids_catalog"), start, tr("dialog.filter_catalog"))
        if file:
            self.load_catalog_for_check(file)

    def load_catalog_for_check(self, path: str) -> None:
        if self._busy:
            return
        self._busy = True
        self.settings.set("paths/last", str(Path(path).parent))

        def work(progress: Callable[[str], None]) -> FieldCatalog:
            progress(tr("status.loading_ids", name=Path(path).name))
            return load_catalog(path)

        job = Job(work)
        job.signals.progress.connect(self.statusBar().showMessage)
        job.signals.finished.connect(self._on_catalog_for_check)
        job.signals.failed.connect(self._on_catalog_failed)
        run_job(job)

    def _on_catalog_for_check(self, catalog: object) -> None:
        self._busy = False
        self.statusBar().showMessage(tr("status.ready"))
        if isinstance(catalog, FieldCatalog):
            loaded = self.ids.catalog if self.ids is not None else None
            self.show_id_check(self._with_subtheme_names(catalog, loaded))

    @staticmethod
    def _with_subtheme_names(catalog: FieldCatalog, loaded: FieldCatalog | None) -> FieldCatalog:
        """Vul ontbrekende subthemanamen aan uit de geladen catalogus (een JSON kent alleen subthema-id's); de
        originelen blijven ongewijzigd. Fill missing subtheme names from the loaded catalog (JSON only has subtheme
        IDs); the originals stay unchanged."""
        if loaded is None or catalog.has_subtheme_names or not loaded.has_subtheme_names:
            return catalog
        merged = copy.copy(catalog)
        merged.subtheme_names = dict(loaded.subtheme_names)
        merged.invalidate()
        return merged

    def _on_catalog_failed(self, error: object) -> None:
        self._busy = False
        log.warning("Field catalog failed: %s", error)
        detail = str(error) if isinstance(error, (FieldMapError, CatalogError)) else f"{type(error).__name__}: {error}"
        self._warn(tr("error.read_catalog", detail=detail))
        self.statusBar().showMessage(tr("status.ready"))

    def id_check_dialog_for(self, catalog: FieldCatalog) -> IdCheckDialog:
        """Bouw de dialoog zonder die te tonen. / Build the dialog without showing it."""
        return IdCheckDialog(check_ids(self.tabs, catalog, self.ids), self)

    def show_id_check(self, catalog: FieldCatalog) -> None:
        """Controleer op een werkthread en toon daarna de dialoog. / Check on a worker thread, then show the dialog."""
        if self._busy:
            return
        self._busy = True
        tabs, ids = list(self.tabs), self.ids

        def work(progress: Callable[[str], None]) -> list[Any]:
            progress(tr("status.checking_ids"))
            return check_ids(tabs, catalog, ids)

        job = Job(work)
        job.signals.progress.connect(self.statusBar().showMessage)
        job.signals.finished.connect(self._on_ids_checked)
        job.signals.failed.connect(self._on_ids_check_failed)
        run_job(job)

    def _on_ids_checked(self, findings: object) -> None:
        self._busy = False
        self.statusBar().showMessage(tr("status.ready"))
        if isinstance(findings, list):
            self._exec_dialog(IdCheckDialog(findings, self))

    def _on_ids_check_failed(self, error: object) -> None:
        self._busy = False
        log.warning("Field ID check failed: %s", error)
        self._warn(tr("error.id_check", detail=f"{type(error).__name__}: {error}"))
        self.statusBar().showMessage(tr("status.ready"))

    def _exec_dialog(self, dialog: QDialog) -> int:
        """Eén plek om dialogen te tonen (tests vervangen deze). / Single place to show dialogs (tests replace it)."""
        return dialog.exec()

    # --- import van een bijgewerkt Excel-ontwerp / import of a refined Excel design --------------------------

    def import_refined(self) -> None:
        start = self.settings.string("paths/last", str(Path.home()))
        file, _ = QFileDialog.getOpenFileName(self, tr("dialog.import_refined"), start, tr("dialog.filter_xlsx"))
        if file:
            self.load_refined(file)

    def load_refined(self, path: str) -> None:
        """Lees het ontwerp (en het verschil met de specificatie) op een werkthread.
        Read the design (and the difference with the specification) on a worker thread."""
        if self._busy:
            return
        self._busy = True
        self.settings.set("paths/last", str(Path(path).parent))
        job = Job(lambda progress: self.read_refined_with_diff(path, progress))
        job.signals.progress.connect(self.statusBar().showMessage)
        job.signals.finished.connect(self._on_refined_loaded)
        job.signals.failed.connect(self._on_refined_failed)
        run_job(job)

    def read_refined_with_diff(self, path: str, progress: Callable[[str], None] | None = None) -> ImportResult:
        if progress is not None:
            progress(tr("import.loading", name=Path(path).name))
        refined = read_refined(path, self.spec)
        diffs = diff_workbook(refined, self.spec, self.engine) if self.spec and self.engine and refined.sheets else None
        return ImportResult(refined, diffs)

    def _on_refined_failed(self, error: object) -> None:
        self._busy = False
        log.warning("Refined import failed: %s", error)
        self._warn(tr("error.read_refined", detail=f"{type(error).__name__}: {error}"))
        self.statusBar().showMessage(tr("status.ready"))

    def _on_refined_loaded(self, result: object) -> None:
        self._busy = False
        if isinstance(result, ImportResult):
            self.apply_import(result)

    def apply_import(self, result: ImportResult) -> None:
        """Maak de ingelezen bladen het huidige ontwerp. / Make the imported sheets the current design."""
        refined = result.refined
        if not refined.sheets:
            self._warn(tr("error.no_sheets"))
            self.statusBar().showMessage(tr("status.ready"))
            return
        diffs = dict(result.diffs or [])
        self.imported = refined
        self.imported_sheets = [ImportedSheet(sheet, diffs.get(sheet.name)) for sheet in refined.sheets]
        self.tabs = [entry.sheet.tab for entry in self.imported_sheets]
        self._preview = None
        self.back_action.setEnabled(True)
        self._update_merge_state()
        self._fill_filter_list()
        self._update_title()
        self.crossref_panel.show_report(
            refined.path.name, result.diffs, self._import_warnings(), self.spec is not None,
        )
        changes = sum(len(d.entries) for _, d in result.diffs or [])
        key = "import.done" if result.diffs is not None else "import.done_nospec"
        self.statusBar().showMessage(tr(key, sheets=len(refined.sheets), name=refined.path.name, changes=changes))
        self.views.setCurrentWidget(self.mockup)

    def _import_warnings(self) -> list[str]:
        if self.imported is None:
            return []
        warnings = list(self.imported.warnings)
        for entry in self.imported_sheets:
            warnings += [f"{entry.sheet.name}: {w}" for w in entry.sheet.warnings]
        return warnings

    def back_to_generated(self) -> None:
        """Terug naar het uit de specificatie gegenereerde ontwerp. / Back to the design generated from the spec."""
        if self.imported is None:
            return
        self._clear_import()
        if self.spec is not None:
            self._rebuild_designs()
        else:
            self.tabs = []
            self._fill_filter_list()
        self.statusBar().showMessage(tr("import.back_done"))

    def _clear_import(self) -> None:
        self.imported = None
        self.imported_sheets = []
        self.back_action.setEnabled(False)
        self._update_merge_state()
        self.crossref_panel.show_report("", None, [], self.spec is not None)
        self._update_title()

    def _update_merge_state(self) -> None:
        """Samenvoegen alleen bij het gegenereerde ontwerp; een import zou erdoor vervallen.
        Merging only for the generated design; it would discard an import."""
        blocked = self.imported is not None
        tip = tr("merge.imported_disabled")
        for widget in (self.apply_button, self.merge_selected_button, self.reset_button, self.merge_selected_action):
            widget.setEnabled(not blocked)
        self.apply_button.setToolTip(tip if blocked else "")
        self.reset_button.setToolTip(tip if blocked else "")
        self.merge_selected_button.setToolTip(tip if blocked else tr("merge.selected_tip"))
        self.merge_selected_action.setToolTip(tip if blocked else "")
        self.merge_selected_action.setStatusTip(tip if blocked else "")

    def _merge_blocked(self) -> bool:
        if self.imported is None:
            return False
        self.statusBar().showMessage(tr("merge.imported_disabled"))
        return True

    def _update_title(self) -> None:
        title = tr("app.title")
        if self.imported is not None:
            title += f" — {tr('import.window', name=self.imported.path.name)}"
        self.setWindowTitle(title)

    def _imported_entry(self, tab: PassportTab | None) -> ImportedSheet | None:
        return next((e for e in self.imported_sheets if e.sheet.tab is tab), None) if tab is not None else None

    def current_highlights(self, tab: PassportTab | None = None) -> dict[str, str]:
        """Veldnaam -> soort verschil als de markering aan staat en het blad een verschil heeft.
        Field name -> kind of difference when highlighting is on and the sheet has a diff."""
        entry = self._imported_entry(tab or self.current_tab())
        if not self.highlight_action.isChecked() or entry is None or entry.diff is None:
            return {}
        return changed_labels(entry.diff)

    def _on_highlight_toggled(self) -> None:
        self.settings.set("view/highlight_changes", self.highlight_action.isChecked())
        self._refresh_views()

    def _on_extra_tabs_toggled(self) -> None:
        self.mockup.show_extra_tabs = self.extra_tabs_action.isChecked()
        self.settings.set("view/extra_tabs", self.mockup.show_extra_tabs)
        self._refresh_views()

    # --- annotaties / annotations ----------------------------------------------------------------------------

    def check_annotations(self) -> None:
        start = self.settings.string("paths/last", str(Path.home()))
        file, _ = QFileDialog.getOpenFileName(self, tr("dialog.check_annotations"), start, tr("dialog.filter_xlsx"))
        if file:
            self.run_annotation_check(file)

    def run_annotation_check(self, path: str) -> None:
        """Controleer de annotaties op een werkthread en toon de dialoog.
        Check the annotations on a worker thread and show the dialog."""
        if self._busy:
            return
        self._busy = True
        self.settings.set("paths/last", str(Path(path).parent))

        def work(progress: Callable[[str], None]) -> Any:
            from .. import annotations

            progress(tr("import.loading", name=Path(path).name))
            return annotations.check_annotations(path, self.spec, self.engine)

        job = Job(work)
        job.signals.progress.connect(self.statusBar().showMessage)
        job.signals.finished.connect(self._on_annotations_checked)
        job.signals.failed.connect(self._on_annotations_failed)
        run_job(job)

    def _on_annotations_checked(self, report: object) -> None:
        self._busy = False
        self.statusBar().showMessage(tr("status.ready"))
        self._exec_dialog(self.annotation_dialog_for(report))

    def _on_annotations_failed(self, error: object) -> None:
        self._busy = False
        log.warning("Annotation check failed: %s", error)
        self._warn(tr("error.annotations", detail=f"{type(error).__name__}: {error}"))
        self.statusBar().showMessage(tr("status.ready"))

    def annotation_dialog_for(self, report: Any) -> AnnotationDialog:
        """Bouw de annotatiedialoog zonder die te tonen. / Build the annotation dialog without showing it."""

        def fix() -> Any:
            from .. import annotations

            return annotations.fix_annotations(report.path, self.spec, self.engine)

        return AnnotationDialog(report, self.spec is not None, fix, self)

    # --- ontwerp en weergave / design and display ------------------------------------------------------------

    def _populate_columns(self) -> None:
        """Vul de keuzelijst met kolommen van het tabblad 'Objecttypen'. / Fill the 'Objecttypen' column picker."""
        self.column_combo.blockSignals(True)
        self.column_combo.clear()
        if self.spec is not None:
            self.column_combo.addItems(self.spec.columns)
            self.column_combo.setCurrentIndex(max(self.column_combo.findText(self.spec.filter_column), 0))
        self.column_combo.blockSignals(False)

    def set_filter_column(self, column: str) -> None:
        """Groepeer de paspoorten op een andere kolom (bijv. Fase); samenvoegingen vervallen.
        Group the passports by another column (e.g. Fase); applied merges are dropped."""
        if self.spec is None or column == self.spec.filter_column or column not in self.spec.columns:
            return
        self.spec.filter_column = column
        self.settings.set("design/filter_column", column)
        self.applied_merges.clear()
        self._populate_columns()
        self._rebuild_designs()
        files, types = len(self.spec.sources), len(self.spec.object_types)
        self.statusBar().showMessage(tr("status.loaded", files=files, filters=len(self.tabs), types=types))

    def _on_filter_column_changed(self, _index: int) -> None:
        self.set_filter_column(self.column_combo.currentText())

    def _on_flagged_toggled(self, checked: bool) -> None:
        self.settings.set("design/only_flagged", checked)
        if self.spec is not None:
            self._rebuild_designs()

    def _rebuild_designs(self) -> None:
        if self.spec is None:
            return
        if self.imported is not None:
            self._clear_import()
        current = self.current_tab()
        previous = current.name if current else ""
        self._preview = None
        self.engine = LayoutEngine(
            self.spec, LayoutOptions(only_flagged=self.flagged_check.isChecked(), profile=self.profile),
        )
        base = self.engine.build_all()
        self.tabs = apply_merges(self.spec, self.engine, base, self.applied_merges)
        self._update_suggestions()
        self._fill_filter_list(previous)

    def _fill_filter_list(self, previous: str = "") -> None:
        """Vul de paspoortlijst met ``self.tabs`` en kies ``previous`` (of de eerste). / Fill the passport list."""
        self.filter_list.blockSignals(True)
        self.filter_list.clear()
        for tab in self.tabs:
            mark = " ⧉" if tab.merged_from else ""
            self.filter_list.addItem(QListWidgetItem(f"{tab.name} ({len(tab.object_types)}){mark}"))
        self.filter_list.blockSignals(False)
        names = [t.name for t in self.tabs]
        self.filter_list.setCurrentRow(names.index(previous) if previous in names else 0)
        self._on_filter_changed(self.filter_list.currentRow())

    def current_tab(self) -> PassportTab | None:
        if self._preview is not None:
            return self._preview
        row = self.filter_list.currentRow()
        return self.tabs[row] if 0 <= row < len(self.tabs) else None

    def _on_filter_changed(self, _row: int) -> None:
        self._preview = None
        self._populate_types()

    def _populate_types(self) -> None:
        tab = self.current_tab()
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        if tab:
            # Eerst het hele paspoort (zoals de export), daarna per objecttype. / Whole passport first, then per type.
            self.type_combo.addItem(tr("panel.all_types"), "")
            for object_type in tab.object_types:
                self.type_combo.addItem(object_type.name, object_type.name)
        self.type_combo.blockSignals(False)
        self._refresh_views()

    def selected_object_type(self) -> str:
        """Gekozen voorbeeld-objecttype ("" = alle objecttypen). / Chosen preview object type ("" = all)."""
        data = self.type_combo.currentData()
        return data if isinstance(data, str) else ""

    def preview_tab(self) -> PassportTab | None:
        """Het getoonde paspoort: voor één objecttype zonder de velden die daar niet voor gelden.
        The passport shown: for one object type without the fields that do not apply to it."""
        tab = self.current_tab()
        object_type = self.selected_object_type()
        if tab is None or not object_type or self.engine is None or self.imported is not None:
            return tab
        return self.engine.build_single(tab, object_type)

    # --- samenvoegen / merging -------------------------------------------------------------------------------

    def _on_merge_params_changed(self, *_args: object) -> None:
        self.settings.set("merge/threshold", self.threshold_spin.value())
        self.settings.set("merge/same_group", self.same_group_check.isChecked())
        self._update_suggestions()

    def _update_suggestions(self) -> None:
        """Bereken suggesties op de ongemerged filters; reeds toegepaste samenvoegingen verdwijnen uit de lijst.
        Compute suggestions on the unmerged filters; already applied merges disappear from the list."""
        self.suggestions = []
        if self.spec is not None and self.engine is not None:
            applied = {m for _, members in self.applied_merges for m in members}
            found = suggest_merges(
                self.spec, self.engine, self.threshold_spin.value() / 100, self.same_group_check.isChecked(),
            )
            self.suggestions = [s for s in found if not applied & set(s.members)]
        self._fill_merge_tree()

    def _fill_merge_tree(self) -> None:
        self.merge_tree.clear()
        for suggestion in self.suggestions:
            top = QTreeWidgetItem([
                suggestion.name,
                f"{suggestion.similarity:.0%}",
                str(suggestion.object_type_count),
                tr("merge.fields_fmt", common=suggestion.common_fields, partial=suggestion.partial_fields),
                f"{suggestion.lowest_fit:.0%}",
            ])
            if suggestion.low_fit:
                top.setToolTip(4, tr("merge.low_fit_tip"))
                top.setText(4, f"⚠ {suggestion.lowest_fit:.0%}")
            for fit in suggestion.fits:
                member = [fit.filter, "", str(fit.object_types), str(fit.fields), f"{fit.fit:.0%}"]
                top.addChild(QTreeWidgetItem(member))
            self.merge_tree.addTopLevelItem(top)
            top.setExpanded(True)
        for column in range(5):
            self.merge_tree.resizeColumnToContents(column)
        if self.spec is None:
            self.merge_summary.setText(tr("payload.empty"))
        elif not self.suggestions:
            self.merge_summary.setText(tr("merge.none"))
        else:
            saved = sum(s.passports_saved for s in self.suggestions)
            self.merge_summary.setText(tr("merge.summary", count=len(self.suggestions), saved=saved))

    def _selected_suggestion(self) -> MergeSuggestion | None:
        item = self.merge_tree.currentItem()
        if item is None:
            return self.suggestions[0] if self.suggestions else None
        top = item.parent() or item
        index = self.merge_tree.indexOfTopLevelItem(top)
        return self.suggestions[index] if 0 <= index < len(self.suggestions) else None

    def preview_merge(self) -> None:
        suggestion = self._selected_suggestion()
        if suggestion is None or suggestion.tab is None:
            return
        self._preview = suggestion.tab
        self._populate_types()
        self.views.setCurrentIndex(0)
        self.statusBar().showMessage(tr("merge.previewing", name=suggestion.name))

    def _report_merge(self, name: str) -> None:
        """Meld succes alleen als de samenvoeging echt in de ontwerpen zit. / Report success only if really merged."""
        if any(t.name == name and t.merged_from for t in self.tabs):
            self.statusBar().showMessage(tr("merge.applied", name=name))
            return
        self.applied_merges = [m for m in self.applied_merges if m[0] != name]
        self.statusBar().showMessage(tr("merge.not_applied", name=name))

    def apply_selected_merge(self) -> None:
        if self._merge_blocked():
            return
        suggestion = self._selected_suggestion()
        if suggestion is None:
            return
        self.applied_merges.append((suggestion.name, list(suggestion.members)))
        self._rebuild_designs()
        self._report_merge(suggestion.name)

    def _show_filter_menu(self, pos: QPoint) -> None:
        """Contextmenu van de paspoortlijst. / Context menu of the passport list."""
        menu = QMenu(self)
        menu.addAction(self.merge_selected_action)
        viewport = self.filter_list.viewport()
        if viewport is not None:
            menu.exec(viewport.mapToGlobal(pos))

    def _expand_members(self, names: list[str]) -> list[str]:
        """Vervang samengevoegde paspoorten door hun filters. / Replace merged passports by their filters."""
        by_name = {t.name: t for t in self.tabs}
        members: list[str] = []
        for name in names:
            tab = by_name.get(name)
            for member in (tab.merged_from if tab and tab.merged_from else [name]):
                if member not in members:
                    members.append(member)
        return members

    def _taken_names(self, members: list[str]) -> set[str]:
        """Bestaande paspoortnamen, zonder de samen te voegen paspoorten. / Existing names minus those being merged."""
        merging = set(members) | {t.name for t in self.tabs if t.merged_from and set(t.merged_from) & set(members)}
        return {t.name for t in self.tabs if t.name not in merging}

    def _merge_dialog_for(self, names: list[str]) -> MergeDialog | None:
        """Bouw de samenvoegdialoog zonder die te tonen. / Build the merge dialog without showing it."""
        if self.spec is None or self.engine is None:
            return None
        members = self._expand_members(names)
        if len(members) < 2:
            return None
        taken = self._taken_names(members)
        info = manual_merge_info(self.spec, self.engine, members, taken)
        return MergeDialog(info, taken, self)

    def _apply_manual_merge(self, name: str, names: list[str]) -> None:
        """Voeg de paspoorten samen onder ``name``; eerdere samenvoegingen van de leden vervallen.
        Merge the passports under ``name``; earlier merges of those members are replaced."""
        if self._merge_blocked():
            return
        members = self._expand_members(names)
        self.applied_merges = [m for m in self.applied_merges if not set(m[1]) & set(members)]
        self.applied_merges.append((name, members))
        self._rebuild_designs()
        for row, tab in enumerate(self.tabs):
            if tab.name == name:
                self.filter_list.setCurrentRow(row)
        self._report_merge(name)

    def merge_selected(self) -> None:
        """Voeg de geselecteerde paspoorten samen, ongeacht filter of groep. / Merge the selected passports."""
        if self._merge_blocked():
            return
        rows = sorted({self.filter_list.row(i) for i in self.filter_list.selectedItems()})
        names = [self.tabs[r].name for r in rows if 0 <= r < len(self.tabs)]
        dialog = self._merge_dialog_for(names) if len(names) > 1 else None
        if dialog is None:
            self._warn(tr("merge.need_two"))
            return
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_manual_merge(dialog.merge_name(), names)

    def reset_merges(self) -> None:
        if self._merge_blocked():
            return
        self.applied_merges.clear()
        self._rebuild_designs()
        self.statusBar().showMessage(tr("merge.reset_done"))

    def export_merge_matrix(self) -> None:
        if not self.suggestions:
            self._warn(tr("merge.none"))
            return
        path = self._save_path("dialog.save_merge", "Samenvoegadvies.xlsx", "dialog.filter_xlsx")
        if not path:
            return
        try:
            export_merge_report(self.suggestions, path)
        except (OSError, ValueError) as exc:
            log.exception("Merge report export failed")
            self._warn(tr("error.write", detail=str(exc)))
            return
        self.statusBar().showMessage(tr("status.saved", path=path))

    def _refresh_views(self) -> None:
        tab = self.current_tab()
        shown = self.preview_tab()
        entry = self._imported_entry(tab)
        self.mockup.show_tab(
            shown, self.selected_object_type(), PALETTES[self.theme_name],
            entry.sheet.column_widths if entry else None, self.current_highlights(tab),
            entry.sheet.positions if entry else None,
        )
        self.sheet_preview.show_tab(shown)
        self.payload = build_tab_payload(tab, self.ids, self.options) if tab else None
        self._render_payload_text()
        self.validation_list.clear()
        if self.payload is None:
            self.summary_label.setText(tr("payload.empty"))
            return
        self.summary_label.setText(
            tr("payload.summary", resolved=self.payload.resolved_count, total=self.payload.field_count),
        )
        for issue in self.payload.issues:
            severity = tr(f"sev.{issue.severity.value}")
            self.validation_list.addItem(f"{SEVERITY_MARK[issue.severity]} {severity}: {issue.message}")

    def payload_string(self, payload: TabPayload | None = None, fmt: int | None = None) -> str:
        data = payload or self.payload
        if data is None:
            return ""
        index = self.format_combo.currentIndex() if fmt is None else fmt
        if index == 1:
            return to_compact_json(data.body)
        if index == 2:
            return to_form_lines(data.body)
        return to_json(data.body)

    def _render_payload_text(self) -> None:
        text = self.payload_string()
        self.payload_text.setPlainText(f"{ENDPOINT}\n\n{text}" if text else "")

    def _copy_payload(self) -> None:
        text = self.payload_string()
        if text:
            QGuiApplication.clipboard().setText(text)  # type: ignore[union-attr]
            self.statusBar().showMessage(tr("status.copied"))

    # --- exporteren / exporting ------------------------------------------------------------------------------

    def _require_tabs(self) -> bool:
        if not self.tabs:
            self._warn(tr("error.nothing"))
            return False
        return True

    def _save_path(self, title_key: str, default_name: str, pattern_key: str) -> str:
        start = str(Path(self.settings.string("paths/last", str(Path.home()))) / default_name)
        path, _ = QFileDialog.getSaveFileName(self, tr(title_key), start, tr(pattern_key))
        return path

    def _write_text(self, path: str, text: str) -> bool:
        try:
            Path(path).write_text(text, encoding="utf-8")
        except OSError as exc:
            log.exception("Cannot write %s", path)
            self._warn(tr("error.write", detail=str(exc)))
            return False
        return True

    def export_excel(self) -> None:
        if not self._require_tabs():
            return
        path = self._save_path("dialog.save_excel", "Paspoortinrichting.xlsx", "dialog.filter_xlsx")
        if not path:
            return
        try:
            export_workbook(self.tabs, path, spec=self.spec)
        except (OSError, ValueError) as exc:
            log.exception("Excel export failed")
            self._warn(tr("error.write", detail=str(exc)))
            return
        self.statusBar().showMessage(tr("status.saved", path=path))

    def export_excel_per_type(self) -> None:
        """Eén tabblad per objecttype, zonder de velden die niet voor dat objecttype gelden.
        One sheet per object type, without the fields that do not apply to that object type."""
        if not self._require_tabs() or self.engine is None:
            return
        if self.imported is not None:
            self._warn(tr("error.export_imported_types"))
            return
        path = self._save_path("dialog.save_excel", "Paspoortinrichting per objecttype.xlsx", "dialog.filter_xlsx")
        if not path:
            return
        engine = self.engine
        pairs = [(engine.build_single(tab, o.name), o.name) for tab in self.tabs for o in tab.object_types]
        try:
            export_workbook([tab for tab, _ in pairs], path, [name for _, name in pairs], spec=self.spec)
        except (OSError, ValueError) as exc:
            log.exception("Excel export failed")
            self._warn(tr("error.write", detail=str(exc)))
            return
        self.statusBar().showMessage(tr("status.saved", path=path))

    def export_png(self) -> None:
        tab = self.current_tab()
        if tab is None:
            self._require_tabs()
            return
        path = self._save_path("dialog.save_png", f"{safe_filename(tab.name)}.png", "dialog.filter_png")
        if not path:
            return
        if not self.mockup.render_pixmap().save(path, "PNG"):
            log.error("PNG export failed: %s", path)
            self._warn(tr("error.write", detail=path))
            return
        self.statusBar().showMessage(tr("status.saved", path=path))

    def save_payload(self) -> None:
        tab = self.current_tab()
        if tab is None or self.payload is None:
            self._require_tabs()
            return
        path = self._save_path("dialog.save_payload", f"{safe_filename(tab.name)}.json", "dialog.filter_json")
        if path and self._write_text(path, self.payload_string()):
            self.statusBar().showMessage(tr("status.saved", path=path))

    def save_all_payloads(self) -> None:
        if not self._require_tabs():
            return
        folder = QFileDialog.getExistingDirectory(
            self, tr("dialog.save_folder"), self.settings.string("paths/last", str(Path.home())),
        )
        if not folder:
            return
        for tab in self.tabs:
            payload = build_tab_payload(tab, self.ids, self.options)
            target = Path(folder) / f"{safe_filename(tab.name)}.json"
            if not self._write_text(str(target), self.payload_string(payload, fmt=0)):
                return
        self.statusBar().showMessage(tr("status.saved", path=folder))

    # --- overig / misc ---------------------------------------------------------------------------------------

    def edit_payload_settings(self) -> None:
        dialog = PayloadSettingsDialog(self.options, self)
        if dialog.exec():
            self.options = dialog.options()
            self.settings.save_payload_options(self.options)
            self._refresh_views()

    def show_about(self) -> None:
        text = tr("about.text", version=__version__) + f"\n\nLog: {data_dir() / 'passport_designer.log'}"
        QMessageBox.about(self, f"{tr('about.title')} {APP_NAME}", text)

    def _warn(self, message: str) -> None:
        QMessageBox.warning(self, tr("error.title"), message)

    def statusBar(self) -> QStatusBar:  # noqa: N802 - Qt-naam; nooit None na aanmaken / Qt name; never None once created
        bar = super().statusBar()
        return bar if bar is not None else QStatusBar(self)

    def closeEvent(self, a0: QCloseEvent | None) -> None:  # noqa: N802 - Qt-naam / Qt name
        self.settings.set("ui/language", translator.language)
        super().closeEvent(a0)
