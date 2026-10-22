"""Leest de relatiesecties (Sem.Rel) uit een handmatig bijgewerkt paspoortinrichting-bestand en schrijft ze naar
passport_designer/data/rotterdam_v3_relations.json.
Reads the relation sections (Sem.Rel) from a manually tuned passport design workbook and writes them to
passport_designer/data/rotterdam_v3_relations.json.

Gebruik / Usage:
    python tools/extract_relations.py "Paspoort inrichting ... Wave-1-v3.xlsx"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from passport_designer.compare import ROTTERDAM_V3_SHEETS as SHEET_FILTERS  # noqa: E402

OUTPUT = Path(__file__).resolve().parent.parent / "passport_designer" / "data" / "rotterdam_v3_relations.json"

GENERIC = {
    "basis", "object informatie", "locatie informatie", "beleidsinformatie", "overige informatie", "geometrie",
    "actoren en rollen (sem.rel)", "memo (sem.rel)",
}
MARGIN_COLUMN = 6  # kolom G (0-gebaseerd 6) en verder bevat opmerkingen / column G onwards holds remarks
ELLIPSIS_CHARS = set("&.…")


def is_heading(cell: Any) -> bool:
    return bool(cell.fill.fill_type == "solid" and cell.value)


def is_ellipsis_row(values: list[str]) -> bool:
    return bool(values) and all(v and set(v) <= ELLIPSIS_CHARS for v in values)


def extract_sheet(worksheet: Any) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for row in worksheet.iter_rows():
        first = row[0]
        if is_heading(first):
            title = str(first.value).strip()
            current = None if title.casefold() in GENERIC else {"title": title, "rows": [], "remarks": {}}
            if current is not None:
                sections.append(current)
            continue
        if current is None:
            continue
        grid = [str(c.value).strip() for c in row[:MARGIN_COLUMN] if c.value is not None and str(c.value).strip()]
        margin = " ".join(str(c.value).replace("\n", " ").strip() for c in row[MARGIN_COLUMN:] if c.value is not None)
        if not grid:
            continue
        if is_ellipsis_row(grid):
            current["repeater"] = True
            continue
        current["rows"].append(grid)
        if margin:
            current["remarks"][len(current["rows"]) - 1] = margin
    for section in sections:
        rows = section["rows"]
        if section.get("repeater") and rows:
            section["repeat"] = len(rows)
            section["rows"] = [rows[0]]
            section["remarks"] = {}
    return sections


def main(path: str) -> None:
    workbook = load_workbook(path)
    merged: dict[str, dict[str, Any]] = {}
    for sheet, filters in SHEET_FILTERS.items():
        if sheet not in workbook.sheetnames:
            print(f"skip: no sheet {sheet}")
            continue
        for section in extract_sheet(workbook[sheet]):
            key = json.dumps(section, sort_keys=True, ensure_ascii=False)
            entry = merged.setdefault(key, {**section, "filters": []})
            entry["filters"].extend(f for f in filters if f not in entry["filters"])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    data = {"source": Path(path).name, "sections": list(merged.values())}
    OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(merged)} relation sections -> {OUTPUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
