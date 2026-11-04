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

from ..crossref import label_key
from ..i18n import tr
from ..layout_engine import notes_section
from ..models import Cell, PassportTab, Section, SectionStyle
from .theme import DARK, KIND_COLOURS, Palette

EXPORT_WIDTH = 1100
SPACER_HEIGHT = 26
TOOL_ICONS: tuple[tuple[str, str], ...] = (
    ("✎", "mock.edit"), ("🗑", "mock.delete"), ("🖶", "mock.print"), ("⋮", "mock.more"), ("⛶", "mock.fullscreen"),
)
BASIS_SECTION = "Basis"
MAX_COLUMNS = 5
DEFAULT_COLUMN_WIDTH = 8.43  # Excel-standaard / Excel default
STRETCH_SCALE = 10
RADIUS = 4


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
        self._widths: list[float] = []
        self._highlights: dict[str, str] = {}
        self.show_extra_tabs = True
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)
        self.setMinimumWidth(520)

    def show_tab(
        self,
        tab: PassportTab | None,
        object_type: str,
        palette: Palette,
        column_widths: list[float] | None = None,
        highlights: dict[str, str] | None = None,
    ) -> None:
        """(Her)teken de mockup. ``column_widths`` (Excel-tekens, bij een import) bepaalt de verhouding van de
        rasterkolommen; ``highlights`` koppelt een genormaliseerde veldnaam aan een soort verschil (omlijning).
        (Re)draw the mockup. ``column_widths`` (Excel characters, for an import) sets the grid column proportions;
        ``highlights`` maps a normalised field name to a kind of difference (outline)."""
        self._tab, self._object_type, self._palette = tab, object_type, palette
        self._widths = [w for w in (column_widths or [])]
        self._highlights = dict(highlights or {})
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
        full.show_extra_tabs = self.show_extra_tabs
        full.show_tab(self._tab, self._object_type, self._palette, self._widths, self._highlights)
        full.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        full.ensurePolished()
        layout = full.layout()
        if layout is not None:
            layout.activate()
        full.resize(EXPORT_WIDTH, max(full.sizeHint().height(), 200))
        pixmap = full.grab()
        full.deleteLater()
        return pixmap

    def column_stretch(self, tab: PassportTab | None = None) -> list[int]:
        """Stretchfactoren van de rasterkolommen (gelijk, of naar Excel-breedte bij een import).
        Stretch factors of the grid columns (equal, or from the Excel widths for an import)."""
        count = self._column_count(tab or self._tab)
        if not self._widths:
            return [1] * count
        widths = [w if w > 0 else DEFAULT_COLUMN_WIDTH for w in self._widths[:count]]
        widths += [DEFAULT_COLUMN_WIDTH] * (count - len(widths))
        return [max(1, round(w * STRETCH_SCALE)) for w in widths]

    @staticmethod
    def _column_count(tab: PassportTab | None) -> int:
        if tab is None:
            return MAX_COLUMNS
        longest = max((len(row) for s in tab.sections for row in s.rows), default=1)
        return max(1, min(MAX_COLUMNS, longest))

    # --- opbouw / construction -------------------------------------------------------------------------------

    def _build_title_bar(self, tab: PassportTab) -> QWidget:
        p = self._palette
        bar = QWidget()
        bar.setObjectName("mockTitleBar")
        bar.setStyleSheet(
            f"QWidget#mockTitleBar {{ background: {p.title_bar}; border-top-left-radius: 12px; "
            "border-top-right-radius: 12px; }",
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        title = QLabel(self._object_type or tab.name)
        title.setStyleSheet(f"color: {p.text}; font-size: 15pt; font-weight: 700; background: transparent;")
        layout.addWidget(title)
        view = QComboBox()
        view.setObjectName("mockView")
        view.addItem(tab.name)
        view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        view.setMinimumWidth(190)
        view.setStyleSheet(
            f"QComboBox {{ color: {p.text}; background: transparent; border: 1px solid {p.separator}; "
            f"border-radius: {RADIUS}px; padding: 5px 10px; font-size: 10pt; }}",
        )
        layout.addWidget(view)
        layout.addStretch(1)
        for icon, key in TOOL_ICONS:
            button = QToolButton()
            button.setText(icon)
            button.setToolTip(tr(key))
            button.setAccessibleName(tr(key))
            button.setEnabled(False)
            button.setStyleSheet(
                f"QToolButton {{ background: {p.button_bg}; color: #2b2b2f; border-radius: 5px; padding: 5px 9px; }}",
            )
            layout.addWidget(button)
        return bar

    def _build_tab_bar(self, tab: PassportTab) -> QWidget:
        p = self._palette
        bar = QWidget()
        bar.setObjectName("mockTabBar")
        bar.setStyleSheet(f"QWidget#mockTabBar {{ background: {p.body}; border-bottom: 1px solid {p.separator}; }}")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(28)
        names = [tab.name]
        if self.show_extra_tabs:
            names += [tr("mock.activities"), tr("mock.archive"), tr("mock.log")]
        for index, name in enumerate(names):
            label = QLabel(name)
            label.setObjectName("mockTabActive" if index == 0 else "mockTab")
            underline = f"3px solid {p.text}" if index == 0 else "3px solid transparent"
            label.setStyleSheet(
                f"color: {p.text if index == 0 else p.muted}; font-weight: 700; font-size: 10pt; background: "
                f"transparent; padding: 12px 2px 9px 2px; border-bottom: {underline};",
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
        layout.setContentsMargins(22, 14, 22, 22)
        layout.setSpacing(0)
        sections = list(tab.sections)
        extra = notes_section(tab)
        if extra:
            sections.append(extra)
        for index, section in enumerate(sections):
            if index:
                layout.addWidget(self._separator())
            layout.addWidget(self._build_section(tab, section))
        layout.addStretch(1)
        return body

    def _separator(self) -> QWidget:
        line = QFrame()
        line.setObjectName("mockSeparator")
        line.setFixedHeight(1)
        line.setStyleSheet(f"QFrame#mockSeparator {{ background: {self._palette.separator}; border: none; }}")
        return line

    def _build_section(self, tab: PassportTab, section: Section) -> QWidget:
        p = self._palette
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(4)
        heading = QLabel(tr("mock.notes") if section.style is SectionStyle.NOTES else section.title)
        heading.setObjectName("mockSection")
        colour = p.semantic if section.style is SectionStyle.SEMANTIC else p.text
        heading.setStyleSheet(
            f"color: {colour}; font-weight: 700; font-size: 9pt; padding: 2px 4px; background: transparent;",
        )
        layout.addWidget(heading)
        if section.style is SectionStyle.NOTES:
            for row in section.rows:
                for cell in row:
                    note = QLabel(cell.label)
                    note.setWordWrap(True)
                    note.setStyleSheet(f"color: {p.muted}; font-size: 9pt; padding: 2px 6px; background: transparent;")
                    layout.addWidget(note)
            return wrapper
        columns = self._column_count(tab)
        stretch = self.column_stretch(tab)
        for index, row in enumerate(section.rows):
            # Velden die niet voor het gekozen objecttype gelden worden verborgen.
            # Fields that do not apply to the chosen object type are hidden.
            visible = [c for c in row if not self._object_type or tab.applicable(c.label, self._object_type)]
            if row and not visible:
                continue
            layout.addWidget(self._build_row(tab, section, visible, columns, stretch))
            remark = section.margin.get(index)
            if remark:
                note = QLabel(remark)
                note.setWordWrap(True)
                note.setStyleSheet(
                    f"color: {p.muted}; font-style: italic; font-size: 8pt; padding: 0 6px 2px 6px; "
                    "background: transparent;",
                )
                layout.addWidget(note)
        return wrapper

    def _build_row(
        self, tab: PassportTab, section: Section, row: list[Cell], columns: int, stretch: list[int],
    ) -> QWidget:
        p = self._palette
        if not row:
            spacer = QWidget()
            spacer.setFixedHeight(SPACER_HEIGHT)
            return spacer
        holder = QWidget()
        holder.setObjectName("mockRow")
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(6)
        for column in range(max(columns, len(row))):
            grid.setColumnStretch(column, stretch[column] if column < len(stretch) else 1)
            cell = row[column] if column < len(row) else None
            colour = self._highlights.get(label_key(cell.label)) if cell is not None and self._highlights else None
            head = QLabel(self._caption(cell) if cell is not None else "")
            head.setObjectName("mockHead")
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            head.setWordWrap(True)
            tint = KIND_COLOURS.get(colour, "transparent") if colour else ""
            marker = f"border-bottom: 3px solid {tint};" if tint else ""
            head.setStyleSheet(
                f"background: {p.header_band}; color: {p.text}; font-weight: 700; font-size: 8pt; "
                f"padding: 9px 6px; {marker}",
            )
            head.setMinimumWidth(0)
            head.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            grid.addWidget(head, 0, column)
            if cell is None:
                continue
            value = QLabel(self._sample(section, cell))
            value.setObjectName("mockValue")
            value.setMinimumHeight(26)
            value.setMinimumWidth(0)
            value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            outline = f"border: 2px solid {tint};" if tint else "border: none;"
            value.setStyleSheet(
                f"background: {p.input_bg}; color: {p.text}; border-radius: {RADIUS}px; padding: 2px 10px; "
                f"font-size: 9pt; {outline}",
            )
            value_holder = QWidget()
            value_layout = QHBoxLayout(value_holder)
            value_layout.setContentsMargins(6, 0, 6, 0)
            value_layout.addWidget(value)
            grid.addWidget(value_holder, 1, column)
            tips = []
            if cell.footnote:
                tips.append(tr("mock.applies_to", types=", ".join(tab.footnotes.get(cell.footnote, []))))
            if colour:
                tips.append(tr(f"kind.{colour}"))
            for widget in (head, value):
                widget.setToolTip("\n".join(tips))
        grid.setRowMinimumHeight(1, 30)
        return holder

    @staticmethod
    def _caption(cell: Cell) -> str:
        return f"{cell.label} ({cell.footnote})" if cell.footnote else cell.label

    def _sample(self, section: Section, cell: Cell) -> str:
        if section.title == BASIS_SECTION and cell.label.casefold() in {"objecttype", "naam"}:
            return self._object_type
        return cell.sample
