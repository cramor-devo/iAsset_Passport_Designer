"""Leest IMBOR/objecttype-specificaties uit xlsx-bestanden (Wave 1- en Wave 2-indeling) met openpyxl.
Reads IMBOR/object type specifications from xlsx files (Wave 1 and Wave 2 layouts) with openpyxl."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .models import DEFAULT_FILTER_COLUMNS, ObjectType, SpecModel, norm

log = logging.getLogger(__name__)

HEADER_SCAN_ROWS = 15
FLAG_COLUMNS = ("in paspoort tonen", "opnemen")
ProgressCallback = Callable[[str], None]


class SpecError(Exception):
    """Fout bij het lezen van een specificatiebestand (bericht is bedoeld voor de gebruiker).
    Error while reading a specification file (the message is meant for the user)."""


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _find_sheet(names: list[str], wanted: str) -> str | None:
    for name in names:
        if norm(name) == wanted:
            return name
    return None


def _rows_with_header(
    rows: Iterator[tuple[object, ...]], required: tuple[str, ...], any_of: tuple[str, ...] = (),
) -> tuple[dict[str, int], dict[str, str], list]:
    """Zoek de kopregel (eerste regels van het blad) en geef kolomindex per kopnaam, de oorspronkelijke kopnamen en
    de resterende rijen. ``any_of``: minstens één van deze kolommen moet bestaan.
    Find the header row (first rows of the sheet) and return column index per header, the original header names
    and the remaining rows. ``any_of``: at least one of these columns must exist."""
    for _, row in zip(range(HEADER_SCAN_ROWS), rows, strict=False):
        headers: dict[str, int] = {}
        labels: dict[str, str] = {}
        for index, value in enumerate(row):
            label = _text(value)
            key = norm(label)
            if key and key not in headers:  # dubbele kopnamen (GUID, URI): eerste wint / duplicates: first wins
                headers[key] = index
                labels[key] = label
        if all(name in headers for name in required) and (not any_of or any(n in headers for n in any_of)):
            return headers, labels, list(rows)
    wanted = [*required, " / ".join(any_of)] if any_of else list(required)
    raise SpecError(f"Header row with columns {', '.join(wanted)} not found.")


def read_spec(path: str | Path, progress: ProgressCallback | None = None) -> SpecModel:
    """Lees een specificatiebestand. Verwacht de tabbladen 'Objecttypen' (Objecttype + Filter, Zoekfilter of Fase)
    en 'Attributen' (Objecttype, Attribuut).
    Read a specification file. Expects the sheets 'Objecttypen' (Objecttype + Filter, Zoekfilter or Fase) and
    'Attributen' (Objecttype, Attribuut)."""
    file_path = Path(path)
    try:
        workbook = load_workbook(file_path, read_only=True, data_only=True)
    except (OSError, InvalidFileException, KeyError, BadZipFile) as exc:
        raise SpecError(f"Cannot open {file_path.name}: {exc}") from exc
    try:
        sheet_names = list(workbook.sheetnames)
        types_name = _find_sheet(sheet_names, "objecttypen")
        attrs_name = _find_sheet(sheet_names, "attributen")
        if types_name is None or attrs_name is None:
            raise SpecError(f"{file_path.name}: sheets 'Objecttypen' and 'Attributen' are required.")
        spec = SpecModel(sources=[file_path.name])
        if progress:
            progress(f"{file_path.name}: Objecttypen")
        _read_object_types(workbook[types_name].iter_rows(values_only=True), spec)
        if progress:
            progress(f"{file_path.name}: Attributen")
        _read_attributes(workbook[attrs_name].iter_rows(values_only=True), spec)
    finally:
        workbook.close()
    log.info("Loaded %s: %d types, %d with attributes", file_path.name, len(spec.object_types), len(spec.attributes))
    return spec


def _read_object_types(rows: Iterator[tuple[object, ...]], spec: SpecModel) -> None:
    headers, labels, body = _rows_with_header(rows, ("objecttype",), DEFAULT_FILTER_COLUMNS)
    # Standaard-filterkolom: Filter, anders Zoekfilter, anders Fase (Wave 2); in de UI is elke kolom te kiezen.
    # Default filter column: Filter, else Zoekfilter, else Fase (Wave 2); any column can be chosen in the UI.
    filter_key = next(c for c in DEFAULT_FILTER_COLUMNS if c in headers)
    columns = [key for key in headers if key != "objecttype"]
    spec.columns = [labels[key] for key in columns]

    def get(row: tuple[object, ...], name: str) -> str:
        index = headers.get(name)
        return _text(row[index]) if index is not None and index < len(row) else ""

    seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    for row in body:
        name = get(row, "objecttype")
        values = tuple((key, value) for key in columns if (value := get(row, key)))
        if not name or not values or (name, values) in seen:
            continue
        seen.add((name, values))
        # Wave 1 heeft 'Groep'; Wave 2 niet, daar vervangt 'Fase' (bijv. Put, Stuw) de beheergroep.
        # Wave 1 has 'Groep'; Wave 2 does not, there 'Fase' (e.g. Put, Stuw) stands in for the management group.
        group = get(row, "groep") if "groep" in headers else get(row, "fase")
        spec.object_types.append(
            ObjectType(
                name, get(row, filter_key), group, get(row, "fase"), get(row, "geometrietype"), values,
            ),
        )


def _read_attributes(rows: Iterator[tuple[object, ...]], spec: SpecModel) -> None:
    headers, _, body = _rows_with_header(rows, ("objecttype", "attribuut"))
    flag_index = next((headers[c] for c in FLAG_COLUMNS if c in headers), None)
    type_index, attr_index = headers["objecttype"], headers["attribuut"]
    seen: dict[str, set[str]] = {}
    for row in body:
        if max(type_index, attr_index) >= len(row):
            continue
        type_name, attribute = _text(row[type_index]), _text(row[attr_index])
        if not type_name or not attribute:
            continue
        key = norm(attribute)
        if key not in seen.setdefault(type_name, set()):
            seen[type_name].add(key)
            spec.attributes.setdefault(type_name, []).append(attribute)
        if flag_index is not None and flag_index < len(row) and norm(_text(row[flag_index])) == "nee":
            spec.excluded.setdefault(type_name, set()).add(key)
