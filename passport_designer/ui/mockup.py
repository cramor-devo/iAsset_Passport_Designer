"""Visuele mockup van een iAsset-paspoort (titelbalk, tabbladen, secties met kolomkoppen en invoervelden).
Visual mockup of an iAsset passport (title bar, tabs, sections with column headings and input fields)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..layout_engine import notes_section
from ..models import Cell, PassportTab, Section, SectionStyle
from .theme import DARK, Palette

EXPORT_WIDTH = 1100
SPACER_HEIGHT = 26
TOOL_ICONS: tuple[tuple[str, str], ...] = (
    ("✎", "mock.edit"), ("🗑", "mock.delete"), ("🖶", "mock.print"), ("⋮", "mock.more"), ("⛶", "mock.fullscreen"),
)
BASIS_SECTION = "Basis"


class PassportMockup(QFrame):
    """Toont een PassportTab, desgewenst voor één objecttype (velden die daar niet voor gelden zijn verborgen).
    Shows a PassportTab, optionally for one object type (fields that do not apply to it are hidden)."""

    def __init__(self, scrollable: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mockup")
        self._scrollable = scrollable
        self._palette: Palette = DARK
        self._tab: PassportTab | None = None
        self._object_type = ""
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)
        self.setMinimumWidth(520)

    def show_tab(self, tab: PassportTab | None, object_type: str, palette: Palette) -> None:
        """(Her)teken de mockup. / (Re)draw the mockup."""
        self._tab, self._object_type, self._palette = tab, object_type, palette
        while self._root.count():
            item = self._root.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.setStyleSheet(f"QFrame#mockup {{ background: {palette.frame}; border-radius: 12px; }}")
        if tab is None:
            return
        self._root.addWidget(self._build_title_bar(tab))
        self._root.addWidget(self._build_tab_bar(tab))
        body = self._build_body(tab)
        if self._scrollable:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.Shape.NoFrame)
            area.setWidget(body)
            self._root.addWidget(area, 1)
        else:
            self._root.addWidget(body)

    def render_pixmap(self) -> QPixmap:
        """Volledige mockup (zonder scrollen) als afbeelding. / Full mockup (without scrolling) as an image."""
        full = PassportMockup(scrollable=False)
        full.show_tab(self._tab, self._object_type, self._palette)
        full.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        full.ensurePolished()
        layout = full.layout()
        if layout is not None:
            layout.activate()
        full.resize(EXPORT_WIDTH, max(full.sizeHint().height(), 200))
        pixmap = full.grab()
        full.deleteLater()
        return pixmap

    # --- opbouw / construction -------------------------------------------------------------------------------

    def _build_title_bar(self, tab: PassportTab) -> QWidget:
        p = self._palette
        bar = QWidget()
        bar.setStyleSheet(f"background: {p.title_bar}; border-top-left-radius: 12px; border-top-right-radius: 12px;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 10, 14, 10)
        title = QLabel(self._object_type or tab.name)
        title.setStyleSheet(f"color: {p.text}; font-size: 15pt; font-weight: 700; background: transparent;")
        layout.addWidget(title)
        template = QComboBox()
        template.addItem(tab.name)
        template.setEnabled(False)
        template.setMinimumWidth(170)
        template.setStyleSheet(f"color: {p.text}; background: transparent; border: 1px solid {p.muted};")
        layout.addWidget(template)
        layout.addStretch(1)
        for icon, key in TOOL_ICONS:
            button = QToolButton()
            button.setText(icon)
            button.setToolTip(tr(key))
            button.setAccessibleName(tr(key))
            button.setEnabled(False)
            button.setStyleSheet(
                f"QToolButton {{ background: {p.button_bg}; color: #2b2b2f; border-radius: 5px; padding: 5px 8px; }}",
            )
            layout.addWidget(button)
        return bar

    def _build_tab_bar(self, tab: PassportTab) -> QWidget:
        p = self._palette
        bar = QWidget()
        bar.setStyleSheet(f"background: {p.title_bar};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(22)
        names = (tab.name, tr("mock.archive"), tr("mock.log"))
        for index, name in enumerate(names):
            label = QLabel(name)
            underline = f"border-bottom: 2px solid {p.text};" if index == 0 else "border-bottom: 2px solid transparent;"
            weight = 700 if index == 0 else 600
            label.setStyleSheet(
                f"color: {p.text if index == 0 else p.muted}; font-weight: {weight}; padding: 10px 2px; {underline}",
            )
            layout.addWidget(label)
        layout.addStretch(1)
        return bar

    def _build_body(self, tab: PassportTab) -> QWidget:
        p = self._palette
        body = QWidget()
        body.setObjectName("passportBody")
        body.setStyleSheet(f"QWidget#passportBody {{ background: {p.body}; }}")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 12, 20, 20)
        layout.setSpacing(0)
        sections = list(tab.sections)
        extra = notes_section(tab)
        if extra:
            sections.append(extra)
        for section in sections:
            layout.addWidget(self._build_section(tab, section))
        layout.addStretch(1)
        return body

    def _build_section(self, tab: PassportTab, section: Section) -> QWidget:
        p = self._palette
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)
        if section.title != BASIS_SECTION:
            heading = QLabel(tr("mock.notes") if section.style is SectionStyle.NOTES else section.title)
            colour = p.semantic if section.style is SectionStyle.SEMANTIC else p.text
            heading.setStyleSheet(f"color: {colour}; font-weight: 700; font-size: 9pt; padding: 4px 6px;")
            layout.addWidget(heading)
        if section.style is SectionStyle.NOTES:
            for row in section.rows:
                for cell in row:
                    note = QLabel(cell.label)
                    note.setWordWrap(True)
                    note.setStyleSheet(f"color: {p.muted}; font-size: 9pt; padding: 2px 6px;")
                    layout.addWidget(note)
            return wrapper
        for index, row in enumerate(section.rows):
            # Velden die niet voor het gekozen objecttype gelden worden verborgen.
            # Fields that do not apply to the chosen object type are hidden.
            visible = [c for c in row if not self._object_type or tab.applicable(c.label, self._object_type)]
            if row and not visible:
                continue
            layout.addWidget(self._build_row(tab, section, visible))
            remark = section.margin.get(index)
            if remark:
                note = QLabel(remark)
                note.setWordWrap(True)
                note.setStyleSheet(f"color: {p.muted}; font-style: italic; font-size: 8pt; padding: 0 6px 2px 6px;")
                layout.addWidget(note)
        return wrapper

    def _build_row(self, tab: PassportTab, section: Section, row: list[Cell]) -> QWidget:
        p = self._palette
        if not row:
            spacer = QWidget()
            spacer.setFixedHeight(SPACER_HEIGHT)
            return spacer
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        for column, cell in enumerate(row):
            grid.setColumnStretch(column, 1)
            head = QLabel(cell.label)
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            head.setStyleSheet(
                f"background: {p.header_band}; color: {p.text}; font-weight: 700; font-size: 8pt; padding: 7px 4px;",
            )
            head.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            value = QLabel(self._sample(section, cell))
            value.setMinimumHeight(24)
            value.setStyleSheet(
                f"background: {p.input_bg}; color: {p.text}; border-radius: 5px; padding: 2px 8px; font-size: 9pt;",
            )
            if cell.footnote:
                tip = tr("mock.applies_to", types=", ".join(tab.footnotes.get(cell.footnote, [])))
                head.setToolTip(tip)
                value.setToolTip(tip)
            grid.addWidget(head, 0, column)
            grid.addWidget(value, 1, column)
        grid.setRowMinimumHeight(1, 30)
        return holder

    def _sample(self, section: Section, cell: Cell) -> str:
        if section.title == BASIS_SECTION and cell.label.casefold() in {"objecttype", "naam"}:
            return self._object_type
        return cell.sample
