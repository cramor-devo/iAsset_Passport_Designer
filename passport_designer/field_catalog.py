"""Veldencatalogus (offline) uit een opgeslagen GET /diverse-fields JSON of de iAsset GUI-catalogus (xlsx).
Field catalog (offline) from a saved GET /diverse-fields JSON or the iAsset GUI field-catalog xlsx.

Er wordt nooit een netwerkverbinding gemaakt. / No network connection is ever made.

Unverified: de koppeling van veldtypen (V2 ``select``/``numeric``/``input`` en GUI ``pulldown``/``cijferveld``/
``vrij tekstveld``) aan een genormaliseerde soort is een aanname; onbekende typen worden ``unknown``, nooit geraden.
Unverified: the mapping of field types (V2 ``select``/``numeric``/``input`` and GUI ``pulldown``/``cijferveld``/
``vrij tekstveld``) to a normalised kind is an assumption; unknown types become ``unknown``, never guessed.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .models import norm

log = logging.getLogger(__name__)

KIND_UNKNOWN = "unknown"

# Unverified assumption / Niet geverifieerde aanname
TYPE_KINDS: dict[str, str] = {
    "select": "select",
    "pulldown": "select",
    "numeric": "numeric",
    "number": "numeric",
    "cijferveld": "numeric",
    "input": "text",
    "text": "text",
    "textarea": "text",
    "vrij tekstveld": "text",
    "date": "date",
    "datum": "date",
    "datetime": "date",
    "datum/tijd": "date",
    "boolean": "boolean",
    "checkbox": "boolean",
}

CATALOG_SHEET = "Paspoort velden"
THEME_SHEET = "Thema Subthema"
VALUES_SHEET = "Domeinwaarden"
_LABEL_KEYS = ("label", "name", "naam", "veldnaam")
_ID_KEYS = ("id", "field_id", "veld id", "veld_id", "veldid")


class CatalogError(Exception):
    """Fout bij het lezen van een catalogus. / Error while reading a catalog."""


def normalise_type(raw: object) -> str:
    """Genormaliseerde soort van een ruw veldtype. / Normalised kind of a raw field type."""
    return TYPE_KINDS.get(norm(str(raw)) if raw is not None else "", KIND_UNKNOWN)


def to_int(value: object) -> int | None:
    """Zet een celwaarde (ook tekst als '1000') om naar int. / Coerce a cell value (also text like '1000') to int."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(float(str(value).strip()))
    except ValueError:
        return None


def _to_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    text = norm(str(value)) if value is not None else ""
    if text in ("ja", "yes", "true", "1"):
        return True
    if text in ("nee", "no", "false", "0"):
        return False
    return None


@dataclass
class FieldInfo:
    """Eén veld in de catalogus. / One field in the catalog."""

    id: int
    label: str
    type: str = ""
    kind: str = KIND_UNKNOWN
    suffix: str = ""
    mandatory: bool | None = None
    subthemes: frozenset[int] = frozenset()
    values: list[str] = field(default_factory=list)


@dataclass
class FieldCatalog:
    """Velden per id, met optionele (sub)thema-namen. / Fields by id, with optional (sub)theme names."""

    entries: dict[int, FieldInfo] = field(default_factory=dict)
    source: str = ""
    subtheme_names: dict[int, str] = field(default_factory=dict)
    theme_names: dict[int, str] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def has_subtheme_names(self) -> bool:
        return bool(self.subtheme_names)

    def get(self, field_id: int) -> FieldInfo | None:
        return self.entries.get(field_id)

    def by_label(self, label: str) -> list[FieldInfo]:
        """Velden met dit label (hoofdletter-/spatie-ongevoelig). / Fields with this label (case/space-insensitive)."""
        key = norm(label)
        return [info for info in self.entries.values() if norm(info.label) == key] if key else []

    def subthemes_for_name(self, name: str) -> set[int]:
        """Subthema-id's met deze naam. / Subtheme IDs with this name."""
        key = norm(name)
        return {sid for sid, sname in self.subtheme_names.items() if norm(sname) == key} if key else set()


def _pick(record: Mapping[str, object], keys: tuple[str, ...]) -> object:
    lowered = {norm(str(k)): v for k, v in record.items()}
    for key in keys:
        if lowered.get(key) not in (None, ""):
            return lowered[key]
    return None


def _json_cell(value: object) -> object:
    """Tekstcel met JSON (CSV-export) uitpakken. / Unpack a text cell holding JSON (CSV export)."""
    if isinstance(value, str) and value.strip()[:1] in ("[", "{"):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def _values_from(raw: object) -> list[str]:
    result: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                text = item.get("label", item.get("value"))
                if text not in (None, ""):
                    result.append(str(text))
            elif item not in (None, ""):
                result.append(str(item))
    return result


def _subthemes_from(raw: object) -> frozenset[int]:
    ids: set[int] = set()
    if isinstance(raw, list):
        for item in raw:
            sid = to_int(item.get("subtheme")) if isinstance(item, dict) else None
            if sid is not None:
                ids.add(sid)
    return frozenset(ids)


def catalog_from_records(records: Iterable[Mapping[str, object]], source: str = "") -> FieldCatalog:
    """Bouw een catalogus uit (JSON/CSV-)records. / Build a catalog from (JSON/CSV) records."""
    catalog = FieldCatalog(source=source)
    for record in records:
        field_id = to_int(_pick(record, _ID_KEYS))
        label = _pick(record, _LABEL_KEYS)
        if field_id is None or not label:
            continue
        raw_type = _pick(record, ("type", "veldtype"))
        suffix = _pick(record, ("suffix", "achtervoegsel"))
        catalog.entries[field_id] = FieldInfo(
            id=field_id,
            label=str(label).strip(),
            type=str(raw_type) if raw_type is not None else "",
            kind=normalise_type(raw_type),
            suffix=str(suffix) if suffix is not None else "",
            mandatory=_to_bool(_pick(record, ("mandatory", "verplicht"))),
            subthemes=_subthemes_from(_json_cell(_pick(record, ("themes",)))),
            values=_values_from(_json_cell(_pick(record, ("values",)))),
        )
    return catalog


