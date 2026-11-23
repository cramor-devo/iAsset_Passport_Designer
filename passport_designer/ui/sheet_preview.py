"""Voorbeeld van het Excel-ontwerpblad (zelfde indeling en kleuren als de export / het paspoortinrichting-bestand).
Preview of the Excel design sheet (same layout and colours as the export / the passport design file)."""

from __future__ import annotations

from collections.abc import Callable

from openpyxl.utils import get_column_letter
from PyQt6.QtCore import QByteArray, QMimeData, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QGradient,
    QLinearGradient,
)
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QWidget

from ..dataset_flags import MinimalMark
from ..excel_export import SheetCell, SheetLayout, sheet_layout
from ..i18n import tr
from ..layout_overrides import CellRef
from ..models import PassportTab

CELL_MIME = "application/x-passport-designer-cell"  # veld dat versleept wordt / field being dragged

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
    extra_toggled = pyqtSignal(list)  # extra (blauw) markeren/ontmarkeren / toggle the extra (blue) mark
    delete_requested = pyqtSignal(list)  # velden verwijderen / delete fields
    delete_marked_requested = pyqtSignal()  # alle gemarkeerde velden verwijderen / delete all marked fields
    restore_requested = pyqtSignal()  # verwijderde velden herstellen / restore deleted fields
    # Indeling (slepen en neerzetten); de Ontwerpblad-weergave praat alleen via deze signalen met het hoofdvenster.
    # Layout (drag and drop); the design sheet talks to the main window only through these signals.
    move_requested = pyqtSignal(object, object)  # (bron CellRef, doel CellRef) / (source, target)
    insert_row_requested = pyqtSignal(int, int)  # (sectie, rij) / (section, row)
    delete_row_requested = pyqtSignal(int, int)
    add_section_requested = pyqtSignal(int)  # onder sectie / below section
    rename_section_requested = pyqtSignal(int)
    reset_requested = pyqtSignal()
    blocks_requested = pyqtSignal()  # relatie- en standaardblokken bewerken / edit relation and standard blocks
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sheetPreview")
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setWordWrap(True)
        self.setStyleSheet(SHEET_STYLE)
        # Qt mag zelf nooit items verplaatsen: elke wijziging gaat via het model. / Qt must never move items itself:
        # every change goes through the model.
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.IgnoreAction)
        self.setDropIndicatorShown(True)
        self.editable = True
        self._layout: SheetLayout | None = None
        self._refs: dict[tuple[int, int], CellRef] = {}

    def show_tab(
        self, tab: PassportTab | None, *, muted: set[str] | None = None, minimal: dict[str, MinimalMark] | None = None,
        legend: dict[str, str] | None = None, verify: set[str] | None = None, extra: set[str] | None = None,
    ) -> None:
        self.clearSpans()
        self.clear()
        self._layout, self._refs = None, {}
        if tab is None:
            self.setRowCount(0)
            self.setColumnCount(0)
            return
        layout = sheet_layout(tab, muted=muted, minimal=minimal, legend=legend, verify=verify, extra=extra)
        self._layout = layout
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
            if cell.ref is not None:
                self._refs[(cell.row - 1, cell.column - 1)] = cell.ref
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

    def context_menu(self, labels: list[str], target: CellRef | None = None) -> QMenu:
        """Contextmenu voor ``labels``; de acties sturen de signalen uit. / Context menu for ``labels``; the actions
        emit the signals."""
        menu = QMenu(self)
        mark = menu.addAction(tr("verify.mark"))
        delete = menu.addAction(tr("verify.delete"))
        extra = menu.addAction(tr("extra.mark"))
        if extra is not None:
            extra.setEnabled(bool(labels))
            extra.triggered.connect(lambda: self.extra_toggled.emit(labels))
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
        self._add_layout_actions(menu, target)
        return menu

    def _add_layout_actions(self, menu: QMenu, target: CellRef | None) -> None:
        """Acties voor rijen en secties; alleen als de indeling bewerkbaar is. / Row and section actions; only when
        the layout is editable."""
        menu.addSeparator()
        enabled = self.editable and target is not None
        section = target.section if target is not None else 0
        row = max(target.row, 0) if target is not None else 0
        has_row = target is not None and target.row >= 0
        entries: list[tuple[str, bool, Callable[[], None]]] = [
            ("layout.insert_above", has_row, lambda: self.insert_row_requested.emit(section, row)),
            ("layout.insert_below", has_row, lambda: self.insert_row_requested.emit(section, row + 1)),
            ("layout.new_section", True, lambda: self.add_section_requested.emit(section)),
            ("layout.rename_section", True, lambda: self.rename_section_requested.emit(section)),
            ("layout.delete_row", has_row, lambda: self.delete_row_requested.emit(section, row)),
            ("layout.reset", True, lambda: self.reset_requested.emit()),
            ("action.relation_blocks", True, lambda: self.blocks_requested.emit()),
        ]
        for key, applies, callback in entries:
            action = menu.addAction(tr(key).replace("&", ""))
            if action is None:
                continue
            action.setEnabled(
                self.editable if key == "action.relation_blocks" else enabled and (applies or key == "layout.reset"),
            )
            action.triggered.connect(lambda _checked=False, c=callback: c())

    def contextMenuEvent(self, event) -> None:  # type: ignore[no-untyped-def]  # noqa: N802
        """Klik met rechts: een niet-geselecteerde veldcel wordt eerst geselecteerd. / Right-click: an unselected field
        cell is selected first."""
        item = self.itemAt(event.pos())
        if item is not None and not item.isSelected():
            self.clearSelection()
            item.setSelected(True)
        self.context_menu(self.selected_labels(), self.target_at(event.pos())).exec(event.globalPos())

    # --- slepen en neerzetten / drag and drop ----------------------------------------------------------------

    def target_at(self, pos: QPoint) -> CellRef | None:
        """Plek in het paspoort onder ``pos`` (sectiekop = rij -1), of None. / Position in the passport under ``pos``
        (section heading = row -1), or None."""
        if self._layout is None:
            return None
        index = self.indexAt(pos)
        if not index.isValid():
            return None
        ref = self._layout.row_refs.get(index.row() + 1)
        if ref is None:
            return None
        section, row = ref
        return CellRef(section, row, 0 if row < 0 else index.column())

    def startDrag(self, supportedActions) -> None:  # type: ignore[no-untyped-def]  # noqa: N802
        """Start het slepen van het huidige veld; Qt verplaatst zelf niets. / Start dragging the current field; Qt
        moves nothing itself."""
        item = self.currentItem()
        ref = self._refs.get((item.row(), item.column())) if item is not None else None
        if not self.editable or ref is None:
            return
        mime = QMimeData()
        mime.setData(CELL_MIME, QByteArray(f"{ref.section},{ref.row},{ref.col}".encode()))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    @staticmethod
    def _source_of(mime: QMimeData | None) -> CellRef | None:
        if mime is None or not mime.hasFormat(CELL_MIME):
            return None
        try:
            section, row, col = (int(x) for x in bytes(mime.data(CELL_MIME).data()).decode().split(","))
        except ValueError:
            return None
        return CellRef(section, row, col)

    def dragEnterEvent(self, e: QDragEnterEvent | None) -> None:  # noqa: N802
        if e is not None and self.editable and self._source_of(e.mimeData()) is not None:
            e.acceptProposedAction()
        elif e is not None:
            e.ignore()

    def dragMoveEvent(self, e: QDragMoveEvent | None) -> None:  # noqa: N802
        if e is None:
            return
        allowed = self.editable and self._source_of(e.mimeData()) is not None
        if allowed and self.target_at(e.position().toPoint()) is not None:
            e.acceptProposedAction()  # de dropindicator toont het doel / the drop indicator shows the target
        else:
            e.ignore()

    def dropEvent(self, event: QDropEvent | None) -> None:  # noqa: N802
        """Zet neer: nooit het standaardgedrag van Qt (dat verplaatst items), alleen een verzoek aan het model.
        Drop: never Qt's default (which moves items), only a request to the model."""
        if event is None:
            return
        source = self._source_of(event.mimeData())
        target = self.target_at(event.position().toPoint())
        if self.editable and source is not None and target is not None:
            self._handle_drop(source, target)
        event.accept()

    def _handle_drop(self, source: CellRef, target: CellRef) -> None:
        self.move_requested.emit(source, target)

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
