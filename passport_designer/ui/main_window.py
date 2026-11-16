"""Hoofdvenster: specificaties laden, ontwerp kiezen, mockup bekijken en API-strings/Excel exporteren.
Main window: load specifications, pick a design, view the mockup and export API strings/Excel."""

from __future__ import annotations

import copy
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QCloseEvent, QFont, QGuiApplication, QKeySequence, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
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
from ..bulk_export import ExportJob, existing, safe_filename
from ..crossref import TabDiff, changed_labels, diff_workbook
from ..dataset_flags import MinimalMark, excluded_labels, minimal_labels, minimal_marks
from ..excel_export import export_merge_report, export_workbook
from ..field_catalog import CatalogError, FieldCatalog, load_catalog
from ..field_map import FieldIdMap, FieldMapError
from ..i18n import LANGUAGES, tr, translator
from ..id_check import check_ids
from ..layout_engine import LayoutEngine, LayoutOptions
from ..layout_overrides import (
    CellRef,
    LayoutFileError,
    LayoutRefused,
    TabOverride,
    add_section,
    apply_layout,
    apply_override,
    deletable_labels,
    delete_empty_row,
    delete_fields,
    from_json,
    insert_row,
    move_cell,
    override_from_dict,
    override_to_dict,
    rename_section,
    reset_layout,
    restore_fields,
    tab_labels,
    toggle_verify,
    with_capture,
)
from ..layout_overrides import to_json as layouts_to_json
from ..merge_advisor import DEFAULT_THRESHOLD, MergeSuggestion, apply_merges, manual_merge_info, suggest_merges
from ..models import PassportTab, SectionStyle, Severity, SpecModel, norm
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
from .bulk_export_panel import BulkExportPanel, BulkOptions
from .bulk_exporter import BulkExporter, ExportReport
from .crossref_panel import CrossRefPanel
from .id_check_dialog import IdCheckDialog
from .merge_dialog import MergeDialog
from .mockup import PassportMockup, render_tab_pixmap
from .restore_dialog import RestoreDialog
from .settings_dialog import PayloadSettingsDialog
from .sheet_preview import SheetPreview
from .theme import PALETTES, app_stylesheet, qt_palette
from .workers import Job, run_job

log = logging.getLogger(__name__)

