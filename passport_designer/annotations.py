"""Controleert en herstelt voetnootmarkeringen '(n)' en opmerkingen in Excel-ontwerpbladen na handmatig verplaatsen.
Checks and repairs footnote markers '(n)' and margin remarks in Excel design sheets after manual moves.
Issue kinds: wrong-types, missing-marker, unexpected-marker, duplicate-number, gap, order, margin-missing,
margin-mismatch, margin-orphan, unknown-label."""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .design_rules import SECTION_OBJECT
from .excel_export import WRAP_TOP, find_metadata_sheet
from .layout_engine import LayoutEngine
from .models import ObjectType, SpecModel, norm
from .refined_import import FOOTNOTE_REMARK, MARGIN_HEADER, RefinedSheet, read_refined

FOOTNOTE_PART = re.compile(r"^\(\d+\)\s*Objecttype:", re.IGNORECASE)
MARKER_AT_END = re.compile(r"\s*\((\d+)\)(?=[\s*]*$)")
TRAILING_STARS = re.compile(r"^(.*?)(\s*\**)$", re.DOTALL)
ELLIPSIS_CHARS = set("….· ")

WRONG_TYPES = "wrong-types"
MISSING_MARKER = "missing-marker"
UNEXPECTED_MARKER = "unexpected-marker"
DUPLICATE_NUMBER = "duplicate-number"
GAP = "gap"
ORDER = "order"
MARGIN_MISSING = "margin-missing"
MARGIN_MISMATCH = "margin-mismatch"
MARGIN_ORPHAN = "margin-orphan"
UNKNOWN_LABEL = "unknown-label"


@dataclass(frozen=True)
class AnnotationIssue:
    """Eén bevinding. ``cell`` is een Excel-coördinaat ('B12') of '' voor het hele blad.
    One finding. ``cell`` is an Excel coordinate ('B12') or '' for the whole sheet."""

    sheet: str
    cell: str
    kind: str  # zie module-docstring / see module docstring
    severity: str  # error | warning | info
    detail: str


