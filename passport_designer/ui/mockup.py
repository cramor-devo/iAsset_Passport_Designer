"""Visuele mockup van een iAsset-paspoort (titelbalk, tabbladen, secties met kolomkoppen en invoervelden).
Visual mockup of an iAsset passport (title bar, tabs, sections with column headings and input fields)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPixmap
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

from ..compare import ELLIPSIS_CHARS
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
DEFAULT_COLUMN_WIDTH = 8.43  # Excel-standaard / Excel default
STRETCH_SCALE = 10
RADIUS = 4
REPEATER_ROWS = 3  # voorbeeldrijen onder één kopband / sample rows under one header band
BOX_PERCENT = 88  # breedte van een waardevak in procenten van de kolom / width of a value box in % of the column
TABLE_ICONS = ("🔗", "⊘", "↪")  # koppelen, ontkoppelen, koppelen-pijl / link, unlink, link-arrow
PAGER_FIRST, PAGER_LAST = ("«", "‹"), ("›", "»")
GEAR = "⚙"


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
        self._positions: dict[tuple[int, int, int], tuple[int, int]] = {}
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
        positions: dict[tuple[int, int, int], tuple[int, int]] | None = None,
    ) -> None:
        """(Her)teken de mockup. Zoals in iAsset strekt elke rij haar N kolommen over de volle breedte. Bij een
        import bepalen ``column_widths`` (Excel-tekens) en ``positions`` ((sectie, rij, cel) -> (Excel-rij,
        -kolom)) de verhouding: een cel krijgt de breedte van de Excel-kolom waarin hij staat; anders zijn de kolommen
        gelijk. ``highlights`` koppelt een genormaliseerde veldnaam aan een soort verschil (omlijning).
        (Re)draw the mockup. As in iAsset every row stretches its N columns across the full width. For an import
        ``column_widths`` (Excel characters) and ``positions`` ((section, row, cell) -> (Excel row, column)) set the
        proportions: a cell gets the width of the Excel column it sits in; otherwise columns are equal.
        ``highlights`` maps a normalised field name to a kind of difference (outline)."""
        self._tab, self._object_type, self._palette = tab, object_type, palette
        self._widths = [w for w in (column_widths or [])]
        self._highlights = dict(highlights or {})
        self._positions = dict(positions or {})
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
        full.show_tab(
            self._tab, self._object_type, self._palette, self._widths, self._highlights, self._positions,
        )
        full.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        full.ensurePolished()
        layout = full.layout()
        if layout is not None:
            layout.activate()
        full.resize(EXPORT_WIDTH, max(full.sizeHint().height(), 200))
        pixmap = full.grab()
        full.deleteLater()
        return pixmap

    def row_stretch(self, section: int, row: int, cells: list[int]) -> list[int]:
        """Stretchfactoren voor de cellen ``cells`` (indices in rij ``row`` van sectie ``section``): de Excel-breedte
        van hun kolom bij een import, anders gelijk. Stretch factors for ``cells`` (indices in the row): the Excel
        width of their column for an import, otherwise equal."""
        if not self._widths or not self._positions:
            return [1] * len(cells)
        result: list[int] = []
        for index in cells:
            position = self._positions.get((section, row, index))
            width = self._widths[position[1] - 1] if position and 0 < position[1] <= len(self._widths) else 0.0
            result.append(max(1, round((width if width > 0 else DEFAULT_COLUMN_WIDTH) * STRETCH_SCALE)))
        return result

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
            layout.addWidget(self._build_section(tab, section, index))
        layout.addStretch(1)
        return body

    def _separator(self) -> QWidget:
        line = QFrame()
        line.setObjectName("mockSeparator")
        line.setFixedHeight(1)
        line.setStyleSheet(f"QFrame#mockSeparator {{ background: {self._palette.separator}; border: none; }}")
        return line

    def _build_section(self, tab: PassportTab, section: Section, section_index: int) -> QWidget:
        p = self._palette
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(4)
        is_table = section.style is not SectionStyle.NOTES and tab.profile.is_table_section(section.title)
        heading = QLabel(tr("mock.notes") if section.style is SectionStyle.NOTES else section.title)
        heading.setObjectName("mockSection")
        # iAsset toont (Sem.Rel)-titels gelijk aan andere secties / iAsset shows (Sem.Rel) titles like other sections.
        heading.setStyleSheet(
            f"color: {p.text}; font-weight: 700; font-size: 9pt; padding: 2px 4px; background: transparent;",
        )
        if is_table:
            layout.addWidget(self._build_table(tab, section, section_index, heading))
            return wrapper
        layout.addWidget(heading)
        if section.style is SectionStyle.NOTES:
            for row in section.rows:
                for cell in row:
                    note = QLabel(cell.label)
                    note.setWordWrap(True)
                    note.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
                    note.setStyleSheet(f"color: {p.muted}; font-size: 9pt; padding: 2px 6px; background: transparent;")
                    layout.addWidget(note)
            return wrapper
        if section.repeater:
            repeated = self._build_repeater(tab, section, section_index)
            if repeated is not None:
                layout.addWidget(repeated)
                return wrapper
        for index, row in enumerate(section.rows):
            kept = self._kept(tab, row)
            if row and not kept:
                continue
            stretch = self.row_stretch(section_index, index, kept)
            layout.addWidget(self._build_row(tab, section, [row[i] for i in kept], stretch))
            remark = section.margin.get(index)
            if remark:
                note = QLabel(remark)
                note.setWordWrap(True)
                note.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
                note.setStyleSheet(
                    f"color: {p.muted}; font-style: italic; font-size: 8pt; padding: 0 6px 2px 6px; "
                    "background: transparent;",
                )
                layout.addWidget(note)
        return wrapper

    def _kept(self, tab: PassportTab, row: list[Cell]) -> list[int]:
        """Indices van de velden die voor het gekozen objecttype gelden (de rest wordt verborgen).
        Indices of the fields that apply to the chosen object type (the others are hidden)."""
        return [i for i, c in enumerate(row) if not self._object_type or tab.applicable(c.label, self._object_type)]

    def _template_row(self, section: Section) -> tuple[int, list[Cell]] | None:
        """Eerste rij zonder weglatingstekens: de voorbeeldrij van een herhaalbare sectie. / First row without
        ellipsis cells: the sample row of a repeatable section."""
        for index, row in enumerate(section.rows):
            if row and not any(set(c.label) <= ELLIPSIS_CHARS for c in row):
                return index, row
        return None

    def _shade(self, colour: str, amount: int) -> str:
        """Iets lichter (donker thema) of donkerder (licht thema) dan ``colour``. / Slightly lighter (dark theme) or
        darker (light theme) than ``colour``."""
        base = QColor(colour)
        return (base.lighter(100 + amount) if base.lightness() < 128 else base.darker(100 + amount)).name()

    def _new_grid(self, holder: QWidget, stretch: list[int]) -> QGridLayout:
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(6)
        for column, value in enumerate(stretch):
            grid.setColumnStretch(column, value)
        return grid

    def _build_repeater(self, tab: PassportTab, section: Section, section_index: int) -> QWidget | None:
        """Herhaalbare sectie zoals iAsset: één kopband en ``REPEATER_ROWS`` voorbeeldrijen met een dunne lijn en
        wisselende achtergrond; de '…'-rij blijft alleen in het Excel-bestand.
        Repeatable section like iAsset: one header band and ``REPEATER_ROWS`` sample rows with a thin line and
        alternating background; the '…' row stays in the Excel file only."""
        template = self._template_row(section)
        if template is None:
            return None
        row_index, row = template
        kept = self._kept(tab, row)
        if not kept:
            return None
        cells = [row[i] for i in kept]
        stretch = self.row_stretch(section_index, row_index, kept)
        p = self._palette
        block = QWidget()
        block.setObjectName("mockRepeater")
        outer = QVBoxLayout(block)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        band = QWidget()
        band.setObjectName("mockRepeatHead")
        grid = self._new_grid(band, stretch)
        for column, cell in enumerate(cells):
            head, _tint, _colour = self._head(tab, cell)
            grid.addWidget(head, 0, column)
        outer.addWidget(band)
        line, zebra = self._shade(p.body, 14), self._shade(p.body, 6)
        for number in range(REPEATER_ROWS):
            frame = QFrame()
            frame.setObjectName("mockRepeatRow")
            background = zebra if number % 2 else "transparent"
            frame.setStyleSheet(
                f"QFrame#mockRepeatRow {{ background: {background}; border: none; border-top: 1px solid {line}; }}",
            )
            row_grid = self._new_grid(frame, stretch)
            row_grid.setContentsMargins(0, 6, 0, 6)
            for column, cell in enumerate(cells):
                row_grid.addWidget(self._value_box(tab, section, cell, pill=True), 0, column)
            outer.addWidget(frame)
        return block

    def _build_table(self, tab: PassportTab, section: Section, section_index: int, heading: QLabel) -> QWidget:
        """Koppeltabel zoals iAsset (bijv. 'Memo'): titel met knoppen, zoekvelden per kolom, 'geen gegevens' en een
        paginering. Linked-object table like iAsset (e.g. 'Memo'): title with buttons, search boxes per column,
        'no data' and a pager."""
        p = self._palette
        template = self._template_row(section)
        row_index, row = template if template else (0, [])
        kept = self._kept(tab, row)
        cells = [row[i] for i in kept]
        stretch = self.row_stretch(section_index, row_index, kept) if cells else []
        table = QWidget()
        table.setObjectName("mockTable")
        outer = QVBoxLayout(table)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(heading)
        top.addStretch(1)
        for glyph in TABLE_ICONS:
            button = QLabel(glyph)
            button.setObjectName("mockTableIcon")
            button.setFixedSize(26, 26)
            button.setAlignment(Qt.AlignmentFlag.AlignCenter)
            button.setStyleSheet(
                f"background: {p.header_band}; color: {p.text}; border-radius: 3px; font-size: 10pt;",
            )
            top.addWidget(button)
        outer.addLayout(top)
        outer.addWidget(self._separator())
        columns = QWidget()
        grid = self._new_grid(columns, stretch)
        grid.setHorizontalSpacing(10)
        for column, cell in enumerate(cells):
            colour = self._highlights.get(label_key(cell.label)) if self._highlights else None
            title = QLabel(self._caption(cell))
            title.setObjectName("mockTableHead")
            title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            title.setStyleSheet(f"color: {p.text}; font-weight: 700; font-size: 8pt; background: transparent;")
            title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            box = QLabel(tr("mock.search", label=cell.label.lower()))
            box.setObjectName("mockSearch")
            box.setMinimumHeight(26)
            box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            border = KIND_COLOURS.get(colour, p.separator) if colour else p.separator
            width = 2 if colour else 1
            box.setStyleSheet(
                f"background: transparent; color: {p.muted}; border: {width}px solid {border}; "
                f"border-radius: 3px; padding: 2px 8px; font-size: 9pt;",
            )
            tips = self._tips(tab, cell, colour)
            title.setToolTip(tips)
            box.setToolTip(tips)
            grid.addWidget(title, 0, column)
            grid.addWidget(box, 1, column)
        outer.addWidget(columns)
        empty = QLabel(tr("mock.no_data"))
        empty.setObjectName("mockNoData")
        empty.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        empty.setStyleSheet(f"color: {p.muted}; font-size: 9pt; padding: 8px 0; background: transparent;")
        outer.addWidget(empty)
        outer.addWidget(self._separator())
        outer.addWidget(self._build_pager())
        return table

    def _build_pager(self) -> QWidget:
        p = self._palette
        pager = QWidget()
        pager.setObjectName("mockPager")
        layout = QHBoxLayout(pager)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)
        layout.addStretch(1)

        def round_button(glyph: str) -> QLabel:
            button = QLabel(glyph)
            button.setObjectName("mockPagerButton")
            button.setFixedSize(24, 24)
            button.setAlignment(Qt.AlignmentFlag.AlignCenter)
            button.setStyleSheet(f"background: {p.header_band}; color: {p.text}; border-radius: 12px; font-size: 10pt;")
            return button

        for glyph in PAGER_FIRST:
            layout.addWidget(round_button(glyph))
        text = QLabel(tr("mock.pager"))
        text.setObjectName("mockPagerText")
        text.setStyleSheet(f"color: {p.text}; font-size: 9pt; padding: 0 8px; background: transparent;")
        layout.addWidget(text)
        for glyph in PAGER_LAST:
            layout.addWidget(round_button(glyph))
        layout.addStretch(1)
        gear = QLabel(GEAR)
        gear.setObjectName("mockGear")
        gear.setStyleSheet(f"color: {p.text}; font-size: 12pt; background: transparent;")
        layout.addWidget(gear)
        return pager

    def _tips(self, tab: PassportTab, cell: Cell, colour: str | None) -> str:
        tips = []
        if cell.footnote:
            tips.append(tr("mock.applies_to", types=", ".join(tab.footnotes.get(cell.footnote, []))))
        if colour:
            tips.append(tr(f"kind.{colour}"))
        return "\n".join(tips)

    def _head(self, tab: PassportTab, cell: Cell) -> tuple[QLabel, str, str | None]:
        """Kopcel in de donkere band: gecentreerde vette tekst. / Header cell in the dark band: centred bold text."""
        p = self._palette
        colour = self._highlights.get(label_key(cell.label)) if self._highlights else None
        head = QLabel(self._caption(cell))
        head.setObjectName("mockHead")
        head.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        head.setWordWrap(True)
        tint = KIND_COLOURS.get(colour, "transparent") if colour else ""
        marker = f"border-bottom: 3px solid {tint};" if tint else ""
        head.setStyleSheet(
            f"background: {p.header_band}; color: {p.text}; font-weight: 700; font-size: 8pt; "
            f"padding: 9px 6px; {marker}",
        )
        head.setMinimumWidth(0)
        head.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        head.setToolTip(self._tips(tab, cell, colour))
        return head, tint, colour

    def _value_box(self, tab: PassportTab, section: Section, cell: Cell, pill: bool = False) -> QWidget:
        """Waardevak, horizontaal gecentreerd in zijn kolom (gelijke marges); de tekst erin staat links met opvulling.
        Value box, horizontally centred in its column (equal margins); the text inside is left-aligned with padding."""
        p = self._palette
        colour = self._highlights.get(label_key(cell.label)) if self._highlights else None
        tint = KIND_COLOURS.get(colour, "") if colour else ""
        value = QLabel(self._sample(section, cell))
        value.setObjectName("mockValue")
        value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        value.setMinimumHeight(26)
        value.setMinimumWidth(0)
        value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        outline = f"border: 2px solid {tint};" if tint else "border: none;"
        background = p.header_band if pill else p.input_bg
        value.setStyleSheet(
            f"background: {background}; color: {p.text}; border-radius: {RADIUS}px; padding: 2px 10px; "
            f"font-size: 9pt; {outline}",
        )
        value.setToolTip(self._tips(tab, cell, colour))
        holder = QWidget()
        holder.setObjectName("mockValueHolder")
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        margin = (100 - BOX_PERCENT) // 2
        layout.addStretch(margin)
        layout.addWidget(value, BOX_PERCENT)
        layout.addStretch(margin)
        return holder

    def _build_row(
        self, tab: PassportTab, section: Section, row: list[Cell], stretch: list[int],
    ) -> QWidget:
        if not row:
            spacer = QWidget()
            spacer.setFixedHeight(SPACER_HEIGHT)
            return spacer
        holder = QWidget()
        holder.setObjectName("mockRow")
        grid = self._new_grid(holder, stretch)
        for column, cell in enumerate(row):
            grid.addWidget(self._head(tab, cell)[0], 0, column)
            grid.addWidget(self._value_box(tab, section, cell), 1, column)
        grid.setRowMinimumHeight(1, 30)
        return holder

    @staticmethod
    def _caption(cell: Cell) -> str:
        return f"{cell.label} ({cell.footnote})" if cell.footnote else cell.label

    def _sample(self, section: Section, cell: Cell) -> str:
        if section.title == BASIS_SECTION and cell.label.casefold() in {"objecttype", "naam"}:
            return self._object_type
        return cell.sample
