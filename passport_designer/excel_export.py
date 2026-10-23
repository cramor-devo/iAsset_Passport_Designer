"""Exporteert paspoortontwerpen naar een Excel-ontwerpbestand (één tabblad per filter) met openpyxl.
Exports passport designs to an Excel design file (one sheet per filter) with openpyxl."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .layout_engine import notes_section
from .merge_advisor import MergeSuggestion, field_matrix
from .models import PassportTab, Section, SectionStyle

GREY = "D9D9D9"
PURPLE = "D9D2E9"
COLUMN_WIDTH = 30
MARGIN_WIDTH = 70
INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
BOLD = Font(bold=True)
WRAP_TOP = Alignment(wrap_text=True, vertical="top")


def sheet_title(name: str, used: set[str]) -> str:
    """Geldige, unieke tabbladnaam (max. 31 tekens, zonder []:*?/\\). / Valid, unique sheet name (max 31 chars)."""
    base = INVALID_SHEET_CHARS.sub("_", name).strip("'") or "Sheet"
    candidate, number = base[:31], 2
    while candidate.casefold() in used:
        suffix = f" ({number})"
        candidate = base[: 31 - len(suffix)] + suffix
        number += 1
    used.add(candidate.casefold())
    return candidate


@dataclass(frozen=True)
class SheetCell:
    """Eén cel van een ontwerpblad (1-gebaseerd), gedeeld door de Excel-export en het voorbeeld in de UI.
    One cell of a design sheet (1-based), shared by the Excel export and the preview in the UI."""

    row: int
    column: int
    value: str = ""
    fill: str = ""  # RGB-kleur / RGB colour
    bold: bool = False
    italic: bool = False
    size: int | None = None
    wrap: bool = False
    merge_to: int = 0  # laatste kolom bij samengevoegde cellen / last column of merged cells


@dataclass
class SheetLayout:
    """Ontwerpblad: cellen plus kolombreedtes (in Excel-tekens). / Design sheet: cells plus column widths."""

    cells: list[SheetCell] = field(default_factory=list)
    widths: dict[int, int] = field(default_factory=dict)

    @property
    def row_count(self) -> int:
        return max((c.row for c in self.cells), default=0)

    @property
    def column_count(self) -> int:
        return max([*(max(c.column, c.merge_to) for c in self.cells), *self.widths], default=0)


def _heading(cells: list[SheetCell], row: int, section: Section, tab: PassportTab) -> None:
    colour = tab.profile.semantic_fill if section.style is SectionStyle.SEMANTIC else GREY
    cells.append(SheetCell(row, 1, section.title, fill=colour, bold=True))
    cells.extend(SheetCell(row, column, fill=colour) for column in range(2, tab.profile.grid_columns + 1))


def sheet_layout(tab: PassportTab) -> SheetLayout:
    """Indeling van één paspoortontwerp zoals in het paspoortinrichting-bestand: titel, objecttypen eronder, secties
    met grijze/blauwe koppen, een lege kolom en de opmerkingen (verwijzingen naar objecttypen) ernaast.
    Layout of one passport design as in the passport design file: title, object types below, sections with
    grey/blue headings, an empty column and the remarks (references to object types) beside them."""
    profile = tab.profile
    columns = profile.grid_columns
    margin_column = columns + 2  # één lege kolom tussen raster en opmerkingen / one empty column before the remarks
    layout = SheetLayout()
    cells = layout.cells
    row = 1
    if profile.header_lines:
        cells.append(SheetCell(1, 1, tab.name, bold=True, size=18))
        names = ", ".join(o.name for o in tab.object_types)
        cells.append(SheetCell(2, 1, f"Objecttypes: {names}", italic=True))
        row = 4
    sections = list(tab.sections)
    notes = notes_section(tab)
    if notes:
        sections.append(notes)
    for index, section in enumerate(sections):
        if index:
            row += 1  # witregel tussen secties / blank line between sections
        _heading(cells, row, section, tab)
        if profile.margin_notes and index == 0:
            cells.append(SheetCell(row, margin_column, "Opmerkingen"))
        row += 1
        for row_index, row_cells in enumerate(section.rows):
            is_notes = section.style is SectionStyle.NOTES
            for column, cell in enumerate(row_cells, start=1):
                bold = profile.bold_fields and not is_notes
                merge_to = columns if is_notes and column == 1 and columns > 1 else 0
                cells.append(SheetCell(row, column, cell.display, bold=bold, wrap=True, merge_to=merge_to))
            remark = section.margin.get(row_index)
            if remark:
                cells.append(SheetCell(row, margin_column, remark, wrap=True))
            row += 1
    layout.widths = {column: COLUMN_WIDTH for column in range(1, columns + 1)}
    if profile.margin_notes:
        layout.widths[margin_column] = MARGIN_WIDTH
    return layout


def write_tab(sheet: Worksheet, tab: PassportTab) -> None:
    """Schrijf één paspoortontwerp naar een tabblad. / Write one passport design to a sheet."""
    layout = sheet_layout(tab)
    for item in layout.cells:
        target = sheet.cell(row=item.row, column=item.column, value=item.value or None)
        if item.fill:
            target.fill = PatternFill("solid", fgColor=item.fill)
        if item.bold or item.italic or item.size:
            target.font = Font(bold=item.bold, italic=item.italic, size=item.size)
        if item.wrap:
            target.alignment = WRAP_TOP
        if item.merge_to:
            sheet.merge_cells(start_row=item.row, start_column=item.column, end_row=item.row, end_column=item.merge_to)
    for column, width in layout.widths.items():
        sheet.column_dimensions[get_column_letter(column)].width = width


def export_workbook(tabs: list[PassportTab], path: str | Path, sheet_names: list[str] | None = None) -> Path:
    """Schrijf alle ontwerpen naar één xlsx-bestand; ``sheet_names`` vervangt desgewenst de tabbladnamen (bijv. per
    objecttype). / Write all designs to one xlsx file; ``sheet_names`` optionally replaces the sheet names."""
    if not tabs:
        raise ValueError("No passport designs to export.")
    workbook = Workbook()
    default_sheet = workbook.active
    if default_sheet is not None:
        workbook.remove(default_sheet)
    used: set[str] = set()
    names = sheet_names if sheet_names is not None and len(sheet_names) == len(tabs) else [t.name for t in tabs]
    for tab, name in zip(tabs, names, strict=True):
        write_tab(workbook.create_sheet(sheet_title(name, used)), tab)
    target = Path(path)
    workbook.save(target)
    return target


SUMMARY_HEADERS = (
    "Samengevoegd paspoort", "Filters", "Objecttypen", "Gelijkenis", "Velden totaal", "Gemeenschappelijk",
    "Per subthema (voetnoot)", "Laagste pasvorm",
)
HEADER_FILL = PatternFill("solid", fgColor=GREY)
PARTIAL_FILL = PatternFill("solid", fgColor=PURPLE)


def export_merge_report(suggestions: list[MergeSuggestion], path: str | Path) -> Path:
    """Schrijf de samenvoegsuggesties: een samenvatting plus per suggestie een matrix veld x objecttype (subthema).
    Write the merge suggestions: a summary plus per suggestion a field x object type (sub-theme) matrix."""
    if not suggestions:
        raise ValueError("No merge suggestions to export.")
    workbook = Workbook()
    summary = workbook.active
    if summary is None:
        raise ValueError("Cannot create a worksheet.")
    summary.title = "Samenvatting"
    summary.append(list(SUMMARY_HEADERS))
    used = {"samenvatting"}
    for item in suggestions:
        summary.append([
            item.name, ", ".join(item.members), item.object_type_count, round(item.similarity, 2), item.total_fields,
            item.common_fields, item.partial_fields, round(item.lowest_fit, 2),
        ])
    for cell in summary[1]:
        cell.font, cell.fill = BOLD, HEADER_FILL
    for column, width in zip("ABCDEFGH", (28, 40, 12, 12, 14, 18, 22, 16), strict=True):
        summary.column_dimensions[column].width = width

    for item in suggestions:
        if item.tab is None:
            continue
        sheet = workbook.create_sheet(sheet_title(item.name, used))
        types = [o.name for o in item.tab.object_types]
        sheet.append(["Veld", "Geldt voor alle", *types])
        for cell in sheet[1]:
            cell.font, cell.fill, cell.alignment = BOLD, HEADER_FILL, Alignment(wrap_text=True, vertical="top")
        for label, applies_to, everywhere in field_matrix(item.tab):
            sheet.append([label, "Ja" if everywhere else "Nee", *["✓" if t in applies_to else "" for t in types]])
            if not everywhere:
                for cell in sheet[sheet.max_row]:
                    cell.fill = PARTIAL_FILL
        sheet.column_dimensions["A"].width = 34
        sheet.column_dimensions["B"].width = 16
        sheet.freeze_panes = "C2"
    target = Path(path)
    workbook.save(target)
    return target