@dataclass
class AnnotationReport:
    """Resultaat van de controle. / Result of the check."""

    path: Path
    issues: list[AnnotationIssue] = field(default_factory=list)
    sheets_checked: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Geen fouten of waarschuwingen (info telt niet). / No errors or warnings (info does not count)."""
        return not any(i.severity in ("error", "warning") for i in self.issues)

    def for_sheet(self, name: str) -> list[AnnotationIssue]:
        return [i for i in self.issues if i.sheet == name]


@dataclass
class FixResult:
    """Resultaat van het herstel: nieuw bestand, wijzigingen en de controle erna.
    Result of the repair: new file, changes and the check afterwards."""

    out_path: Path
    changes: list[str] = field(default_factory=list)
    report_after: AnnotationReport = field(default_factory=lambda: AnnotationReport(Path(".")))
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Field:
    section: int
    row: int  # Excel
    column: int
    label: str
    key: str
    number: int | None
    text: str


@dataclass
class _Remark:
    cell: str
    parts: dict[int, list[str]]


@dataclass
class _Expected:
    """Gewenst type per veld: ``marked`` en de objecttypen (None = onbekend). / Wanted state per field."""

    marked: bool
    types: list[str] | None
    known: bool  # label staat in de spec / label is in the spec


def _coordinate(row: int, column: int) -> str:
    return f"{get_column_letter(column)}{row}"


def _type_key(names: list[str] | None) -> frozenset[str] | None:
    return None if names is None else frozenset(norm(n) for n in names)


def _fmt(names: list[str] | None) -> str:
    return ", ".join(names) if names else "?"


def _remark_text(number: int, names: list[str]) -> str:
    return f"({number}) Objecttype: {', '.join(names)}"


def _fields_of(sheet: RefinedSheet) -> list[_Field]:
    result: list[_Field] = []
    for (section, row_index, column_index), (row, column) in sheet.positions.items():
        cell = sheet.tab.sections[section].rows[row_index][column_index]
        if cell.label and set(cell.label) <= ELLIPSIS_CHARS:
            continue
        result.append(_Field(section, row, column, cell.label, norm(cell.label), cell.footnote, ""))
    result.sort(key=lambda f: (f.row, f.column))
    return result


def _remarks_of(sheet: RefinedSheet) -> dict[int, _Remark]:
    result: dict[int, _Remark] = {}
    for (section, row_index), (row, column) in sheet.margin_positions.items():
        text = sheet.tab.sections[section].margin.get(row_index, "")
        parts: dict[int, list[str]] = {}
        for match in FOOTNOTE_REMARK.finditer(text):
            parts.setdefault(int(match.group(1)), [n.strip() for n in match.group(2).split(",") if n.strip()])
        if parts:
            result[row] = _Remark(_coordinate(row, column), parts)
    return result


class _Context:
    """Spec-gegevens voor één blad. / Spec data for one sheet."""

    def __init__(self, sheet: RefinedSheet, engine: LayoutEngine | None) -> None:
        self.names: list[str] = []
        self.per_type: dict[str, set[str]] = {}
        self.engine = engine
        types: list[ObjectType] = sheet.tab.object_types
        if engine is not None and types:
            self.names = [o.name for o in types if engine._attributes_of(o.name)] or [o.name for o in types]
            self.per_type, _ = engine.attribute_sets(types)

    @property
    def active(self) -> bool:
        return self.engine is not None and bool(self.names)

    def expected(self, key: str) -> _Expected:
        applies = [n for n in self.names if key in self.per_type.get(n, set())]
        if not applies:
            return _Expected(False, None, False)
        return _Expected(len(applies) < len(self.names), applies, True)


def _engine_for(spec: SpecModel | None, engine: LayoutEngine | None) -> LayoutEngine | None:
    if engine is not None:
        return engine
    return LayoutEngine(spec) if spec is not None else None


def _claimed(
    sheet: RefinedSheet, remarks: dict[int, _Remark], item: _Field, fields: list[_Field],
) -> list[str] | None:
    """Objecttypen die de markering van een veld claimt: de opmerking op de rij, anders het blad/de metadata.
    Object types a field's marker claims: the remark on its row, otherwise the sheet / metadata."""
    if item.number is None:
        return None
    remark = remarks.get(item.row)
    if remark and item.number in remark.parts:
        return remark.parts[item.number]
    known = sheet.tab.footnotes.get(item.number)
    if known is None and remark:
        carried = {f.number for f in fields if f.row == item.row}
        loose = [names for n, names in remark.parts.items() if n not in carried]
        if len(loose) == 1:
            return loose[0]  # hernummerd veld, één losse opmerking / renumbered field, one loose remark
    return known


def _object_sections(sheet: RefinedSheet) -> set[int]:
    """Indices van de secties 'Object informatie'; zonder zo'n sectie (oude indeling) tellen alle secties mee.
    Indices of the 'Object informatie' sections; without one (legacy layout) all sections count."""
    found = {i for i, s in enumerate(sheet.tab.sections) if norm(s.title) == norm(SECTION_OBJECT)}
    return found or set(range(len(sheet.tab.sections)))


