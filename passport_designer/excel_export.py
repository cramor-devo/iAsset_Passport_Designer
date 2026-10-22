"""Exporteert paspoortontwerpen naar een Excel-ontwerpbestand (één tabblad per filter) met openpyxl.
Exports passport designs to an Excel design file (one sheet per filter) with openpyxl."""

from __future__ import annotations

import re
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


def _heading(sheet: Worksheet, row: int, section: Section, tab: PassportTab) -> None:
    colour = tab.profile.semantic_fill if section.style is SectionStyle.SEMANTIC else GREY
    fill = PatternFill("solid", fgColor=colour)
    for column in range(1, tab.profile.grid_columns + 1):
        sheet.cell(row=row, column=column).fill = fill
    sheet.cell(row=row, column=1, value=section.title).font = BOLD


def write_tab(sheet: Worksheet, tab: PassportTab) -> None:
    """Schrijf één paspoortontwerp naar een tabblad. / Write one passport design to a sheet."""
    profile = tab.profile
    columns = profile.grid_columns
    margin_column = columns + 2  # één lege kolom tussen raster en opmerkingen / one empty column before the remarks
    row = 1
    if profile.header_lines:
        sheet.cell(row=1, column=1, value=tab.name).font = Font(bold=True, size=18)
        names = ", ".join(o.name for o in tab.object_types)
        sheet.cell(row=2, column=1, value=f"Objecttypes: {names}").font = Font(italic=True)
        row = 4
    sections = list(tab.sections)
    notes = notes_section(tab)
    if notes:
        sections.append(notes)
    for index, section in enumerate(sections):
        if index:
            row += 1  # witregel tussen secties / blank line between sections
        _heading(sheet, row, section, tab)
        if profile.margin_notes and index == 0:
            sheet.cell(row=row, column=margin_column, value="Opmerkingen")
        row += 1
        for row_index, cells in enumerate(section.rows):
            for column, cell in enumerate(cells, start=1):
                target = sheet.cell(row=row, column=column, value=cell.display)
                target.alignment = WRAP_TOP
                if profile.bold_fields and section.style is not SectionStyle.NOTES:
                    target.font = BOLD
            if section.style is SectionStyle.NOTES and cells:
                sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=columns)
            remark = section.margin.get(row_index)
            if remark:
                sheet.cell(row=row, column=margin_column, value=remark).alignment = WRAP_TOP
            row += 1
    for column in range(1, columns + 1):
        sheet.column_dimensions[get_column_letter(column)].width = COLUMN_WIDTH
    if profile.margin_notes:
        sheet.column_dimensions[get_column_letter(margin_column)].width = MARGIN_WIDTH


def export_workbook(tabs: list[PassportTab], path: str | Path) -> Path:
    """Schrijf alle ontwerpen naar één xlsx-bestand. / Write all designs to one xlsx file."""
    if not tabs:
        raise ValueError("No passport designs to export.")
    workbook = Workbook()
    default_sheet = workbook.active
    if default_sheet is not None:
        workbook.remove(default_sheet)
    used: set[str] = set()
    for tab in tabs:
        write_tab(workbook.create_sheet(sheet_title(tab.name, used)), tab)
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
