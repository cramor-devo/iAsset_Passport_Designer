"""Exporteert paspoortontwerpen naar een Excel-ontwerpbestand (één tabblad per filter) met openpyxl.
Exports passport designs to an Excel design file (one sheet per filter) with openpyxl."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from . import __version__
from .layout_engine import LayoutEngine, notes_section
from .merge_advisor import MergeSuggestion, field_matrix
from .models import PassportTab, RawSheet, Section, SectionStyle, SpecModel, norm

GREY = "D9D9D9"
PURPLE = "D9D2E9"
COLUMN_WIDTH = 30
MARGIN_WIDTH = 70
METADATA_SHEET = "_designer"
REFERENCE_SHEETS = {"objecttypen": "Bron Objecttypen", "attributen": "Bron Attributen"}
METADATA_FORMAT = "1"
INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
BOLD = Font(bold=True)
WRAP_TOP = Alignment(wrap_text=True, vertical="top")


def find_metadata_sheet(workbook: Any) -> str | None:
    """Naam van het verborgen metadatablad: bij voorkeur '_designer', anders een blad dat er qua kop uitziet
    (kop key/value, daarna 'format'). Name of the hidden metadata sheet: preferably '_designer', otherwise a sheet
    with the metadata header (key/value, then 'format')."""
    names = sorted(workbook.sheetnames, key=lambda n: norm(n) != METADATA_SHEET)
    for name in names:
        rows = list(workbook[name].iter_rows(min_row=1, max_row=2, max_col=2, values_only=True))
        head = [tuple(str(v).strip().casefold() if v is not None else "" for v in row) for row in rows]
        if len(head) == 2 and head[0] == ("key", "value") and head[1][0] == "format":
            return str(name)
    return None


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


def _union_columns(sheets: list[RawSheet]) -> list[tuple[str, int]]:
    """Unie van de kopnamen van alle bronnen in volgorde van voorkomen; (kopnaam, n-de keer) houdt dubbele kopnamen
    (GUID, GUID) uit elkaar. / Union of the headers of all sources in order of appearance; (header, n-th occurrence)
    keeps duplicate headers (GUID, GUID) apart."""
    columns: list[tuple[str, int]] = []
    for sheet in sheets:
        seen: dict[str, int] = {}
        for name in sheet.header:
            key = norm(name)
            seen[key] = seen.get(key, 0) + 1
            if (key, seen[key]) not in columns:
                columns.append((key, seen[key]))
    return columns


def _reference_sheet(
    workbook: Workbook, title: str, sheets: list[RawSheet], object_types: set[str], today: str,
) -> None:
    """Ruwe kopie van een bronblad, gefilterd op de geëxporteerde objecttypen, met bron en exportdatum erboven.
    Raw copy of a source sheet, filtered to the exported object types, with source and export date above."""
    sheet = workbook.create_sheet(title)
    multiple = len(sheets) > 1
    sources = ", ".join(s.source for s in sheets)
    sheet.cell(row=1, column=1, value=f"Bron: {sources} | Exportdatum: {today}").font = Font(italic=True)
    columns = _union_columns(sheets)
    names: dict[tuple[str, int], str] = {}
    for source_sheet in sheets:
        seen: dict[str, int] = {}
        for name in source_sheet.header:
            key = norm(name)
            seen[key] = seen.get(key, 0) + 1
            names.setdefault((key, seen[key]), name)
    offset = 1 if multiple else 0
    header_row = 3
    if multiple:
        sheet.cell(row=header_row, column=1, value="Bron")
    for index, column in enumerate(columns, start=1 + offset):
        sheet.cell(row=header_row, column=index, value=names[column] or None)
    for cell in sheet[header_row]:
        cell.font, cell.fill = BOLD, PatternFill("solid", fgColor=GREY)
    row_number = header_row + 1
    for source_sheet in sheets:
        type_index = next((i for i, h in enumerate(source_sheet.header) if norm(h) == "objecttype"), None)
        if type_index is None:
            continue
        positions: dict[tuple[str, int], int] = {}
        seen: dict[str, int] = {}
        for position, name in enumerate(source_sheet.header):
            key = norm(name)
            seen[key] = seen.get(key, 0) + 1
            positions[(key, seen[key])] = position
        for row in source_sheet.rows:
            if norm(str(row[type_index] or "")) not in object_types:
                continue
            if multiple:
                sheet.cell(row=row_number, column=1, value=source_sheet.source)
            for index, column in enumerate(columns, start=1 + offset):
                position = positions.get(column)
                if position is not None and row[position] is not None:
                    sheet.cell(row=row_number, column=index, value=row[position])
            row_number += 1
    sheet.freeze_panes = sheet.cell(row=header_row + 1, column=1)
    for index in range(1, len(columns) + offset + 1):
        sheet.column_dimensions[get_column_letter(index)].width = 24


def add_reference_sheets(workbook: Workbook, spec: SpecModel, tabs: list[PassportTab], used: set[str]) -> list[str]:
    """Voeg 'Bron Objecttypen' en 'Bron Attributen' toe (ruwe kopie van de spec, gefilterd op de objecttypen van
    ``tabs``). Zonder ruwe gegevens in ``spec`` gebeurt er niets. Geeft de toegevoegde bladnamen terug.
    Add 'Bron Objecttypen' and 'Bron Attributen' (raw copy of the spec, filtered to the object types of ``tabs``).
    Does nothing when ``spec`` has no raw data. Returns the names of the added sheets."""
    object_types = {norm(o.name) for tab in tabs for o in tab.object_types}
    engine = LayoutEngine(spec)
    # Objecttypen zonder eigen attributen erven van een bronobjecttype; die attribuutrijen horen er ook bij.
    # Object types without own attributes inherit from a source type; those attribute rows belong too.
    with_sources = object_types | {norm(engine._source_type(o.name)) for tab in tabs for o in tab.object_types}
    today = date.today().isoformat()
    added: list[str] = []
    for key, title in REFERENCE_SHEETS.items():
        sheets = spec.raw_sheets.get(key, [])
        if not sheets:
            continue
        name = sheet_title(title, used)
        _reference_sheet(workbook, name, sheets, with_sources if key == "attributen" else object_types, today)
        added.append(name)
    return added


def write_metadata(
    workbook: Workbook, tabs: list[PassportTab], titles: list[str], spec: SpecModel | None, used: set[str],
    reference_sheets: list[str] | None = None,
) -> None:
    """Verborgen blad '_designer' met sleutel/waarde-regels (versie, profiel, bronnen, filterkolom en per ontwerpblad
    de objecttypen, samenvoeging en voetnoten als JSON). Hidden '_designer' sheet with key/value rows (version,
    profile, sources, filter column and per design sheet the object types, merge and footnotes as JSON)."""
    sheet = workbook.create_sheet(sheet_title(METADATA_SHEET, used))
    sheet.append(["key", "value"])
    sheet.append(["format", METADATA_FORMAT])
    sheet.append(["metadata_sheet", sheet.title])
    sheet.append(["reference_sheets", json.dumps(reference_sheets or [], ensure_ascii=False)])
    sheet.append(["app_version", __version__])
    sheet.append(["profile", tabs[0].profile.key])
    sheet.append(["sources", json.dumps(spec.sources if spec else [], ensure_ascii=False)])
    sheet.append(["filter_column", spec.filter_column if spec else ""])
    sheet.append(["generated", datetime.now().isoformat(timespec="seconds")])
    for title, tab in zip(titles, tabs, strict=True):
        info = {
            "tab": tab.name,
            "object_types": [o.name for o in tab.object_types],
            "merged_from": list(tab.merged_from),
            "footnotes": {str(n): list(names) for n, names in sorted(tab.footnotes.items())},
        }
        sheet.append([f"sheet:{title}", json.dumps(info, ensure_ascii=False)])
    sheet.column_dimensions["A"].width = 28
    sheet.column_dimensions["B"].width = 100
    sheet.sheet_state = "hidden"


def export_workbook(
    tabs: list[PassportTab], path: str | Path, sheet_names: list[str] | None = None, spec: SpecModel | None = None,
) -> Path:
    """Schrijf alle ontwerpen naar één xlsx-bestand; ``sheet_names`` vervangt desgewenst de tabbladnamen (bijv. per
    objecttype). Met ``spec`` komen er bronbladen bij ('Bron Objecttypen', 'Bron Attributen'); altijd komt er een
    verborgen blad '_designer' met metadata bij.
    Write all designs to one xlsx file; ``sheet_names`` optionally replaces the sheet names. With ``spec`` the
    reference sheets ('Bron Objecttypen', 'Bron Attributen') are added; a hidden '_designer' sheet always is."""
    if not tabs:
        raise ValueError("No passport designs to export.")
    workbook = Workbook()
    default_sheet = workbook.active
    if default_sheet is not None:
        workbook.remove(default_sheet)
    used: set[str] = set()
    references: list[str] = []
    names = sheet_names if sheet_names is not None and len(sheet_names) == len(tabs) else [t.name for t in tabs]
    titles: list[str] = []
    for tab, name in zip(tabs, names, strict=True):
        sheet = workbook.create_sheet(sheet_title(name, used))
        titles.append(sheet.title)
        write_tab(sheet, tab)
    if spec is not None:
        references = add_reference_sheets(workbook, spec, tabs, used)
    write_metadata(workbook, tabs, titles, spec, used, references)
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