CATALOG_LOADED, CATALOG_OTHER = "loaded", "other"
FORMATS = ("payload.fmt_json", "payload.fmt_compact", "payload.fmt_form")
SEVERITY_MARK = {Severity.INFO: "ℹ", Severity.WARNING: "⚠", Severity.ERROR: "⛔"}


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
        # Handmatige markeringen en verwijderingen per paspoortnaam, plus een stapel om ongedaan te maken.
        # Manual marks and deletions per passport name, plus a stack for undo.
        self.overrides: dict[str, TabOverride] = {}
        self._undo_stack: list[dict[str, TabOverride]] = []
        self._redo_stack: list[dict[str, TabOverride]] = []
        # Alle bewaarde indelingen (ook van andere profielen), sleutel 'profiel|paspoortnaam'; automatisch bewaard
        # na 500 ms rust. / All stored layouts (other profiles too), key 'profile|passport name'; autosaved after
        # 500 ms of rest.
        self._layout_store: dict[str, TabOverride] = {}
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._save_layouts)
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
        left_layout.addWidget(self.filter_label)
        left_layout.addWidget(self.filter_list, 1)
        for widget in (self.type_label, self.type_combo):
            left_layout.addWidget(widget)
        splitter.addWidget(left)

        self.views = QTabWidget()
        self.mockup = PassportMockup()
        self.mockup.show_extra_tabs = self.settings.boolean("view/extra_tabs", True)
        self.views.addTab(self.mockup, "")
        self.sheet_preview = SheetPreview()
        self.sheet_preview.move_requested.connect(self._on_move_requested)
        self.sheet_preview.insert_row_requested.connect(self._on_insert_row)
        self.sheet_preview.delete_row_requested.connect(self._on_delete_row)
        self.sheet_preview.add_section_requested.connect(self._on_add_section)
        self.sheet_preview.rename_section_requested.connect(self._on_rename_section)
        self.sheet_preview.reset_requested.connect(self._on_reset_layout)
        self.views.addTab(self.sheet_preview, "")
        self.views.addTab(self._build_payload_tab(), "")
        self.validation_list = QListWidget()
        self.validation_list.setWordWrap(True)
        self.views.addTab(self.validation_list, "")
        self.views.addTab(self._build_merge_tab(), "")
        self.crossref_panel = CrossRefPanel()
        self.views.addTab(self.crossref_panel, "")
        self.bulk_panel = BulkExportPanel()
        self.bulk_panel.set_folders(
            self.settings.string("paths/bulk_tabs", ""), self.settings.string("paths/bulk_types", ""),
        )
        self.bulk_panel.folders_changed.connect(self._remember_bulk_folders)
        self.bulk_panel.export_requested.connect(self._start_bulk_export)
        self.bulk_panel.cancel_requested.connect(self._cancel_bulk_export)
        self.views.addTab(self.bulk_panel, "")
        self.views.currentChanged.connect(self._on_view_changed)
        self._bulk: BulkExporter | None = None
        self._bulk_folder = ""
        # Werkbalkrij boven de weergaven met de Opnemen-schakelaar / Toolbar row above the views with the Opnemen toggle
        self.only_included_check = QCheckBox()
        self.only_included_check.setChecked(self.settings.boolean("design/only_flagged", True))
        self.only_included_check.toggled.connect(self._set_only_included)
        self.minimal_check = QCheckBox()
        self.minimal_check.setChecked(self.settings.boolean("view/minimal_dataset", False))
        self.minimal_check.toggled.connect(self._set_minimal)
        toolbar_row = QHBoxLayout()
        toolbar_row.setContentsMargins(0, 0, 0, 0)
        toolbar_row.addWidget(self.only_included_check)
        toolbar_row.addWidget(self.minimal_check)
        toolbar_row.addStretch(1)
        views_holder = QWidget()
        views_layout = QVBoxLayout(views_holder)
        views_layout.setContentsMargins(0, 0, 0, 0)
        views_layout.addLayout(toolbar_row)
        views_layout.addWidget(self.views, 1)
        splitter.addWidget(views_holder)
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
        self.edit_menu = bar.addMenu("") or QMenu()
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
        self.only_included_action = self._action("action.only_included", self._on_only_included_action, "Ctrl+Alt+O")
        self.only_included_action.setCheckable(True)
        self.only_included_action.setChecked(self.settings.boolean("design/only_flagged", True))
        self.view_menu.addAction(self.highlight_action)
        self.view_menu.addAction(self.extra_tabs_action)
        self.view_menu.addAction(self.only_included_action)
        self.minimal_action = self._action("action.minimal_dataset", self._on_minimal_action, "Ctrl+Shift+M")
        self.minimal_action.setCheckable(True)
        self.minimal_action.setChecked(self.settings.boolean("view/minimal_dataset", False))
        self.view_menu.addAction(self.minimal_action)
        self.verify_marks_action = self._action("action.verify_marks", self._on_verify_marks_toggled)
        self.verify_marks_action.setCheckable(True)
        self.verify_marks_action.setChecked(self.settings.boolean("view/verify_marks", True))
        self.view_menu.addAction(self.verify_marks_action)
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

        self.mark_action = self._action("verify.mark", self.mark_verify_selected, "Ctrl+Shift+V")
        self.delete_action = self._action("verify.delete", self.delete_selected, "Del")
        self.delete_marked_action = self._action("verify.delete_marked", self.delete_all_marked)
        self.restore_action = self._action("verify.restore", self.restore_dialog)
        self.undo_action = self._action("verify.undo", self.undo_override, QKeySequence.StandardKey.Undo)
        self.undo_action.setEnabled(False)
        self.redo_action = self._action("layout.redo", self.redo_override, QKeySequence.StandardKey.Redo)
        self.redo_action.setEnabled(False)
        self.save_layout_action = self._action("layout.save", self.save_layout)
        self.load_layout_action = self._action("layout.load", self.load_layout_dialog)
        self.file_menu.insertAction(self.merge_selected_action, self.save_layout_action)
        self.file_menu.insertAction(self.merge_selected_action, self.load_layout_action)
        self.file_menu.insertSeparator(self.merge_selected_action)
        for action in (self.mark_action, self.delete_action, self.delete_marked_action, self.restore_action):
            self.edit_menu.addAction(action)
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(self.undo_action)
        self.edit_menu.addAction(self.redo_action)

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
        self.bulk_panel.retranslate()
        self.file_menu.setTitle(tr("menu.file"))
        self.view_menu.setTitle(tr("menu.view"))
        self.edit_menu.setTitle(tr("menu.edit"))
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
        self.only_included_check.setText(tr("action.only_included"))
        self.only_included_check.setToolTip(tr("action.only_included_tip"))
        self.minimal_check.setText(tr("action.minimal_dataset").replace("&", ""))
        tab_keys = (
            "tab.mockup", "tab.sheet", "tab.payload", "tab.validation", "tab.merge", "tab.crossref",
            "tab.bulk_export")
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
        """Het gekozen thema wint van de Windows-modus: palet, kleurenschema en stijlblad. / The chosen theme wins
        over the Windows mode: palette, colour scheme and stylesheet."""
        app = QApplication.instance()
        if isinstance(app, QApplication):
            palette = PALETTES[self.theme_name]
            hints = app.styleHints()
            if hints is not None and hasattr(hints, "setColorScheme"):  # Qt 6.8 en later / Qt 6.8 and later
                hints.setColorScheme(Qt.ColorScheme.Light if palette.name == "light" else Qt.ColorScheme.Dark)
            app.setPalette(qt_palette(palette))
            app.setStyleSheet(app_stylesheet(palette))

    def _set_theme(self, name: str) -> None:
        self.theme_name = name
        self.settings.set("ui/theme", name)
        self._apply_theme()
        self._refresh_views()

    def _set_profile(self, key: str) -> None:
        self._flush_layouts()  # de indeling hoort bij het profiel / the layout belongs to the profile
        self.profile = PROFILES[key]
        self.settings.set("design/profile", key)
        if self.spec is not None:
            self._reset_overrides()
            self._load_layouts()
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
            self._reset_overrides()
        else:
            self.spec.merge(loaded)
        self.spec.filter_column = self.spec.resolve_filter_column(
            self.spec.filter_column or self.settings.string("design/filter_column", ""),
        )
        if replace:
            self._load_layouts()
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
        cancel = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(cancel)
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
        self._reset_overrides()
        for entry in self.imported_sheets:
            restored = self._imported_override(entry.sheet)
            if restored is not None:
                self.overrides[entry.sheet.tab.name] = restored
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
        self._reset_overrides()
        if self.spec is not None:
            self._load_layouts()
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
        # NL: Titel met versie, bv. "... v0.5.0 — bestand". / EN: Title with version, e.g. "... v0.5.0 — file".
        title = f"{tr('app.title')} v{__version__}"
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

    def _on_only_included_action(self) -> None:
        self._set_only_included(self.only_included_action.isChecked())

    def _set_only_included(self, checked: bool) -> None:
        """Zet de Opnemen-schakelaar (werkbalk en menu synchroon), bewaar de keuze en bouw de ontwerpen opnieuw.
        Set the Opnemen toggle (toolbar and menu in sync), save the choice and rebuild the designs."""
        for widget in (self.only_included_check, self.only_included_action):
            widget.blockSignals(True)
            widget.setChecked(checked)
            widget.blockSignals(False)
        self.settings.set("design/only_flagged", checked)
        if self.spec is not None:
            self._rebuild_designs()
        else:
            self._refresh_views()

    def _on_minimal_action(self) -> None:
        self._set_minimal(self.minimal_action.isChecked())

    def _set_minimal(self, checked: bool) -> None:
        """Zet de schakelaar 'Minimale dataset markeren' (werkbalk en menu synchroon) en bewaar de keuze.
        Set the 'Highlight minimal dataset' toggle (toolbar and menu in sync) and save the choice."""
        for widget in (self.minimal_check, self.minimal_action):
            widget.blockSignals(True)
            widget.setChecked(checked)
            widget.blockSignals(False)
        self.settings.set("view/minimal_dataset", checked)
        self._refresh_views()

    def _minimal_available(self) -> bool:
        return self.spec is not None and self.spec.has_minimal_flags

    def _minimal_on(self) -> bool:
        return self.minimal_check.isChecked() and self._minimal_available()

    def _minimal_info(
        self, tab: PassportTab | None, object_type: str = "", *, on: bool | None = None,
    ) -> tuple[dict[str, MinimalMark], dict[str, str]]:
        """(markeringen, legenda) voor ``tab`` als de schakelaar aan staat en de spec de kolom heeft; anders leeg.
        (marks, legend) for ``tab`` when the toggle is on and the spec has the column; otherwise empty."""
        wanted = self.minimal_check.isChecked() if on is None else on
        if tab is None or self.spec is None or not wanted or not self._minimal_available():
            return {}, {}
        labels = minimal_labels(self.spec, tab=tab, object_type=object_type or None)
        types = [object_type] if object_type else [o.name for o in tab.object_types]
        return minimal_marks(labels, tab_types=types)

    def _update_minimal_state(self) -> None:
        """Zonder MinimaleDataset-kolom is de schakelaar uitgeschakeld met uitleg. / Without a MinimaleDataset column
        the toggle is disabled with an explanation."""
        available = self._minimal_available()
        tip = tr("action.minimal_dataset_tip") if available else tr("minimal.unavailable")
        for widget in (self.minimal_check, self.minimal_action):
            widget.setEnabled(available)
            widget.setToolTip(tip)

    # --- markeren en verwijderen / marking and deleting -----------------------------------------------------

    def _effective(
        self, tab: PassportTab | None, *, keep_empty: bool = False,
    ) -> tuple[PassportTab | None, set[str]]:
        """Het paspoort met de gebruikersindeling en zonder verwijderde velden, plus de gemarkeerde veldnamen. Eén
        plek voor alle uitvoer (mockup, ontwerpblad, Excel, PNG, payload). / The passport with the user layout and
        without deleted fields, plus the marked field names. One place for all output (mockup, design sheet, Excel,
        PNG, payload)."""
        if tab is None:
            return None, set()
        return apply_override(tab, self.overrides.get(tab.name, TabOverride()), keep_empty=keep_empty)

    def _single_tab(self, tab: PassportTab, object_type: str) -> PassportTab:
        """Het paspoort voor één objecttype, met dezelfde indeling en verwijderingen. / The passport for one object
        type, with the same layout and deletions."""
        if self.engine is None or self.imported is not None:
            return self._effective(tab)[0] or tab
        single = self.engine.build_single(tab, object_type)
        return apply_override(single, self.overrides.get(tab.name, TabOverride()))[0]

    def _reset_overrides(self) -> None:
        self.overrides.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()

    def _change_override(self, change: Callable[[TabOverride], TabOverride]) -> None:
        """Pas het huidige paspoort aan, met een momentopname voor ongedaan maken. / Change the current passport, with
        a snapshot for undo."""
        tab = self.current_tab()
        if tab is None:
            return
        current = self.overrides.get(tab.name, TabOverride())
        updated = change(current)
        if updated == current:
            return
        self._undo_stack.append(dict(self.overrides))
        del self._undo_stack[:-50]
        self._redo_stack.clear()
        if updated.is_empty:
            self.overrides.pop(tab.name, None)
        else:
            self.overrides[tab.name] = updated
        self._schedule_save()
        self._refresh_views()

    def undo_override(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(dict(self.overrides))
        self.overrides = self._undo_stack.pop()
        self._schedule_save()
        self._refresh_views()

    def redo_override(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(dict(self.overrides))
        self.overrides = self._redo_stack.pop()
        self._schedule_save()
        self._refresh_views()

    # --- indeling: slepen en neerzetten / layout: drag and drop ----------------------------------------------

    def _edit_layout(self, change: Callable[[TabOverride], TabOverride]) -> None:
        """Pas de indeling van het getoonde paspoort aan; weigeringen komen in de statusbalk. / Change the layout of
        the shown passport; refusals go to the status bar."""
        tab = self.current_tab()
        if tab is None:
            return
        if self.selected_object_type():
            self.statusBar().showMessage(tr("layout.pick_all_types"))
            return
        displayed = self._effective(tab, keep_empty=True)[0]
        if displayed is None:
            return
        base = with_capture(self.overrides.get(tab.name, TabOverride()), displayed)
        try:
            updated = change(base)
        except LayoutRefused as exc:
            self.statusBar().showMessage(tr(f"layout.{exc.code}", max=tab.profile.grid_columns))
            return
        if updated.layout == base.layout:
            return
        self._change_override(lambda _current: updated)

    def _on_move_requested(self, source: object, target: object) -> None:
        tab = self.current_tab()
        if tab is None or not isinstance(source, CellRef) or not isinstance(target, CellRef):
            return
        columns = tab.profile.grid_columns
        self._edit_layout(lambda o: move_cell(o, source=source, target=target, max_columns=columns))

    def _on_insert_row(self, section: int, row: int) -> None:
        self._edit_layout(lambda o: insert_row(o, section=section, row=row))

    def _on_delete_row(self, section: int, row: int) -> None:
        self._edit_layout(lambda o: delete_empty_row(o, section=section, row=row))

    def _ask_section(self, title: str = "", *, with_style: bool = True) -> tuple[str, SectionStyle] | None:
        """Vraag titel (en stijl) van een sectie; None bij annuleren. / Ask the title (and style) of a section; None
        on cancel."""
        text, ok = QInputDialog.getText(self, tr("app.title"), tr("layout.section_prompt"), text=title)
        if not ok:
            return None
        style = SectionStyle.PLAIN
        if with_style:
            labels = [tr("layout.style_plain"), tr("layout.style_semantic")]
            choice, ok = QInputDialog.getItem(self, tr("app.title"), tr("layout.style_prompt"), labels, 0, False)
            if not ok:
                return None
            style = SectionStyle.SEMANTIC if choice == labels[1] else SectionStyle.PLAIN
        return text, style

    def _on_add_section(self, after: int) -> None:
        if self.selected_object_type():
            self.statusBar().showMessage(tr("layout.pick_all_types"))
            return
        asked = self._ask_section()
        if asked is not None:
            title, style = asked
            self._edit_layout(lambda o: add_section(o, after=after, title=title, style=style))

    def _on_rename_section(self, section: int) -> None:
        shown = self._effective(self.current_tab(), keep_empty=True)[0]
        if shown is None or self.selected_object_type() or not 0 <= section < len(shown.sections):
            self.statusBar().showMessage(tr("layout.pick_all_types"))
            return
        asked = self._ask_section(shown.sections[section].title, with_style=False)
        if asked is not None:
            self._edit_layout(lambda o: rename_section(o, section=section, title=asked[0]))

    def _on_reset_layout(self) -> None:
        self._change_override(reset_layout)
        self.statusBar().showMessage(tr("layout.reset_done"))

    # --- indeling: bewaren / layout: persistence -------------------------------------------------------------

    def _layout_key(self, tab_name: str) -> str:
        return f"{self.profile.key}|{tab_name}"

    def _layout_file(self) -> Path | None:
        """Bestand voor de huidige specificaties (vingerafdruk = gesorteerde bronbestandsnamen). / File for the
        current specifications (fingerprint = sorted source file names)."""
        if self.spec is None:
            return None
        digest = hashlib.sha1("\n".join(sorted(self.spec.sources)).encode("utf-8")).hexdigest()[:16]
        return self.settings.layouts_dir() / f"{digest}.json"

    def _imported_override(self, sheet: RefinedSheet) -> TabOverride | None:
        """Markeringen en indeling uit een ingelezen blad. / Marks and layout from an imported sheet."""
        stored = TabOverride()
        if sheet.layout:
            try:
                stored = override_from_dict(sheet.layout)
            except LayoutFileError:
                log.warning("Layout metadata of sheet %s is not usable", sheet.name)
        verify = frozenset(sheet.verify) | stored.verify
        result = replace(stored, verify=verify, deleted=frozenset())
        return None if result.is_empty else result

    def _load_layouts(self) -> None:
        """Lees de bewaarde indeling bij de huidige specificaties; onleesbaar = negeren. / Read the stored layout for
        the current specifications; unreadable = ignore."""
        self._layout_store = {}
        path = self._layout_file()
        if path is not None and path.exists():
            try:
                self._layout_store = from_json(path.read_text(encoding="utf-8"))
            except (OSError, LayoutFileError):
                log.warning("Stored layout %s is not usable and is ignored", path)
        self._apply_store()

    def _apply_store(self) -> None:
        prefix = self._layout_key("")
        self.overrides = {k[len(prefix):]: o for k, o in self._layout_store.items() if k.startswith(prefix)}
        self._undo_stack.clear()
        self._redo_stack.clear()

    def _schedule_save(self) -> None:
        if self.imported is None and self.spec is not None:
            self._save_timer.start()

    def _flush_layouts(self) -> None:
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save_layouts()

    def _collect_store(self) -> dict[str, TabOverride]:
        prefix = self._layout_key("")
        store = {k: o for k, o in self._layout_store.items() if not k.startswith(prefix)}
        store.update({self._layout_key(name): o for name, o in self.overrides.items() if not o.is_empty})
        return store

    def _save_layouts(self) -> None:
        """Bewaar de indeling (zonder geheimen) in de app-gegevensmap. / Store the layout (no secrets) in the app data
        folder."""
        path = self._layout_file()
        if path is None or self.imported is not None:
            return
        self._layout_store = self._collect_store()
        try:
            path.write_text(layouts_to_json(self._layout_store), encoding="utf-8")
        except OSError:
            log.exception("Cannot store the layout in %s", path)

    def save_layout(self) -> None:
        """Bestand → Indeling opslaan…: wissel de indeling uit als JSON. / Save the layout as a JSON file."""
        if not self._require_tabs():
            return
        path = self._save_path("layout.save", "Layout.json", "layout.filter")
        if path:
            self.write_layout_file(path)

    def write_layout_file(self, path: str) -> None:
        if self._write_text(path, layouts_to_json(self._collect_store())):
            self.statusBar().showMessage(tr("layout.saved", path=path))

    def load_layout_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("layout.load"), self.settings.string("paths/last", str(Path.home())), tr("layout.filter"),
        )
        if path:
            self.load_layout(path)

    def load_layout(self, path: str) -> None:
        """Lees een indelingsbestand; een fout laat de huidige indeling ongemoeid. / Read a layout file; an error leaves
        the current layout untouched."""
        try:
            loaded = from_json(Path(path).read_text(encoding="utf-8"))
        except OSError as exc:
            self._warn(tr("layout.file_error", detail=str(exc)))
            return
        except LayoutFileError as exc:
            self._warn(tr("layout.file_error", detail=str(exc)))
            return
        self._undo_stack.append(dict(self.overrides))
        self._redo_stack.clear()
        self._layout_store = {**self._collect_store(), **loaded}
        prefix = self._layout_key("")
        self.overrides = {k[len(prefix):]: o for k, o in self._layout_store.items() if k.startswith(prefix)}
        self._schedule_save()
        self._refresh_views()
        self.statusBar().showMessage(tr("layout.loaded", count=len(loaded)))

    def _selected_labels(self) -> list[str]:
        return self.sheet_preview.selected_labels()

    def mark_verify_selected(self) -> None:
        self._mark_labels(self._selected_labels())

    def delete_selected(self) -> None:
        self._delete_labels(self._selected_labels())

    def _mark_labels(self, labels: list[str]) -> None:
        self._change_override(lambda o: toggle_verify(o, labels=labels))

    def _delete_labels(self, labels: list[str]) -> None:
        tab = self.current_tab()
        if tab is None or not labels:
            return
        allowed = deletable_labels(tab, labels)
        refused = [name for key, name in tab_labels(tab).items() if key in {norm(name) for name in labels} - allowed]
        if refused:
            self.statusBar().showMessage(tr("verify.protected", fields=", ".join(refused)))
        if allowed:
            self._change_override(lambda o: delete_fields(o, labels=allowed))

    def delete_all_marked(self) -> None:
        tab = self.current_tab()
        if tab is None:
            return
        override = self.overrides.get(tab.name, TabOverride())
        present = deletable_labels(tab, override.verify & set(tab_labels(tab)))
        if not present:
            self.statusBar().showMessage(tr("verify.none_marked"))
            return
        answer = QMessageBox.question(
            self, tr("app.title"), tr("verify.confirm", count=len(present), tab=tab.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._change_override(lambda o: delete_fields(o, labels=present))

    def restore_dialog(self) -> None:
        tab = self.current_tab()
        if tab is None:
            return
        deleted = self.overrides.get(tab.name, TabOverride()).deleted
        if not deleted:
            self.statusBar().showMessage(tr("verify.nothing_deleted"))
            return
        names = tab_labels(tab)
        dialog = RestoreDialog({key: names.get(key, key) for key in sorted(deleted)}, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.chosen():
            self._change_override(lambda o: restore_fields(o, labels=dialog.chosen()))

    def _on_verify_marks_toggled(self) -> None:
        self.settings.set("view/verify_marks", self.verify_marks_action.isChecked())
        self._refresh_views()

    def _export_overrides(self) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        """Gemarkeerde en verwijderde velden per paspoortnaam voor de export. / Marked and deleted fields per passport
        name for the export."""
        show = self.verify_marks_action.isChecked()
        verify = {t.name: (self._effective(t)[1] if show else set()) for t in self.tabs}
        deleted = {t.name: set(o.deleted) for t in self.tabs if (o := self.overrides.get(t.name))}
        return verify, deleted

    def _muted_labels(self, tab: PassportTab | None) -> set[str]:
        """Genormaliseerde veldnamen met Opnemen = Nee die grijs getoond worden (alleen in de modus 'alle velden').
        Normalised field names with Opnemen = Nee to show grey (only in the 'all fields' mode)."""
        if tab is None or self.spec is None or self.only_included_check.isChecked():
            return set()
        return excluded_labels(self.spec, tab=tab)

    def _rebuild_designs(self) -> None:
        if self.spec is None:
            return
        if self.imported is not None:
            self._clear_import()
        current = self.current_tab()
        previous = current.name if current else ""
        object_type = self.selected_object_type()
        self._preview = None
        self.engine = LayoutEngine(
            self.spec, LayoutOptions(only_flagged=self.only_included_check.isChecked(), profile=self.profile),
        )
        base = self.engine.build_all()
        self.tabs = apply_merges(self.spec, self.engine, base, self.applied_merges)
        self._update_suggestions()
        self._fill_filter_list(previous)
        index = self.type_combo.findData(object_type)
        if object_type and index >= 0:  # de gekozen objecttype blijft gekozen / keep the chosen object type
            self.type_combo.setCurrentIndex(index)

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
        self.bulk_panel.set_tabs(self.tabs)

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
        if tab is None:
            return None
        if not object_type or self.engine is None or self.imported is not None:
            return self._effective(tab, keep_empty=True)[0]
        return self._single_tab(tab, object_type)

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
        base = self.current_tab()
        tab, verify_all = self._effective(base)
        shown = self.preview_tab()
        verify = verify_all if self.verify_marks_action.isChecked() else set()
        entry = self._imported_entry(base)
        deleted = bool(base is not None and self.overrides.get(base.name, TabOverride()).deleted)
        modified = deleted or bool(base is not None and self.overrides.get(base.name, TabOverride()).layout)
        muted = self._muted_labels(shown)
        self._update_minimal_state()
        self.undo_action.setEnabled(bool(self._undo_stack))
        self.redo_action.setEnabled(bool(self._redo_stack))
        self.sheet_preview.editable = base is not None and not self.selected_object_type()
        marks, legend = self._minimal_info(shown, self.selected_object_type())
        self.mockup.show_tab(
            shown, self.selected_object_type(), PALETTES[self.theme_name],
            entry.sheet.column_widths if entry and not modified else None, self.current_highlights(base),
            entry.sheet.positions if entry and not modified else None,
            muted=muted, minimal=marks, legend=legend, verify=verify,
        )
        self.sheet_preview.show_tab(shown, muted=muted, minimal=marks, legend=legend, verify=verify)
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
        if self.spec is not None:
            for name in self.spec.orphan_types():
                self.validation_list.addItem(
                    f"{SEVERITY_MARK[Severity.WARNING]} {tr('sev.warning')}: {tr('spec.orphan', name=name)}",
                )
        if base is not None:
            override = self.overrides.get(base.name, TabOverride())
            if override.layout is not None:
                _, layout_warnings, layout_infos = apply_layout(base, override)
                for severity, items in ((Severity.WARNING, layout_warnings), (Severity.INFO, layout_infos)):
                    for message in items:
                        self.validation_list.addItem(
                            f"{SEVERITY_MARK[severity]} {tr(f'sev.{severity.value}')}: {message}",
                        )
            names = tab_labels(base)
            for key in sorted(override.deleted):
                message = tr("verify.deleted_info", field=names.get(key, key))
                self.validation_list.addItem(f"{SEVERITY_MARK[Severity.INFO]} {tr('sev.info')}: {message}")

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
            verify, deleted = self._export_overrides()
            export_workbook(
                [self._effective(t)[0] or t for t in self.tabs], path, spec=self.spec,
                only_included=self.only_included_check.isChecked(),
                minimal_by_tab={t.name: self._minimal_info(self._effective(t)[0] or t) for t in self.tabs}
                if self._minimal_on() else None,
                verify_by_tab=verify, deleted_by_tab=deleted,
                layout_by_tab={
                    t.name: override_to_dict(o) for t in self.tabs if (o := self.overrides.get(t.name)) and o.layout
                },
            )
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
        verify, deleted = self._export_overrides()
        pairs: list[tuple[PassportTab, str]] = []
        verify_by_name: dict[str, set[str]] = {}
        deleted_by_name: dict[str, set[str]] = {}
        for tab in self.tabs:
            for o in tab.object_types:
                single = self._single_tab(tab, o.name)
                pairs.append((single, o.name))
                verify_by_name[o.name] = verify.get(tab.name, set()) & set(tab_labels(single))
                deleted_by_name[o.name] = deleted.get(tab.name, set())
        try:
            export_workbook(
                [tab for tab, _ in pairs], path, [name for _, name in pairs], spec=self.spec,
                only_included=self.only_included_check.isChecked(),
                minimal_by_tab=(
                    {o.name: self._minimal_info(tab, o.name) for tab in self.tabs for o in tab.object_types}
                    if self._minimal_on() else None
                ),
                verify_by_tab=verify_by_name, deleted_by_tab=deleted_by_name,
            )
        except (OSError, ValueError) as exc:
            log.exception("Excel export failed")
            self._warn(tr("error.write", detail=str(exc)))
            return
        self.statusBar().showMessage(tr("status.saved", path=path))

    # --- bulk-export van PNG's / bulk PNG export ---------------------------------------------------------------

    def _on_view_changed(self, _index: int) -> None:
        """Bij het openen van het tabblad Bulkexport: opties volgen de huidige weergave. / On opening the Bulk
        export tab: options follow the current view."""
        if self.views.currentWidget() is self.bulk_panel and self._bulk is None:
            self.bulk_panel.set_options(
                dark=self.theme_name == "dark", only_included=self.only_included_check.isChecked(),
                minimal=self.minimal_check.isChecked(), minimal_available=self._minimal_available(),
                verify=self.verify_marks_action.isChecked(), extra_tabs=self.mockup.show_extra_tabs,
            )

    def _remember_bulk_folders(self, tab_folder: str, type_folder: str) -> None:
        self.settings.set("paths/bulk_tabs", tab_folder)
        self.settings.set("paths/bulk_types", type_folder)

    def _bulk_renderer(self, options: BulkOptions) -> Callable[[ExportJob], QPixmap]:
        """Een functie die één taak tekent met precies deze opties, zonder de weergave te wijzigen. De indeling,
        verwijderingen en markeringen van de gebruiker gelden ook. / A function that draws one job with exactly
        these options without changing the view. The user's layout, deletions and marks apply too."""
        spec, palette = self.spec, PALETTES["dark" if options.dark else "light"]
        if (self.engine is None or spec is None or self.imported is not None
                or options.only_included == self.only_included_check.isChecked()):
            engine, tabs = self.engine, self.tabs
        else:
            engine = LayoutEngine(spec, LayoutOptions(only_flagged=options.only_included, profile=self.profile))
            tabs = apply_merges(spec, engine, engine.build_all(), self.applied_merges)
        by_name = {t.name: t for t in tabs}

        def render(job: ExportJob) -> QPixmap:
            base = by_name[job.passport]
            if job.object_type is not None and engine is not None and self.imported is None:
                base = engine.build_single(base, job.object_type)
            shown, marked = apply_override(base, self.overrides.get(job.passport, TabOverride()))
            marks, legend = self._minimal_info(shown, job.object_type or "", on=options.minimal)
            muted = excluded_labels(spec, tab=shown) if spec is not None and not options.only_included else set()
            return render_tab_pixmap(
                tab=shown, object_type=job.object_type, palette=palette, minimal=marks, legend=legend, muted=muted,
                verify=marked if options.verify else set(), show_extra_tabs=options.extra_tabs,
            )

        return render

    def _start_bulk_export(self, jobs: list[ExportJob], options: BulkOptions) -> None:
        if self._bulk is not None or not jobs:
            return
        skipped = 0
        clashes = existing(jobs)
        if clashes:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setText(tr("bulk.exists", count=len(clashes)))
            overwrite = box.addButton(tr("bulk.overwrite_all"), QMessageBox.ButtonRole.AcceptRole)
            skip = box.addButton(tr("bulk.skip_existing"), QMessageBox.ButtonRole.ActionRole)
            box.addButton(tr("bulk.cancel"), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked is skip:
                keep = [j for j in jobs if j not in clashes]
                skipped, jobs = len(jobs) - len(keep), keep
            elif clicked is not overwrite:
                return
        parents = {str(j.path.parent) for j in jobs}
        self._bulk_folder = next(iter(parents)) if len(parents) == 1 else self.bulk_panel.tab_folder_edit.text()
        exporter = BulkExporter(jobs, self._bulk_renderer(options), skipped=skipped, parent=self)
        self._bulk = exporter
        exporter.progress.connect(self.bulk_panel.show_progress)
        exporter.finished.connect(self._bulk_finished)
        self.bulk_panel.set_running(True)
        exporter.start()

    def _cancel_bulk_export(self) -> None:
        if self._bulk is not None:
            self._bulk.cancel()

    def _bulk_finished(self, report: ExportReport) -> None:
        folder = self._bulk_folder
        self._bulk = None
        self.bulk_panel.set_running(False)
        self.bulk_panel.show_report(report, folder)
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
            payload = build_tab_payload(self._effective(tab)[0] or tab, self.ids, self.options)
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
        self._flush_layouts()
        self.settings.set("ui/language", translator.language)
        super().closeEvent(a0)