def load_json_catalog(path: str | Path) -> FieldCatalog:
    """Laad een opgeslagen /diverse-fields JSON (lijst of {"data": [...]}). / Load a saved /diverse-fields JSON."""
    file_path = Path(path)
    try:
        data = json.loads(file_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise CatalogError(f"Cannot read {file_path.name}: {exc}") from exc
    if isinstance(data, dict):
        data = data.get("data", data.get("fields", []))
    if not isinstance(data, list):
        raise CatalogError(f"{file_path.name}: expected a list of field objects")
    return catalog_from_records((item for item in data if isinstance(item, dict)), file_path.name)


def is_gui_catalog(path: str | Path) -> bool:
    """Is dit de GUI-catalogus (blad 'Paspoort velden' met kolom 'Veld ID')? / Is this the GUI field catalog?"""
    if Path(path).suffix.lower() not in (".xlsx", ".xlsm"):
        return False
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except (OSError, InvalidFileException, BadZipFile, ValueError):
        return False
    try:
        if CATALOG_SHEET not in workbook.sheetnames:
            return False
        header = next(workbook[CATALOG_SHEET].iter_rows(max_row=1, values_only=True), ())
        return "veld id" in {norm(str(c)) for c in header if c is not None}
    finally:
        workbook.close()


def _rows(workbook, sheet: str):  # noqa: ANN001, ANN202
    """Datarijen als dicts per kopnaam (genormaliseerd). / Data rows as dicts keyed by normalised header."""
    rows = workbook[sheet].iter_rows(values_only=True)
    headers = [norm(str(c)) if c is not None else "" for c in next(rows, ())]
    for row in rows:
        yield dict(zip(headers, row, strict=False))


def load_gui_catalog(path: str | Path, include_values: bool = False) -> FieldCatalog:
    """Laad de iAsset GUI-catalogus (xlsx); ``include_values`` leest ook 'Domeinwaarden'.
    Load the iAsset GUI field-catalog xlsx; ``include_values`` also reads 'Domeinwaarden'."""
    file_path = Path(path)
    try:
        workbook = load_workbook(file_path, read_only=True, data_only=True)
    except (OSError, InvalidFileException, BadZipFile, ValueError) as exc:
        raise CatalogError(f"Cannot read {file_path.name}: {exc}") from exc
    catalog = FieldCatalog(source=file_path.name)
    try:
        if CATALOG_SHEET not in workbook.sheetnames:
            raise CatalogError(f"{file_path.name}: sheet '{CATALOG_SHEET}' not found")
        subthemes: dict[int, set[int]] = {}
        for row in _rows(workbook, CATALOG_SHEET):
            field_id = to_int(row.get("veld id"))
            label = row.get("label")
            if field_id is None or label in (None, ""):
                continue
            raw_type = row.get("veldtype")
            suffix = row.get("achtervoegsel")
            catalog.entries[field_id] = FieldInfo(
                id=field_id,
                label=str(label).strip(),
                type=str(raw_type) if raw_type is not None else "",
                kind=normalise_type(raw_type),
                suffix=str(suffix) if suffix is not None else "",
                mandatory=_to_bool(row.get("verplicht")),
            )
        if THEME_SHEET in workbook.sheetnames:
            for row in _rows(workbook, THEME_SHEET):
                field_id, theme_id = to_int(row.get("veld id")), to_int(row.get("thema id"))
                sub_id = to_int(row.get("subthema id"))
                if sub_id is None:
                    continue
                if field_id is not None:
                    subthemes.setdefault(field_id, set()).add(sub_id)
                if row.get("subthema") not in (None, ""):
                    catalog.subtheme_names[sub_id] = str(row["subthema"]).strip()
                if theme_id is not None and row.get("thema") not in (None, ""):
                    catalog.theme_names[theme_id] = str(row["thema"]).strip()
            for field_id, ids in subthemes.items():
                if field_id in catalog.entries:
                    catalog.entries[field_id].subthemes = frozenset(ids)
        if include_values and VALUES_SHEET in workbook.sheetnames:
            for row in _rows(workbook, VALUES_SHEET):
                info = catalog.entries.get(to_int(row.get("veld id")) or -1)
                if info is not None and row.get("value") not in (None, ""):
                    info.values.append(str(row["value"]))
    finally:
        workbook.close()
    if not catalog.entries:
        raise CatalogError(f"{file_path.name}: no fields found")
    log.info("Loaded %d catalog fields from %s", len(catalog.entries), file_path.name)
    return catalog


def load_catalog(path: str | Path, include_values: bool = False) -> FieldCatalog:
    """Laad een catalogus uit .json (V2) of .xlsx (GUI). / Load a catalog from .json (V2) or .xlsx (GUI)."""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".json":
        return load_json_catalog(file_path)
    if suffix in (".xlsx", ".xlsm"):
        if not is_gui_catalog(file_path):
            raise CatalogError(f"{file_path.name}: not an iAsset field catalog (sheet '{CATALOG_SHEET}')")
        return load_gui_catalog(file_path, include_values)
    raise CatalogError(f"Unsupported catalog file type: {suffix or file_path.name}")
