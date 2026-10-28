"""Koppelt veldnamen aan iAsset veld-id's, ingelezen uit een export van GET /fields of /diverse-fields.
Maps field labels to iAsset field IDs, loaded from an export of GET /fields or /diverse-fields."""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .models import norm

log = logging.getLogger(__name__)

LABEL_KEYS = ("label", "name", "naam", "veldnaam", "attribuut", "field")
ID_KEYS = ("field_id", "id", "veld_id", "veldid")


class FieldMapError(Exception):
    """Fout bij het lezen van een veld-id-bestand. / Error while reading a field ID file."""


class FieldIdMap:
    """Zoekt het iAsset veld-id bij een veldnaam (hoofdletterongevoelig). / Finds the iAsset field ID for a label."""

    def __init__(self) -> None:
        self._ids: dict[str, int] = {}
        self.ambiguous: set[str] = set()
        self.source = ""

    def __len__(self) -> int:
        return len(self._ids)

    def add(self, label: str, field_id: int) -> None:
        key = norm(label)
        if not key:
            return
        if key in self._ids and self._ids[key] != field_id:
            self.ambiguous.add(key)
            return
        self._ids[key] = field_id

    def lookup(self, label: str) -> int | None:
        return self._ids.get(norm(label))

    def is_ambiguous(self, label: str) -> bool:
        return norm(label) in self.ambiguous

    @classmethod
    def from_file(cls, path: str | Path) -> FieldIdMap:
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        try:
            if suffix == ".json":
                records = _records_from_json(file_path)
            elif suffix == ".csv":
                records = _records_from_csv(file_path)
            elif suffix in (".xlsx", ".xlsm"):
                records = _records_from_xlsx(file_path)
            else:
                raise FieldMapError(f"Unsupported file type: {suffix or file_path.name}")
        except (OSError, ValueError, InvalidFileException, KeyError, BadZipFile) as exc:
            raise FieldMapError(f"Cannot read {file_path.name}: {exc}") from exc
        mapping = cls()
        mapping.source = file_path.name
        for record in records:
            label = _pick(record, LABEL_KEYS)
            raw_id = _pick(record, ID_KEYS)
            try:
                field_id = int(float(str(raw_id)))
            except (TypeError, ValueError):
                continue
            if label:
                mapping.add(str(label), field_id)
        if not len(mapping):
            raise FieldMapError(f"{file_path.name}: no (label, id) pairs found.")
        log.info("Loaded %d field IDs from %s", len(mapping), file_path.name)
        return mapping


def _pick(record: dict[str, object], keys: tuple[str, ...]) -> object:
    lowered = {norm(str(k)): v for k, v in record.items()}
    for key in keys:
        if key in lowered and lowered[key] not in (None, ""):
            return lowered[key]
    return None


def _records_from_json(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("data", data.get("fields", []))
    if not isinstance(data, list):
        raise ValueError("expected a list of field objects")
    return [item for item in data if isinstance(item, dict)]


def _records_from_csv(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8-sig")
    # Scheidingsteken uit de koptekst: de "values"-kolom bevat zelf ';' en komma's, en regeleinden tussen quotes.
    # Delimiter from the header line only: the "values" column itself contains ';' and commas, and quoted newlines.
    header = text.split("\n", 1)[0]
    delimiter = max(",;\t", key=header.count)
    # Passport diverse-fields exports hold huge JSON cells in "values" / Exports hebben enorme JSON-cellen
    csv.field_size_limit(2**30)
    return [dict(row) for row in csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)]


def _records_from_xlsx(path: Path) -> list[dict[str, object]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        for sheet in workbook.worksheets:
            rows = sheet.iter_rows(values_only=True)
            for index, row in enumerate(rows):
                headers = [str(c) if c is not None else "" for c in row]
                lowered = {norm(h) for h in headers}
                if index < 15 and lowered & set(LABEL_KEYS) and lowered & set(ID_KEYS):
                    return [dict(zip(headers, r, strict=False)) for r in rows]
    finally:
        workbook.close()
    return []
