from __future__ import annotations

from openpyxl import load_workbook

from passport_designer.excel_export import GREY, PURPLE, export_workbook, sheet_title
from passport_designer.layout_engine import LayoutEngine, LayoutOptions
from passport_designer.profiles import LEGACY


def test_export_creates_one_sheet_per_filter_with_styling(tmp_path, wave1_spec):
    tabs = LayoutEngine(wave1_spec, LayoutOptions(profile=LEGACY)).build_all()
    target = export_workbook(tabs, tmp_path / "out.xlsx")
    workbook = load_workbook(target)
    assert workbook.sheetnames == ["Bord", "Verharding"]
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