def _analyse(
    sheet: RefinedSheet, engine: LayoutEngine | None,
) -> tuple[list[AnnotationIssue], list[tuple[_Field, _Expected]]]:
    """Controleer één blad; geeft de bevindingen en per veld de gewenste toestand. / Check one sheet; returns the
    issues and the wanted state per field."""
    context = _Context(sheet, engine)
    fields = _fields_of(sheet)
    remarks = _remarks_of(sheet)
    issues: list[AnnotationIssue] = []

    def add(cell: str, kind: str, severity: str, detail: str) -> None:
        issues.append(AnnotationIssue(sheet.name, cell, kind, severity, detail))

    object_sections = _object_sections(sheet)
    wanted: list[tuple[_Field, _Expected]] = []
    first_set: dict[int, tuple[frozenset[str] | None, str]] = {}
    for item in fields:
        cell = _coordinate(item.row, item.column)
        claimed = _claimed(sheet, remarks, item, fields)
        # Alleen de objectsectie volgt de spec; velden in relatie-/vaste secties houden hun eigen markering.
        # Only the object section follows the spec; fields in relation/fixed sections keep their own marker.
        expected = _Expected(item.number is not None, claimed, False)
        if context.active and item.section in object_sections:
            expected = context.expected(item.key)
            if not expected.known:
                expected = _Expected(item.number is not None, claimed, False)
                add(cell, UNKNOWN_LABEL, "info", f"'{item.label}' staat niet in de spec / is not in the spec")
        wanted.append((item, expected))
        if item.number is None:
            if expected.marked:
                add(cell, MISSING_MARKER, "error", f"'{item.label}' mist een markering voor {_fmt(expected.types)} / "
                    f"needs a marker for {_fmt(expected.types)}")
            continue
        if not expected.marked:
            add(cell, UNEXPECTED_MARKER, "warning", f"({item.number}) bij '{item.label}' hoort er niet / "
                f"marker should not be there")
            continue
        number = item.number
        if expected.known and claimed is not None and _type_key(claimed) != _type_key(expected.types):
            add(cell, WRONG_TYPES, "error", f"({number}) hoort bij {_fmt(claimed)} maar spec zegt "
                f"{_fmt(expected.types)} / ({number}) is for {_fmt(claimed)} but spec says {_fmt(expected.types)}")
        key = _type_key(expected.types)
        if number not in first_set:
            first_set[number] = (key, cell)
        elif key != first_set[number][0] and key is not None and first_set[number][0] is not None:
            add(cell, DUPLICATE_NUMBER, "error", f"({number}) staat ook bij {first_set[number][1]} met andere "
                f"objecttypen / ({number}) is also used at {first_set[number][1]} for other object types")
        remark = remarks.get(item.row)
        if sheet.margin_column is None:
            continue
        if remark is None or number not in remark.parts:
            add(cell, MARGIN_MISSING, "warning", f"opmerking voor ({number}) ontbreekt op rij {item.row} / "
                f"remark for ({number}) is missing on row {item.row}")
        else:
            reference = expected.types if expected.known else sheet.tab.footnotes.get(number)
            wrong = expected.known and claimed is not None and _type_key(claimed) != _type_key(expected.types)
            if reference and not wrong and remark.parts[number] != reference:
                add(remark.cell, MARGIN_MISMATCH, "warning",
                    f"{_remark_text(number, remark.parts[number])} wijkt af van {_remark_text(number, reference)} / "
                    f"differs from the expected text")

    if sheet.margin_column is not None:
        carried: dict[int, set[int]] = {}
        for item in fields:
            if item.number is not None:
                carried.setdefault(item.row, set()).add(item.number)
        for row, remark in remarks.items():
            for number in remark.parts:
                if number not in carried.get(row, set()):
                    add(remark.cell, MARGIN_ORPHAN, "warning",
                        f"opmerking ({number}) staat naast geen veld met ({number}) / "
                        f"remark ({number}) has no field with ({number}) beside it")

    numbers = sorted({i.number for i in fields if i.number is not None})
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        add("", GAP, "warning", f"nummers {numbers} zijn niet aaneengesloten vanaf 1 / "
        f"numbers are not contiguous from 1")
    order: list[int] = []
    for item in fields:
        if item.number is not None and item.number not in order:
            order.append(item.number)
    if order != sorted(order):
        add("", ORDER, "info", f"nummers staan niet oplopend in leesvolgorde: {order} / "
            f"numbers are not increasing in reading order")
    return issues, wanted


