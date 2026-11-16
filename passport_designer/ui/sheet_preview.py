"""Voorbeeld van het Excel-ontwerpblad (zelfde indeling en kleuren als de export / het paspoortinrichting-bestand).
Preview of the Excel design sheet (same layout and colours as the export / the passport design file)."""

from __future__ import annotations

from openpyxl.utils import get_column_letter
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QGradient, QLinearGradient
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QWidget

from ..dataset_flags import MinimalMark
from ..excel_export import SheetCell, SheetLayout, sheet_layout
from ..i18n import tr
from ..models import PassportTab

PIXELS_PER_CHAR = 7  # Excel-kolombreedte (tekens) -> pixels / Excel column width (characters) -> pixels
DEFAULT_WIDTH = 9
SHEET_STYLE = (
    "QTableWidget { background: #FFFFFF; color: #000000; gridline-color: #E1E1E1; }"
    "QHeaderView::section { background: #F3F3F3; color: #444444; border: 1px solid #E1E1E1; padding: 2px; }"
)


class SheetPreview(QTableWidget):
    """Toont een PassportTab als ontwerpblad (Excel-weergave). / Shows a PassportTab as a design sheet (Excel view)."""

    # Velden zijn genormaliseerde namen. / Fields are normalised names.
    verify_toggled = pyqtSignal(list)  # markeren/ontmarkeren / toggle the mark
    delete_requested = pyqtSignal(list)  # velden verwijderen / delete fields
    delete_marked_requested = pyqtSignal()  # alle gemarkeerde velden verwijderen / delete all marked fields
    restore_requested = pyqtSignal()  # verwijderde velden herstellen / restore deleted fields

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sheetPreview")
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setWordWrap(True)
        self.setStyleSheet(SHEET_STYLE)

    def show_tab(
        self, tab: PassportTab | None, *, muted: set[str] | None = None, minimal: dict[str, MinimalMark] | None = None,
        legend: dict[str, str] | None = None, verify: set[str] | None = None,
    ) -> None:
        self.clearSpans()
        self.clear()
        if tab is None:
            self.setRowCount(0)
            self.setColumnCount(0)
            return
        layout = sheet_layout(tab, muted=muted, minimal=minimal, legend=legend, verify=verify)
        self.setRowCount(layout.row_count)
        self.setColumnCount(layout.column_count)
        self.setHorizontalHeaderLabels([get_column_letter(c) for c in range(1, layout.column_count + 1)])
        for column in range(1, layout.column_count + 1):
            width = layout.widths.get(column, DEFAULT_WIDTH)
            self.setColumnWidth(column - 1, width * PIXELS_PER_CHAR)
        for cell in layout.cells:
            item = QTableWidgetItem(cell.value)
            item.setData(Qt.ItemDataRole.UserRole, cell.key)
            item.setForeground(QBrush(QColor(f"#{cell.colour}" if cell.colour else "#000000")))
            if cell.tip:
                item.setToolTip(cell.tip)
            if cell.fill_stops:
                item.setBackground(QBrush(_stripes(cell.fill_stops)))
            elif cell.fill:
                item.setBackground(QBrush(QColor(f"#{cell.fill[-6:]}")))
            font = QFont(item.font())
            font.setBold(cell.bold)
            font.setItalic(cell.italic)
            if cell.size:
                font.setPointSize(cell.size)
            item.setFont(font)
            self.setItem(cell.row - 1, cell.column - 1, item)
            last = cell.merge_to or _overflow_end(cell, layout)
            if last > cell.column:
                self.setSpan(cell.row - 1, cell.column - 1, 1, last - cell.column + 1)
        self.resizeRowsToContents()

    def selected_labels(self) -> list[str]:
        """Genormaliseerde veldnamen van de geselecteerde veldcellen. / Normalised names of the selected field cells."""
        labels: list[str] = []
        for item in self.selectedItems():
            key = item.data(Qt.ItemDataRole.UserRole)
            if key and key not in labels:
                labels.append(str(key))
        return labels

    def context_menu(self, labels: list[str]) -> QMenu:
        """Contextmenu voor ``labels``; de acties sturen de signalen uit. / Context menu for ``labels``; the actions
        emit the signals."""
        menu = QMenu(self)
        mark = menu.addAction(tr("verify.mark"))
        delete = menu.addAction(tr("verify.delete"))
        if mark is not None:
            mark.setEnabled(bool(labels))
            mark.triggered.connect(lambda: self.verify_toggled.emit(labels))
        if delete is not None:
            delete.setEnabled(bool(labels))
            delete.triggered.connect(lambda: self.delete_requested.emit(labels))
        menu.addSeparator()
        for text, signal in (("verify.delete_marked", self.delete_marked_requested),
                             ("verify.restore", self.restore_requested)):
            action = menu.addAction(tr(text))
            if action is not None:
                action.triggered.connect(lambda _checked=False, s=signal: s.emit())
        return menu

    def contextMenuEvent(self, event) -> None:  # type: ignore[no-untyped-def]  # noqa: N802
        """Klik met rechts: een niet-geselecteerde veldcel wordt eerst geselecteerd. / Right-click: an unselected field
        cell is selected first."""
        item = self.itemAt(event.pos())
        if item is not None and not item.isSelected():
            self.clearSelection()
            item.setSelected(True)
        self.context_menu(self.selected_labels()).exec(event.globalPos())

    def text_at(self, row: int, column: int) -> str:
        """Tekst in een cel (1-gebaseerd, zoals Excel). / Text in a cell (1-based, like Excel)."""
        item = self.item(row - 1, column - 1)
        return item.text() if item is not None else ""



def _stripes(colours: tuple[str, ...]) -> QLinearGradient:
    """Strepen met harde randen (als in de Excel-export).
    / Hard-edged stripes (as in the Excel export)."""
    gradient = QLinearGradient(0, 0, 1, 0)
    gradient.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
    count = len(colours)
    for index, colour in enumerate(colours):
        gradient.setColorAt(index / count, QColor(f"#{colour}"))
        gradient.setColorAt(min((index + 1) / count - 0.001, 1.0), QColor(f"#{colour}"))
    return gradient


def _overflow_end(cell: SheetCell, layout: SheetLayout) -> int:
    """Laatste kolom waarin tekst zonder terugloop doorloopt (zoals in Excel, tot de volgende gevulde cel).
    Last column into which unwrapped text overflows (as in Excel, up to the next filled cell)."""
    if cell.wrap or not cell.value:
        return 0
    filled = [c.column for c in layout.cells if c.row == cell.row and c.value and c.column > cell.column]
    return (min(filled) - 1) if filled else layout.column_count
