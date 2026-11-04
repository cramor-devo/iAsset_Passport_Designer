"""Dialoog met het resultaat van de veld-ID-controle (filterbaar, sorteerbaar, exporteerbaar naar xlsx).
Dialog with the field ID check result (filterable, sortable, exportable to xlsx)."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..id_check import IdFinding, export_id_report, summary_text

log = logging.getLogger(__name__)

COLUMNS = ("tab", "section", "label", "id", "status", "detail", "types")
SEVERITY_COLOURS = {"error": "#e5484d", "warning": "#f0a500", "info": "#8a8a8e"}
ALL = ""


class IdCheckDialog(QDialog):
    """Toont ``findings``; filter op ernst en status. Shows ``findings``; filter by severity and status."""

    def __init__(self, findings: list[IdFinding], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.findings = findings
        self.setWindowTitle(tr("idcheck.title"))
        self.resize(1100, 560)
        layout = QVBoxLayout(self)
        self.summary_label = QLabel(
            tr("idcheck.summary", total=len(findings), text=summary_text(findings)),
        )
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        layout.addWidget(QLabel(tr("idcheck.offline")))

        filters = QHBoxLayout()
        self.severity_combo = QComboBox()
        self.status_combo = QComboBox()
        self._fill_combo(self.severity_combo, sorted({f.severity for f in findings}), "sev.")
        self._fill_combo(self.status_combo, sorted({f.status for f in findings}), "")
        severity_label, status_label = QLabel(tr("idcheck.severity")), QLabel(tr("idcheck.status"))
        severity_label.setBuddy(self.severity_combo)
        status_label.setBuddy(self.status_combo)
        self.shown_label = QLabel()
        for widget in (severity_label, self.severity_combo, status_label, self.status_combo):
            filters.addWidget(widget)
        filters.addStretch(1)
        filters.addWidget(self.shown_label)
        layout.addLayout(filters)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("idCheckTable")
        self.table.setHorizontalHeaderLabels([tr(f"idcheck.col.{c}") for c in COLUMNS])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.export_button = QPushButton(tr("idcheck.export"))
        self.close_button = QPushButton(tr("mock.close"))
        self.close_button.setDefault(True)
        buttons.addWidget(self.export_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.severity_combo.currentIndexChanged.connect(self.apply_filters)
        self.status_combo.currentIndexChanged.connect(self.apply_filters)
        self.export_button.clicked.connect(self.export_report)
        self.close_button.clicked.connect(self.accept)
        self.apply_filters()

    @staticmethod
    def _fill_combo(combo: QComboBox, values: list[str], translate_prefix: str) -> None:
        combo.addItem(tr("idcheck.all"), ALL)
        for value in values:
            text = tr(f"{translate_prefix}{value}") if translate_prefix else value
            combo.addItem(text, value)

    def visible_findings(self) -> list[IdFinding]:
        severity = self.severity_combo.currentData() or ALL
        status = self.status_combo.currentData() or ALL
        return [
            f for f in self.findings if (not severity or f.severity == severity) and (not status or f.status == status)
        ]

    def apply_filters(self) -> None:
        """Vul de tabel met de zichtbare bevindingen. / Fill the table with the visible findings."""
        shown = self.visible_findings()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(shown))
        for row, finding in enumerate(shown):
            values = (
                finding.tab, finding.section, finding.label, finding.field_id, finding.status, finding.detail,
                ", ".join(finding.object_types),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.DisplayRole, value if value is not None else "")
                if column == 4:
                    item.setForeground(QColor(SEVERITY_COLOURS.get(finding.severity, "#8a8a8e")))
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.shown_label.setText(tr("idcheck.shown", shown=len(shown), total=len(self.findings)))

    def export_to(self, path: str | Path) -> None:
        """Schrijf alle bevindingen naar ``path``. / Write all findings to ``path``."""
        export_id_report(self.findings, path)

    def export_report(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, tr("dialog.save_id_report"), "ID-controle.xlsx", tr("dialog.filter_xlsx"),
        )
        if not path:
            return
        try:
            self.export_to(path)
        except OSError as exc:
            log.exception("ID report export failed")
            QMessageBox.warning(self, tr("error.title"), tr("error.write", detail=str(exc)))
