"""Hoofdvenster: specificaties laden, ontwerp kiezen, mockup bekijken en API-strings/Excel exporteren.
Main window: load specifications, pick a design, view the mockup and export API strings/Excel."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup, QCloseEvent, QFont, QGuiApplication, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
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
from ..excel_export import export_merge_report, export_workbook
from ..field_map import FieldIdMap, FieldMapError
from ..i18n import LANGUAGES, tr, translator
from ..layout_engine import LayoutEngine, LayoutOptions
from ..merge_advisor import DEFAULT_THRESHOLD, MergeSuggestion, apply_merges, suggest_merges
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
from ..settings import AppSettings, data_dir
from ..spec_reader import SpecError, read_spec
from .mockup import PassportMockup
from .settings_dialog import PayloadSettingsDialog
from .theme import PALETTES, app_stylesheet
from .workers import Job, run_job

log = logging.getLogger(__name__)

FORMATS = ("payload.fmt_json", "payload.fmt_compact", "payload.fmt_form")
SEVERITY_MARK = {Severity.INFO: "ℹ", Severity.WARNING: "⚠", Severity.ERROR: "⛔"}
UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\s]+')


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
        self.filter_label = QLabel()
        self.filter_list = QListWidget()
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
        self.views.addTab(self.mockup, "")
        self.views.addTab(self._build_payload_tab(), "")
        self.validation_list = QListWidget()
        self.validation_list.setWordWrap(True)
        self.views.addTab(self.validation_list, "")
        self.views.addTab(self._build_merge_tab(), "")
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
        self.merge_export_button = QPushButton()
        self.merge_export_button.clicked.connect(self.export_merge_matrix)
        for button in (self.preview_button, self.apply_button, self.reset_button):
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
        self.excel_action = self._action("action.export_excel", self.export_excel, "Ctrl+E")
        self.png_action = self._action("action.export_png", self.export_png, "Ctrl+P")
        self.payload_action = self._action("action.save_payload", self.save_payload, QKeySequence.StandardKey.Save)
        self.all_payload_action = self._action("action.save_all_payloads", self.save_all_payloads, "Ctrl+Shift+S")
        self.quit_action = self._action("action.quit", self.close, QKeySequence.StandardKey.Quit)
        for action in (self.open_action, self.add_action, self.ids_action):
            self.file_menu.addAction(action)
        self.file_menu.addSeparator()
        for action in (self.excel_action, self.png_action, self.payload_action, self.all_payload_action):
            self.file_menu.addAction(action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.quit_action)

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
        self.setWindowTitle(tr("app.title"))
        for action in self._actions:
            action.setText(tr(str(action.data())))
        self.file_menu.setTitle(tr("menu.file"))
        self.view_menu.setTitle(tr("menu.view"))
        self.settings_menu.setTitle(tr("menu.settings"))
        self.help_menu.setTitle(tr("menu.help"))
        self.theme_menu.setTitle(tr("menu.theme"))
        self.language_menu.setTitle(tr("menu.language"))
        self.profile_menu.setTitle(tr("menu.profile"))
        for name, action in self._theme_actions.items():
            action.setText(tr(f"theme.{name}"))
        self.filter_label.setText(tr("panel.filters"))
        self.type_label.setText(tr("panel.object_type"))
        self.flagged_check.setText(tr("panel.only_flagged"))
        self.flagged_check.setToolTip(tr("panel.only_flagged_tip"))
        for index, key in enumerate(("tab.mockup", "tab.payload", "tab.validation", "tab.merge")):
            self.views.setTabText(index, tr(key))
        self.threshold_label.setText(tr("merge.threshold"))
        self.same_group_check.setText(tr("merge.same_group"))
        self.same_group_check.setToolTip(tr("merge.same_group_tip"))
        self.merge_hint.setText(tr("merge.hint"))
        self.preview_button.setText(tr("merge.preview"))
        self.apply_button.setText(tr("merge.apply"))
        self.reset_button.setText(tr("merge.reset"))
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
        start = self.settings.string("paths/last", str(Path.home()))
        file, _ = QFileDialog.getOpenFileName(self, tr("dialog.load_ids"), start, tr("dialog.filter_ids"))
        if not file:
            return
        try:
            self.ids = FieldIdMap.from_file(file)
        except FieldMapError as exc:
            log.warning("Field ID file failed: %s", exc)
            self._warn(tr("error.read_ids", detail=str(exc)))
            return
        self.statusBar().showMessage(tr("status.ids_loaded", count=len(self.ids), name=self.ids.source))
        self._refresh_views()

    # --- ontwerp en weergave / design and display ------------------------------------------------------------

    def _on_flagged_toggled(self, checked: bool) -> None:
        self.settings.set("design/only_flagged", checked)
        if self.spec is not None:
            self._rebuild_designs()

    def _rebuild_designs(self) -> None:
        if self.spec is None:
            return
        current = self.current_tab()
        previous = current.name if current else ""
        self._preview = None
        self.engine = LayoutEngine(
            self.spec, LayoutOptions(only_flagged=self.flagged_check.isChecked(), profile=self.profile),
        )
        base = self.engine.build_all()
        self.tabs = apply_merges(self.spec, self.engine, base, self.applied_merges)
        self._update_suggestions()
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
            self.type_combo.addItems([o.name for o in tab.object_types])
        self.type_combo.blockSignals(False)
        self._refresh_views()

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

    def apply_selected_merge(self) -> None:
        suggestion = self._selected_suggestion()
        if suggestion is None:
            return
        self.applied_merges.append((suggestion.name, list(suggestion.members)))
        self._rebuild_designs()
        self.statusBar().showMessage(tr("merge.applied", name=suggestion.name))

    def reset_merges(self) -> None:
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
        self.mockup.show_tab(tab, self.type_combo.currentText(), PALETTES[self.theme_name])
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
            export_workbook(self.tabs, path)
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
