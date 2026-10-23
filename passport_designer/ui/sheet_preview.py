"""Voorbeeld van het Excel-ontwerpblad (zelfde indeling en kleuren als de export / het paspoortinrichting-bestand).
Preview of the Excel design sheet (same layout and colours as the export / the passport design file)."""

from __future__ import annotations

from openpyxl.utils import get_column_letter
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem, QWidget

from ..excel_export import SheetCell, SheetLayout, sheet_layout
from ..models import PassportTab

PIXELS_PER_CHAR = 7  # Excel-kolombreedte (tekens) -> pixels / Excel column width (characters) -> pixels
DEFAULT_WIDTH = 9
SHEET_STYLE = (
    "QTableWidget { background: #FFFFFF; color: #000000; gridline-color: #E1E1E1; }"
    "QHeaderView::section { background: #F3F3F3; color: #444444; border: 1px solid #E1E1E1; padding: 2px; }"
)


class SheetPreview(QTableWidget):
    """Toont een PassportTab als ontwerpblad (Excel-weergave). / Shows a PassportTab as a design sheet (Excel view)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sheetPreview")
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setWordWrap(True)
        self.setStyleSheet(SHEET_STYLE)

    def show_tab(self, tab: PassportTab | None) -> None:
        self.clearSpans()
        self.clear()
        if tab is None:
            self.setRowCount(0)
            self.setColumnCount(0)
            return
        layout = sheet_layout(tab)
        self.setRowCount(layout.row_count)
        self.setColumnCount(layout.column_count)
        self.setHorizontalHeaderLabels([get_column_letter(c) for c in range(1, layout.column_count + 1)])
        for column in range(1, layout.column_count + 1):
            width = layout.widths.get(column, DEFAULT_WIDTH)
            self.setColumnWidth(column - 1, width * PIXELS_PER_CHAR)
        for cell in layout.cells:
            item = QTableWidgetItem(cell.value)
            item.setForeground(QBrush(QColor("#000000")))
            if cell.fill:
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

    def text_at(self, row: int, column: int) -> str:
        """Tekst in een cel (1-gebaseerd, zoals Excel). / Text in a cell (1-based, like Excel)."""
        item = self.item(row - 1, column - 1)
        return item.text() if item is not None else ""



def _overflow_end(cell: SheetCell, layout: SheetLayout) -> int:
    """Laatste kolom waarin tekst zonder terugloop doorloopt (zoals in Excel, tot de volgende gevulde cel).
    Last column into which unwrapped text overflows (as in Excel, up to the next filled cell)."""
    if cell.wrap or not cell.value:
        return 0
    filled = [c.column for c in layout.cells if c.row == cell.row and c.value and c.column > cell.column]
    return (min(filled) - 1) if filled else layout.column_count
