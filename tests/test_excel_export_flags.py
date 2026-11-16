from __future__ import annotations

from openpyxl import load_workbook

from passport_designer.excel_export import MUTED_COLOUR, export_workbook, sheet_layout
from passport_designer.layout_engine import LayoutEngine, LayoutOptions
from passport_designer.models import AttributeFlags, norm
from passport_designer.profiles import LEGACY


def _bord_tab(spec):
    return next(t for t in LayoutEngine(spec, LayoutOptions(profile=LEGACY)).build_all() if t.name == "Bord")


def _nee_for_all_types(spec, attribute: str) -> None:
    for object_type in ("APV-bord", "Verkeersbord"):
        spec.flags.setdefault(object_type, {})[norm(attribute)] = AttributeFlags(include=False)


def test_muted_cells_grey_italic(wave1_spec):
    tab = _bord_tab(wave1_spec)
    layout = sheet_layout(tab, muted={norm("breedte")})
    fields = [c for c in layout.cells if c.value.startswith("breedte")]
    assert fields and all(c.italic and c.colour == MUTED_COLOUR for c in fields)
    others = [c for c in layout.cells if c.value.startswith("hoogte")]
    assert others and not any(c.italic or c.colour for c in others)


def test_export_all_fields_writes_muted_cells_grey_italic(tmp_path, wave1_spec):
    _nee_for_all_types(wave1_spec, "breedte")
    tab = _bord_tab(wave1_spec)
    target = export_workbook([tab], tmp_path / "all.xlsx", spec=wave1_spec, only_included=False)
    sheet = load_workbook(target)[tab.name]
    cells = [c for row in sheet.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("breedte")]
    assert cells and all(c.font.i and c.font.color.rgb.endswith(MUTED_COLOUR) for c in cells)


def test_metadata_only_included(tmp_path, wave1_spec):
    tab = _bord_tab(wave1_spec)
    for only, expected in ((True, "true"), (False, "false")):
        target = export_workbook([tab], tmp_path / f"{expected}.xlsx", spec=wave1_spec, only_included=only)
        meta = load_workbook(target)["_designer"]
        rows = {row[0].value: row[1].value for row in meta.iter_rows(min_row=2)}
        assert rows["only_included"] == expected
