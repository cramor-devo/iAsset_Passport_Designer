from __future__ import annotations

from openpyxl import load_workbook

from passport_designer.excel_export import GREY, PURPLE, export_workbook, sheet_layout, sheet_title
from passport_designer.layout_engine import LayoutEngine, LayoutOptions
from passport_designer.profiles import LEGACY


def test_export_creates_one_sheet_per_filter_with_styling(tmp_path, wave1_spec):
    tabs = LayoutEngine(wave1_spec, LayoutOptions(profile=LEGACY)).build_all()
    target = export_workbook(tabs, tmp_path / "out.xlsx")
    workbook = load_workbook(target)
    assert workbook.sheetnames == ["Bord", "Verharding", "_designer"]
    sheet = workbook["Bord"]
    assert sheet["A1"].value == "Basis" and sheet["A1"].font.b
    assert sheet["A1"].fill.fgColor.rgb.endswith(GREY)
    assert sheet["D1"].fill.fgColor.rgb.endswith(GREY)
    assert sheet["A2"].value == "Beheergroep (Borden)" and sheet["A2"].font.b
    headings = {c.value: c for c in sheet["A"] if c.value in ("Locatie (Sem.rel)", "Notities / Uitzonderingen")}
    assert headings["Locatie (Sem.rel)"].fill.fgColor.rgb.endswith(PURPLE)
    assert headings["Notities / Uitzonderingen"].fill.fgColor.rgb.endswith(GREY)
    assert any(c.value == "(1) Objecttype: APV-bord" for c in sheet["A"])


def test_sheet_titles_are_valid_and_unique():
    used: set[str] = set()
    first = sheet_title("A/B:C*" + "x" * 40, used)
    second = sheet_title("A/B:C*" + "x" * 40, used)
    assert len(first) <= 31 and len(second) <= 31 and first != second
    assert not set("[]:*?/\\") & set(first)


def test_v3_sheet_has_title_object_types_empty_column_and_reference_list(tmp_path, wave1_spec):
    tab = LayoutEngine(wave1_spec).build_all()[0]
    layout = sheet_layout(tab)
    cells = {(c.row, c.column): c for c in layout.cells}
    assert cells[(1, 1)].value == "Bord" and cells[(1, 1)].size == 18
    assert cells[(2, 1)].value == "Objecttypes: APV-bord, Verkeersbord"
    assert cells[(4, 1)].value == "Basis" and cells[(4, 5)].fill == GREY
    assert cells[(4, 7)].value == "Opmerkingen"
    assert not any(c.column == 6 and c.value for c in layout.cells)  # lege kolom / empty column
    assert any(c.column == 7 and c.value.startswith("(1) Objecttype: APV-bord") for c in layout.cells)


def test_export_per_object_type_hides_fields_that_do_not_apply(tmp_path, wave1_spec):
    engine = LayoutEngine(wave1_spec)
    tab = engine.build_all()[0]
    singles = [engine.build_single(tab, o.name) for o in tab.object_types]
    target = export_workbook(singles, tmp_path / "types.xlsx", [o.name for o in tab.object_types])
    workbook = load_workbook(target)
    assert workbook.sheetnames == ["APV-bord", "Verkeersbord", "_designer"]
    values = {str(c.value) for row in workbook["Verkeersbord"].iter_rows() for c in row if c.value}
    assert "Objecttypes: Verkeersbord" in values
    assert not any(v.startswith("APV-verordening") for v in values)
    assert not any(v.startswith("(1) Objecttype") for v in values)
    assert "APV-verordening" in {str(c.value) for row in workbook["APV-bord"].iter_rows() for c in row}


def test_per_object_type_export_with_spec_adds_reference_sheets(tmp_path, wave1_spec):
    engine = LayoutEngine(wave1_spec)
    tab = engine.build_all()[0]
    singles = [engine.build_single(tab, o.name) for o in tab.object_types]
    target = export_workbook(singles, tmp_path / "t.xlsx", [o.name for o in tab.object_types], spec=wave1_spec)
    workbook = load_workbook(target)
    assert workbook.sheetnames == ["APV-bord", "Verkeersbord", "Bron Objecttypen", "Bron Attributen", "_designer"]
    assert workbook["_designer"].sheet_state == "hidden"
