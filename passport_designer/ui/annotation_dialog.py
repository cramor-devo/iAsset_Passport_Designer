"""Dialoog voor de annotatiecontrole en -reparatie van een Excel-ontwerp.
Dialog for checking and fixing the annotations of an Excel design."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from .workers import Job, run_job

log = logging.getLogger(__name__)

COLUMNS = ("sheet", "cell", "kind", "severity", "detail")


class AnnotationDialog(QDialog):
    """Toont een AnnotationReport; ``fixer`` (optioneel) repareert naar een ``_fixed.xlsx`` en geeft een FixResult.
    Shows an AnnotationReport; ``fixer`` (optional) fixes into a ``_fixed.xlsx`` and returns a FixResult."""

    def __init__(
        self, report: Any, has_spec: bool, fixer: Callable[[], Any] | None = None, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.report = report
        self._fixer = fixer
        self.setWindowTitle(tr("annot.title"))
        self.resize(900, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("annot.file", path=str(report.path))))
        self.info_label = QLabel(tr("annot.no_spec") if not has_spec else "")
        self.info_label.setWordWrap(True)
        self.info_label.setVisible(not has_spec)
        layout.addWidget(self.info_label)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("annotationTable")
        self.table.setHorizontalHeaderLabels([tr(f"annot.col.{c}") for c in COLUMNS])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)
        self.result_box = QPlainTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setMaximumHeight(150)
        self.result_box.setVisible(False)
        layout.addWidget(self.result_box)
        buttons = QHBoxLayout()
        self.fix_button = QPushButton(tr("annot.fix"))
        self.fix_button.setToolTip(tr("annot.fix_tip"))
        self.close_button = QPushButton(tr("mock.close"))
        self.close_button.setDefault(True)
        self.fix_button.setEnabled(fixer is not None)
        buttons.addWidget(self.fix_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.fix_button.clicked.connect(self.run_fix)
        self.close_button.clicked.connect(self.accept)
        self.fix_result: Any = None
        self._fixing = False
        self.show_report(report)

    def show_report(self, report: Any) -> None:
        """Vul de samenvatting en tabel. / Fill the summary and table."""
        issues = list(report.issues)
        checked = report.sheets_checked
        text = tr("annot.summary", sheets=checked if isinstance(checked, int) else len(checked), issues=len(issues))
        self.summary_label.setText(f"{text} {tr('annot.ok')}" if not issues else text)
        self.table.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            for column, key in enumerate(COLUMNS):
                self.table.setItem(row, column, QTableWidgetItem(str(getattr(issue, key))))
        self.table.resizeColumnsToContents()

    def show_fix_result(self, result: Any) -> None:
        """Toon wijzigingen, resterende problemen en het uitvoerpad. / Show changes, remaining issues and the output."""
        self.fix_result = result
        lines = [tr("annot.fixed", path=str(result.out_path)), tr("annot.changes", count=len(result.changes))]
        lines += [f"  • {change}" for change in result.changes]
        warnings = list(getattr(result, "warnings", []))
        if warnings:
            lines.append(tr("annot.warnings"))
            lines += [f"  ! {warning}" for warning in warnings]
        lines.append(tr("annot.after", issues=len(result.report_after.issues)))
        self.result_box.setPlainText("\n".join(lines))
        self.result_box.setVisible(True)
        self.show_report(result.report_after)

    def run_fix(self) -> None:
        """Repareer op een werkthread; het resultaat verschijnt via ``show_fix_result``.
        Repair on a worker thread; the result arrives through ``show_fix_result``."""
        if self._fixer is None or self._fixing:
            return
        self._fixing = True
        self.fix_button.setEnabled(False)
        fixer = self._fixer
        job = Job(lambda progress: fixer())
        job.signals.finished.connect(self._on_fixed)
        job.signals.failed.connect(self._on_fix_failed)
        run_job(job)

    def _on_fixed(self, result: object) -> None:
        self._fixing = False
        self.fix_button.setEnabled(self._fixer is not None)
        self.show_fix_result(result)

    def _on_fix_failed(self, error: object) -> None:
        self._fixing = False
        self.fix_button.setEnabled(self._fixer is not None)
        log.warning("Annotation fix failed: %s", error)
        QMessageBox.warning(self, tr("error.title"), tr("annot.fix_failed", detail=f"{type(error).__name__}: {error}"))


def fixed_name(path: str | Path) -> Path:
    """Standaard uitvoerpad ``<naam>_fixed.xlsx``. / Default output path ``<name>_fixed.xlsx``."""
    source = Path(path)
    return source.with_name(f"{source.stem}_fixed.xlsx")