def check_annotations(
    path: str | Path, spec: SpecModel | None, engine: LayoutEngine | None = None,
) -> AnnotationReport:
    """Controleer voetnoten en opmerkingen van alle ontwerpbladen. Zonder ``spec`` (en ``engine``) worden alleen
    nummering en opmerkingen onderling gecontroleerd.
    Check footnotes and remarks of all design sheets. Without ``spec`` (and ``engine``) only numbering and
    remark consistency are checked."""
    refined = read_refined(path, spec if spec is not None else (engine.spec if engine else None))
    use_engine = _engine_for(spec, engine)
    report = AnnotationReport(Path(path))
    for sheet in refined.sheets:
        report.sheets_checked.append(sheet.name)
        report.issues.extend(_analyse(sheet, use_engine)[0])
    return report


def _free_path(path: Path) -> Path:
    target = path.with_name(f"{path.stem}_fixed.xlsx")
    number = 2
    while target.exists():
        target = path.with_name(f"{path.stem}_fixed_{number}.xlsx")
        number += 1
    return target


def _rewrite_label(text: str, number: int | None) -> str:
    """Zet het nummer in een celtekst (behoudt sterretjes en de rest). / Set the number in a cell text (keeps stars)."""
    base = MARKER_AT_END.sub("", text, count=1)
    if number is None:
        return base
    match = TRAILING_STARS.match(base)
    assert match is not None
    return f"{match.group(1)} ({number}){match.group(2)}"


def _update_metadata(workbook: Any, footnotes: dict[str, dict[int, list[str]]]) -> None:
    name = find_metadata_sheet(workbook)
    if name is None:
        return
    for row in workbook[name].iter_rows(min_row=2):
        key = row[0].value
        if not isinstance(key, str) or not key.startswith("sheet:") or key[len("sheet:"):] not in footnotes:
            continue
        try:
            info = json.loads(str(row[1].value))
        except ValueError:
            continue
        info["footnotes"] = {str(n): names for n, names in sorted(footnotes[key[len("sheet:"):]].items())}
        row[1].value = json.dumps(info, ensure_ascii=False)


def _header_row(sheet: Worksheet, column: int) -> int:
    for row in range(1, min(sheet.max_row, 60) + 1):
        value = sheet.cell(row=row, column=column).value
        if value is not None and norm(str(value)) == MARGIN_HEADER:
            return row
    return 0


def _fix_sheet(
    ws: Worksheet, sheet: RefinedSheet, engine: LayoutEngine | None, changes: list[str],
) -> dict[int, list[str]]:
    """Hernummer en herschrijf één blad; geeft de nieuwe voetnoot-map. / Renumber and rewrite one sheet; returns the
    new footnote map."""
    wanted = _analyse(sheet, engine)[1]
    remarks = _remarks_of(sheet)
    fields = [item for item, _ in wanted]
    types_of: dict[int, list[str]] = {}
    assigned: list[tuple[_Field, int | None]] = []
    counter = 0
    for item, expected in wanted:
        if not expected.marked:
            assigned.append((item, None))
            continue
        counter += 1  # elk veld met voetnoot een eigen nummer in leesvolgorde / own number per footnoted field
        types = expected.types if expected.types is not None else _claimed(sheet, remarks, item, fields)
        if types:
            types_of[counter] = list(types)
        assigned.append((item, counter))

    by_row: dict[int, list[tuple[int, list[str]]]] = {}
    for item, number in assigned:
        cell = ws.cell(row=item.row, column=item.column)
        if isinstance(cell, MergedCell):
            continue
        old = str(cell.value) if cell.value is not None else ""
        new = _rewrite_label(old, number)
        if new != old:
            cell.value = new
            changes.append(f"Blad {ws.title} {_coordinate(item.row, item.column)}: '{old}' -> '{new}'")
        if number is not None and number in types_of:
            row_items = by_row.setdefault(item.row, [])
            if all(n != number for n, _ in row_items):
                row_items.append((number, types_of[number]))

    margin = sheet.margin_column
    if margin is None:
        return types_of
    for row in range(_header_row(ws, margin) + 1, ws.max_row + 1):
        cell = ws.cell(row=row, column=margin)
        if isinstance(cell, MergedCell):
            continue
        old = str(cell.value) if cell.value is not None else ""
        kept = [p.strip() for p in old.split(";") if p.strip() and not FOOTNOTE_PART.match(p.strip())]
        parts = kept + [_remark_text(n, names) for n, names in by_row.get(row, [])]
        new = "; ".join(parts)
        if new == old.strip():
            continue
        if not old and not cell.alignment.wrap_text:
            cell.alignment = WRAP_TOP
        cell.value = new or None
        changes.append(f"Blad {ws.title} {_coordinate(row, margin)}: '{old}' -> '{new}'")
    return types_of


