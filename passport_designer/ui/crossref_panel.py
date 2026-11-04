"""Paneel met de vergelijking tussen een geïmporteerd ontwerp en de specificatie (per blad).
Panel with the comparison between an imported design and the specification (per sheet)."""

from __future__ import annotations

from collections import Counter

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ..crossref import TabDiff
from ..i18n import tr
from .theme import KIND_COLOURS

KIND_ORDER = ("added", "removed", "moved", "renamed", "not-in-spec")
COLUMNS = ("kind", "label", "move", "detail")


class CrossRefPanel(QWidget):
    """Toont per blad de verschillen (soort, veld, van → naar sectie, toelichting) met gekleurde soortlabels.
    Shows the differences per sheet (kind, field, from → to section, detail) with coloured kind badges."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.tree = QTreeWidget()
        self.tree.setObjectName("crossrefTree")
        self.tree.setRootIsDecorated(True)
        self.tree.setColumnCount(len(COLUMNS))
        layout.addWidget(self.tree, 1)
        self._source = ""
        self._diffs: list[tuple[str, TabDiff]] | None = None
        self._warnings: list[str] = []
        self._has_spec = False
        self.retranslate()

    def show_report(
        self, source: str, diffs: list[tuple[str, TabDiff]] | None, warnings: list[str], has_spec: bool,
    ) -> None:
        """``source``: bestandsnaam van de import ('' = geen import); ``diffs``: None zonder specificatie.
        ``source``: file name of the import ('' = no import); ``diffs``: None without a specification."""
        self._source, self._diffs, self._warnings, self._has_spec = source, diffs, list(warnings), has_spec
        self.retranslate()

    def retranslate(self) -> None:
        """Teken het paneel opnieuw in de gekozen taal. / Redraw the panel in the chosen language."""
        self.tree.clear()
        self.tree.setHeaderLabels([tr(f"xref.col.{c}") for c in COLUMNS])
        if not self._source:
            self.summary_label.setText(tr("xref.not_imported"))
            return
        text = tr("xref.imported", name=self._source)
        if self._diffs is None or not self._has_spec:
            text += "\n" + tr("xref.need_spec")
        self.summary_label.setText(text)
        for name, diff in self._diffs or []:
            self._add_sheet(name, diff)
        if self._warnings:
            top = QTreeWidgetItem([tr("xref.warnings")])
            for warning in self._warnings:
                top.addChild(QTreeWidgetItem(["", warning]))
            self.tree.addTopLevelItem(top)
            top.setExpanded(True)
        for column in range(len(COLUMNS)):
            self.tree.resizeColumnToContents(column)

    def counts_text(self, diff: TabDiff) -> str:
        counts = Counter(e.kind for e in diff.entries)
        parts = [f"{counts[k]} {tr(f'kind.{k}').lower()}" for k in KIND_ORDER if counts.get(k)]
        return ", ".join(parts) or tr("xref.no_diff")

    def _add_sheet(self, name: str, diff: TabDiff) -> None:
        top = QTreeWidgetItem([tr("xref.sheet_counts", name=name, counts=self.counts_text(diff))])
        font = top.font(0)
        font.setBold(True)
        top.setFont(0, font)
        if diff.is_empty:
            top.addChild(QTreeWidgetItem([tr("xref.no_diff")]))
        for entry in sorted(diff.entries, key=lambda e: KIND_ORDER.index(e.kind) if e.kind in KIND_ORDER else 99):
            label = entry.label
            if entry.kind == "renamed" and entry.other_label:
                label = f"{entry.other_label} → {entry.label}"
            move = f"{entry.from_section or '–'} → {entry.to_section or '–'}"
            child = QTreeWidgetItem([tr(f"kind.{entry.kind}"), label, move, entry.detail])
            child.setBackground(0, QBrush(QColor(KIND_COLOURS.get(entry.kind, "#8a8a8e"))))
            child.setForeground(0, QBrush(QColor("#ffffff")))
            child.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
            top.addChild(child)
        for section in diff.added_sections:
            top.addChild(QTreeWidgetItem([tr("kind.added"), tr("xref.sections_added", name=section)]))
        for section in diff.removed_sections:
            top.addChild(QTreeWidgetItem([tr("kind.removed"), tr("xref.sections_removed", name=section)]))
        self.tree.addTopLevelItem(top)
        top.setExpanded(True)
