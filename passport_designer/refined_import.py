"""Leest een (handmatig bijgewerkt) Excel-ontwerpbestand terug als paspoortontwerpen (PassportTab) met celposities,
kolombreedtes en metadata. Gebruikt het verborgen blad '_designer' en valt anders terug op opmaakheuristieken.
Reads a (manually refined) Excel design file back as passport designs (PassportTab) with cell positions, column
widths and metadata. Uses the hidden '_designer' sheet and otherwise falls back to styling heuristics."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from .compare import ELLIPSIS_CHARS
from .design_rules import SECTION_NOTES
from .excel_export import GREY, METADATA_SHEET, PURPLE, REFERENCE_SHEETS, find_metadata_sheet
from .layout_engine import semantic_style
from .models import Cell, ObjectType, PassportTab, Section, SectionStyle, SpecModel, norm
from .profiles import LEGACY, PROFILES, ROTTERDAM_V3, DesignProfile

OBJECT_TYPES_LINE = "objecttypes:"
MARGIN_HEADER = "opmerkingen"
FOOTNOTE_REMARK = re.compile(r"\((\d+)\)\s*Objecttype:\s*([^;]*)", re.IGNORECASE)
NOTE_LINE = re.compile(r"^(\(\d+\)\s*Objecttype|\*+\s+\S)", re.IGNORECASE)
TRAILING_FOOTNOTE = re.compile(r"\s*\((\d+)\)\s*$")
MERGED_NOTE = re.compile(r"^Samengevoegd uit filters:\s*(.*)$", re.IGNORECASE)
HEADING_SCAN_ROWS = 6
DEFAULT_WIDTH = 8.43
# Alleen gebruikt voor bestanden zonder metadata. / Only used for files without metadata.
SKIPPED_SHEETS = {norm(name) for name in (METADATA_SHEET, *REFERENCE_SHEETS.values())}
Position = tuple[int, int]


@dataclass
class RefinedSheet:
    """Eén ingelezen ontwerpblad. ``positions`` koppelt (sectie, rij, kolom) aan de Excel-cel (rij, kolom), 1-gebaseerd;
    ``label_positions`` koppelt de genormaliseerde veldnaam aan de eerste cel; ``heading_rows`` en
    ``margin_positions`` geven de Excel-rij van de sectiekop en van de opmerking per (sectie, rij).
    ``column_widths`` zijn de breedtes van de rasterkolommen (Excel-tekens).
    One imported design sheet. ``positions`` maps (section, row, column) to the 1-based Excel cell (row, column);
    ``label_positions`` maps the normalised field name to its first cell; ``heading_rows`` and ``margin_positions``
    give the Excel row of the section heading and of the remark per (section, row). ``column_widths`` are the widths
    of the grid columns (Excel characters)."""

    name: str
    tab: PassportTab
    positions: dict[tuple[int, int, int], Position] = field(default_factory=dict)
    label_positions: dict[str, Position] = field(default_factory=dict)
    heading_rows: list[int] = field(default_factory=list)
    margin_positions: dict[tuple[int, int], Position] = field(default_factory=dict)
    column_widths: list[float] = field(default_factory=list)
    margin_column: int | None = None
    margin_width: float | None = None
    meta_key: str | None = None  # sleutel in metadata['sheets'] (kan afwijken van de bladnaam) / key in metadata
    metadata: dict[str, Any] | None = None  # blokje van dit blad uit '_designer' / this sheet's '_designer' entry
    warnings: list[str] = field(default_factory=list)


@dataclass
class RefinedWorkbook:
    """Ingelezen bestand: metadata (of None), ontwerpbladen en waarschuwingen. / Imported file: metadata (or None),
    design sheets and warnings."""

    path: Path
    metadata: dict[str, Any] | None = None
    sheets: list[RefinedSheet] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def split_label(value: object) -> tuple[str, int | None]:
    """Veldnaam zonder voetnootnummer en sterretjes, plus het nummer (of None). / Field name without footnote number
    and asterisks, plus the number (or None)."""
    text = " ".join(str(value).split())
    footnote: int | None = None
    while True:
        stripped = text.strip().strip("*").strip()
        match = TRAILING_FOOTNOTE.search(stripped)
        if match and footnote is None:
            footnote = int(match.group(1))
            stripped = stripped[: match.start()].strip()
        if stripped == text:
            return text, footnote
        text = stripped


def read_metadata(path: str | Path) -> dict[str, Any] | None:
    """Lees het verborgen blad '_designer' (None als het ontbreekt). / Read the hidden '_designer' sheet."""
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        return _metadata(workbook)
    finally:
        workbook.close()


def _metadata(workbook: Any) -> dict[str, Any] | None:
    name = find_metadata_sheet(workbook)
    if name is None:
        return None
    result: dict[str, Any] = {"sheets": {}}
    for row in workbook[name].iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None or row[1] is None:
            continue
        key, value = str(row[0]), str(row[1])
        try:
            if key.startswith("sheet:"):
                info = json.loads(value)
                info["footnotes"] = {int(n): list(names) for n, names in info.get("footnotes", {}).items()}
                result["sheets"][key[len("sheet:") :]] = info
            elif key in ("sources", "reference_sheets"):
                result[key] = list(json.loads(value))
            else:
                result[key] = value
        except (ValueError, TypeError, AttributeError):
            continue
    return result


def _rgb(cell: Any) -> str:
    colour = cell.fill.fgColor.rgb if cell.fill is not None and cell.fill.fill_type == "solid" else ""
    return colour.upper() if isinstance(colour, str) else ""


def _is_filled(cell: Any) -> bool:
    return cell.fill is not None and cell.fill.fill_type == "solid"


def _text(cell: Any) -> str:
    return "" if cell.value is None else str(cell.value).strip()


def _find_margin_column(sheet: Worksheet) -> int | None:
    for row in sheet.iter_rows(max_row=min(sheet.max_row, 60)):
        for cell in row:
            if norm(_text(cell)) == MARGIN_HEADER:
                return cell.column
    return None


def _widths(sheet: Worksheet, count: int) -> list[float]:
    by_column: dict[int, float] = {}
    for dimension in sheet.column_dimensions.values():
        if dimension.width and dimension.min and dimension.max:
            for column in range(dimension.min, min(dimension.max, 200) + 1):
                by_column[column] = float(dimension.width)
    default = float(sheet.sheet_format.defaultColWidth or DEFAULT_WIDTH)
    return [by_column.get(column, default) for column in range(1, count + 1)]


def _object_types(names: list[str], spec: SpecModel | None, warnings: list[str]) -> list[ObjectType]:
    known = {norm(o.name): o for o in spec.object_types} if spec else {}
    result: list[ObjectType] = []
    for name in names:
        match = known.get(norm(name))
        if match is None:
            if spec is not None:
                warnings.append(f"Object type '{name}' is not in the specification.")
            match = ObjectType(name, "")
        if all(o.name != match.name for o in result):
            result.append(match)
    return result


def _section_style(title: str, colour: str, profile: DesignProfile) -> SectionStyle:
    if colour.endswith(GREY):
        return SectionStyle.PLAIN
    if colour.endswith((profile.semantic_fill, PURPLE)):
        return SectionStyle.SEMANTIC
    return semantic_style(title)


def _is_heading(sheet: Worksheet, row: int, grid_end: int) -> bool:
    first = sheet.cell(row=row, column=1)
    if not _text(first) or not _is_filled(first):
        return False
    return not any(_text(sheet.cell(row=row, column=c)) for c in range(2, grid_end + 1))


def _looks_like_design(sheet: Worksheet, grid_end: int) -> bool:
    second = _text(sheet.cell(row=2, column=1))
    if second.casefold().startswith(OBJECT_TYPES_LINE):
        return True
    return any(
        _is_heading(sheet, row, grid_end) and norm(_text(sheet.cell(row=row, column=1))) == "basis"
        for row in range(1, HEADING_SCAN_ROWS + 1)
    )


def _add_footnotes(text: str, footnotes: dict[int, list[str]]) -> None:
    for match in FOOTNOTE_REMARK.finditer(text):
        names = [n.strip() for n in match.group(2).split(",") if n.strip()]
        footnotes.setdefault(int(match.group(1)), names)


def _header_of(sheet: Worksheet) -> tuple[str, list[str]]:
    """Titel (A1) en objecttypenamen (A2) van een blad met kop. / Title (A1) and object type names (A2) of a sheet."""
    second = _text(sheet.cell(row=2, column=1))
    if not second.casefold().startswith(OBJECT_TYPES_LINE):
        return "", []
    names = [t.strip() for t in second.split(":", 1)[1].split(",") if t.strip()]
    return _text(sheet.cell(row=1, column=1)), names


def _match_metadata(
    sheet: Worksheet, workbook_meta: dict[str, Any] | None, claimed: set[str],
) -> tuple[str | None, dict[str, Any] | None]:
    """Metadata van een blad: op bladnaam; bij een hernoemd blad op de tabnaam in A1, anders op dezelfde set
    objecttypen. ``claimed`` bevat sleutels die al aan een blad zijn gekoppeld.
    Metadata of a sheet: by sheet name; for a renamed sheet by the tab name in A1, else by the same set of object
    types. ``claimed`` holds keys already linked to a sheet."""
    entries: dict[str, Any] = (workbook_meta or {}).get("sheets", {})
    if sheet.title in entries:
        return sheet.title, entries[sheet.title]
    title, names = _header_of(sheet)
    free = [(key, info) for key, info in entries.items() if key not in claimed]
    if title:
        for key, info in free:
            if norm(str(info.get("tab", ""))) == norm(title):
                return key, info
    wanted = {norm(n) for n in names}
    if wanted:
        for key, info in free:
            if {norm(n) for n in info.get("object_types", [])} == wanted:
                return key, info
    return None, None


def _read_sheet(
    sheet: Worksheet, spec: SpecModel | None, workbook_meta: dict[str, Any] | None, claimed: set[str] | None = None,
) -> RefinedSheet | None:
    meta_key, sheet_meta = _match_metadata(sheet, workbook_meta, claimed if claimed is not None else set())
    margin = _find_margin_column(sheet)
    grid_end = (margin - 1) if margin else max(sheet.max_column, 1)
    if sheet_meta is None and not _looks_like_design(sheet, grid_end):
        return None
    warnings: list[str] = []
    profile_key = (workbook_meta or {}).get("profile", "")
    profile = PROFILES.get(profile_key) or (ROTTERDAM_V3 if margin else LEGACY)
    if margin is None:
        warnings.append("No 'Opmerkingen' margin column found; remarks are not imported.")

    second = _text(sheet.cell(row=2, column=1))
    has_header = second.casefold().startswith(OBJECT_TYPES_LINE)
    title = _text(sheet.cell(row=1, column=1)) if has_header else ""
    type_names = [t.strip() for t in second.split(":", 1)[1].split(",") if t.strip()] if has_header else []
    if not type_names and sheet_meta:
        type_names = list(sheet_meta.get("object_types", []))
    tab_name = (sheet_meta or {}).get("tab") or title or sheet.title
    types = _object_types(type_names, spec, warnings)
    if not types and spec is not None:
        types = list(spec.filters().get(tab_name, []))
    if not types:
        warnings.append("The object types of this sheet could not be determined.")
    tab = PassportTab(tab_name, next((o.group for o in types if o.group), ""), types, profile=profile)
    tab.merged_from = list((sheet_meta or {}).get("merged_from", []))

    result = RefinedSheet(
        sheet.title, tab, margin_column=margin, meta_key=meta_key, metadata=sheet_meta, warnings=warnings,
    )
    section: Section | None = None
    notes_mode = False
    pending_blank = False
    used_columns = 1
    first_row = 3 if has_header else 1
    for row in range(first_row, sheet.max_row + 1):
        if _is_heading(sheet, row, grid_end):
            first = sheet.cell(row=row, column=1)
            heading = _text(first)
            notes_mode = norm(heading) == norm(SECTION_NOTES)
            pending_blank = False
            if notes_mode:
                section = None
                continue
            style = _section_style(heading, _rgb(first), profile)
            section = Section(heading, style)
            tab.sections.append(section)
            result.heading_rows.append(row)
            continue
        cells = [(c, _text(sheet.cell(row=row, column=c))) for c in range(1, grid_end + 1)]
        cells = [(c, t) for c, t in cells if t]
        remark = _text(sheet.cell(row=row, column=margin)) if margin else ""
        if remark:
            _add_footnotes(remark, tab.footnotes)
        if notes_mode or section is None:
            for _, text in cells:
                _note(tab, text)
            continue
        fields: list[tuple[int, str]] = []
        for column, text in cells:
            if NOTE_LINE.match(text) or MERGED_NOTE.match(text):
                _note(tab, text)
            else:
                fields.append((column, text))
        if not fields and not remark:
            pending_blank = bool(section.rows)
            continue
        if pending_blank:
            section.rows.append([])
            pending_blank = False
        row_index = len(section.rows)
        section_index = len(tab.sections) - 1
        row_cells: list[Cell] = []
        for column, text in fields:
            label, footnote = split_label(text)
            if not label:
                continue
            row_cells.append(Cell(label, footnote))
            result.positions[(section_index, row_index, len(row_cells) - 1)] = (row, column)
            result.label_positions.setdefault(norm(label), (row, column))
            used_columns = max(used_columns, column)
        section.rows.append(row_cells)
        if remark:
            section.margin[row_index] = remark
            assert margin is not None
            result.margin_positions[(section_index, row_index)] = (row, margin)
    for section in tab.sections:
        section.repeater = _is_repeater(section)
    _finish(result, sheet, used_columns, margin, grid_end)
    return result


def _note(tab: PassportTab, text: str) -> None:
    merged = MERGED_NOTE.match(text)
    if merged:
        if not tab.merged_from:
            tab.merged_from = [n.strip() for n in merged.group(1).split(",") if n.strip()]
        return
    if FOOTNOTE_REMARK.search(text):
        _add_footnotes(text, tab.footnotes)
    if text not in tab.notes:
        tab.notes.append(text)


def _is_repeater(section: Section) -> bool:
    rows = [r for r in section.rows if r]
    if len(rows) < 2 or not all(set(c.label) <= ELLIPSIS_CHARS for c in rows[-1]):
        return False
    return [c.label for c in rows[0]] == [c.label for c in rows[1]]


def _finish(result: RefinedSheet, sheet: Worksheet, used_columns: int, margin: int | None, grid_end: int) -> None:
    tab = result.tab
    heading_fill = max(
        (c for row in result.heading_rows for c in range(1, grid_end + 1) if _is_filled(sheet.cell(row=row, column=c))),
        default=1,
    )
    count = max(used_columns, heading_fill, 1)
    if margin:
        count = min(count, margin - 1)
    result.column_widths = _widths(sheet, count)
    if margin:
        result.margin_width = _widths(sheet, margin)[-1]
    sheet_meta = result.metadata or {}
    for number, names in sheet_meta.get("footnotes", {}).items():
        tab.footnotes.setdefault(number, list(names))
    tab.footnotes = dict(sorted(tab.footnotes.items()))


def read_refined(path: str | Path, spec: SpecModel | None = None) -> RefinedWorkbook:
    """Lees een Excel-ontwerpbestand (eigen export of handmatig bijgewerkt) als ontwerpen. Bladen 'Bron …' en
    '_designer' en bladen die niet op een ontwerp lijken worden overgeslagen (met waarschuwing).
    Read an Excel design file (own export or manually refined) as designs. 'Bron …' sheets, '_designer' and sheets
    that do not look like a design are skipped (with a warning)."""
    file_path = Path(path)
    workbook = load_workbook(file_path, data_only=True)
    result = RefinedWorkbook(file_path)
    try:
        result.metadata = _metadata(workbook)
        meta = result.metadata
        metadata_name = find_metadata_sheet(workbook)
        entries: dict[str, Any] = meta["sheets"] if meta else {}
        recorded = meta.get("reference_sheets") if meta else None
        references = {norm(n) for n in recorded} if isinstance(recorded, list) else SKIPPED_SHEETS
        claimed = {title for title in workbook.sheetnames if title in entries}
        for sheet in workbook.worksheets:
            if sheet.title == metadata_name:
                continue
            if meta is None:
                skip = norm(sheet.title) in SKIPPED_SHEETS
            else:
                skip = sheet.title not in entries and norm(sheet.title) in references
            if skip:
                continue
            refined = _read_sheet(sheet, spec, result.metadata, claimed)
            if refined is None:
                result.warnings.append(f"Sheet '{sheet.title}' does not look like a passport design; skipped.")
                continue
            if refined.meta_key is not None:
                claimed.add(refined.meta_key)
            result.sheets.append(refined)
    finally:
        workbook.close()
    return result