def _drawing_warnings(source: Path, workbook: Any) -> list[str]:
    """Waarschuw voor afbeeldingen, tekeningen en grafieken: openpyxl behoudt die niet.
    Warn about images, drawings and charts: openpyxl does not preserve them."""
    sheets = [ws.title for ws in workbook.worksheets if getattr(ws, "_images", None) or getattr(ws, "_charts", None)]
    if not sheets:
        try:
            with zipfile.ZipFile(source) as archive:
                has_drawings = any(n.startswith("xl/drawings/") for n in archive.namelist())
        except (OSError, zipfile.BadZipFile):
            has_drawings = False
        sheets = ["?"] if has_drawings else []
    return [
        f"Blad '{name}' bevat afbeeldingen, tekeningen of grafieken; die gaan verloren in het herstelde bestand / "
        f"sheet '{name}' contains images, drawings or charts; they are lost in the fixed file"
        if name != "?" else
        "Het bestand bevat tekeningen of afbeeldingen; die gaan verloren in het herstelde bestand / "
        "the file contains drawings or images; they are lost in the fixed file"
        for name in sheets
    ]


def fix_annotations(
    path: str | Path,
    spec: SpecModel | None,
    engine: LayoutEngine | None = None,
    out_path: str | Path | None = None,
) -> FixResult:
    """Geef elk veld met voetnoot een eigen nummer (1..n in leesvolgorde, zoals de generator), herstel markeringen
    (met ``spec``) en schrijf de opmerkingen naast de juiste rijen. Schrijft ``<naam>_fixed.xlsx`` (nooit over het
    origineel); opmaak blijft ongemoeid. Afbeeldingen/grafieken gaan verloren (zie ``FixResult.warnings``).
    Give each footnoted field its own number (1..n in reading order, like the generator), repair markers (with
    ``spec``) and write the remarks beside the right rows. Writes ``<name>_fixed.xlsx`` (never over the input);
    formatting is left untouched. Images/charts are lost (see ``FixResult.warnings``)."""
    source = Path(path)
    target = Path(out_path) if out_path is not None else _free_path(source)
    if target.resolve() == source.resolve():
        raise ValueError("The output file must differ from the input file.")
    use_engine = _engine_for(spec, engine)
    refined = read_refined(source, spec if spec is not None else (engine.spec if engine else None))
    workbook = load_workbook(source)
    changes: list[str] = []
    warnings = _drawing_warnings(source, workbook)
    metadata: dict[str, dict[int, list[str]]] = {}
    try:
        for sheet in refined.sheets:
            if sheet.name not in workbook.sheetnames:
                continue
            metadata[sheet.meta_key or sheet.name] = _fix_sheet(workbook[sheet.name], sheet, use_engine, changes)
            if sheet.margin_column is None:
                changes.append(f"Blad {sheet.name}: geen 'Opmerkingen'-kolom, opmerkingen niet bijgewerkt / "
                               f"no remarks column, remarks not updated")
        if refined.metadata is not None:
            _update_metadata(workbook, {n: m for n, m in metadata.items() if n in refined.metadata["sheets"]})
        workbook.save(target)
    finally:
        workbook.close()
    return FixResult(target, changes, check_annotations(target, spec, engine), warnings)
