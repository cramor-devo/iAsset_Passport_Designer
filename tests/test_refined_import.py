"""Tests voor de bronbladen, metadata en het terugdraaien (import) van ontwerpen. Alles offline.
Tests for reference sheets, metadata and the round trip (import) of designs. Everything offline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from passport_designer.crossref import diff_workbook, label_key
from passport_designer.excel_export import export_workbook
from passport_designer.layout_engine import LayoutEngine, LayoutOptions
from passport_designer.merge_advisor import merged_tab
from passport_designer.models import SpecModel
from passport_designer.profiles import LEGACY
from passport_designer.refined_import import read_metadata, read_refined, split_label
from passport_designer.spec_reader import read_spec


@pytest.fixture
def exported(tmp_path, wave1_spec) -> Path:
    tabs = LayoutEngine(wave1_spec).build_all()
    return export_workbook(tabs, tmp_path / "out.xlsx", spec=wave1_spec)


def test_reference_sheets_are_raw_and_filtered(exported):
    workbook = load_workbook(exported)
    assert workbook.sheetnames == ["Bord", "Verharding", "Bron Objecttypen", "Bron Attributen", "_designer"]
    types = workbook["Bron Objecttypen"]
    assert str(types["A1"].value).startswith("Bron: wave1.xlsx | Exportdatum: 20")
    header = [c.value for c in types[3]]
    assert header[:2] == ["Objecttype", "GUID"] and header[-2:] == ["Geometrietype", "Definitie"]
    assert [r[0].value for r in types.iter_rows(min_row=4)] == ["APV-bord", "Verkeersbord", "Asfaltverharding"]
    attrs = workbook["Bron Attributen"]
    assert [c.value for c in attrs[3]][-1] == "Toelichting"
    rows = [[c.value for c in r] for r in attrs.iter_rows(min_row=4)]
    assert ["APV-bord", "g", "geheim", "g", "Nee", "uitleg geheim"] in rows
    assert {str(r[0]) for r in rows} <= {"APV-bord", "Verkeersbord", "Asfaltverharding"}


def test_reference_sheets_are_filtered_to_exported_object_types(tmp_path, wave1_spec):
    engine = LayoutEngine(wave1_spec)
    tab = engine.build_all()[0]
    single = engine.build_single(tab, "Verkeersbord")
    target = export_workbook([single], tmp_path / "one.xlsx", spec=wave1_spec)
    workbook = load_workbook(target)
    types = {str(r[0].value) for r in workbook["Bron Objecttypen"].iter_rows(min_row=4)}
    attrs = {str(r[0].value) for r in workbook["Bron Attributen"].iter_rows(min_row=4)}
    assert types == attrs == {"Verkeersbord"}


def test_merged_specs_get_bron_column_and_header_union(tmp_path, wave1_file, wave2_file):
    spec = read_spec(wave1_file)
    spec.merge(read_spec(wave2_file))
    spec.merge(read_spec(wave2_file))
    assert len(spec.raw_sheets["objecttypen"]) == 2
    tab = LayoutEngine(spec).build_all()[0]
    other = next(t for t in LayoutEngine(spec).build_all() if t.name == "RD-Obsurv")
    target = export_workbook([tab, other], tmp_path / "m.xlsx", spec=spec)
    sheet = load_workbook(target)["Bron Objecttypen"]
    assert "wave1.xlsx" in str(sheet["A1"].value) and "wave2.xlsx" in str(sheet["A1"].value)
    header = [c.value for c in sheet[3]]
    assert header[0] == "Bron" and "Organisatie" in header and "Definitie" in header
    sources = {str(r[0].value) for r in sheet.iter_rows(min_row=4)}
    assert sources == {"wave1.xlsx", "wave2.xlsx"}


def test_spec_without_raw_data_skips_reference_sheets(tmp_path):
    from tests.conftest import make_spec

    spec = make_spec()
    tabs = LayoutEngine(spec).build_all()
    target = export_workbook(tabs, tmp_path / "x.xlsx", spec=spec)
    assert load_workbook(target).sheetnames[-1] == "_designer"
    assert not any(n.startswith("Bron") for n in load_workbook(target).sheetnames)


def test_metadata_sheet_is_hidden_and_complete(exported):
    sheet = load_workbook(exported)["_designer"]
    assert sheet.sheet_state == "hidden"
    meta = read_metadata(exported)
    assert meta is not None
    assert meta["app_version"] and meta["profile"] == "rotterdam_v3" and meta["sources"] == ["wave1.xlsx"]
    info = meta["sheets"]["Bord"]
    assert info["object_types"] == ["APV-bord", "Verkeersbord"] and info["tab"] == "Bord"
    assert info["footnotes"] == {1: ["APV-bord"]}
    raw = next(str(r[1]) for r in sheet.iter_rows(values_only=True) if r[0] == "sheet:Bord")
    assert json.loads(raw)["merged_from"] == []


def test_split_label():
    assert split_label("breedte (3)") == ("breedte", 3)
    assert split_label("  breedte*  ") == ("breedte", None)
    assert split_label("breedte (3)*") == ("breedte", 3)
    assert split_label("Beheergroep (Borden)") == ("Beheergroep (Borden)", None)


def _assert_round_trip(path: Path, spec: SpecModel, engine: LayoutEngine, tabs) -> None:
    refined = read_refined(path, spec)
    assert [s.name for s in refined.sheets] == [t.name for t in tabs]
    for sheet, tab in zip(refined.sheets, tabs, strict=True):
        assert sheet.tab.footnotes == tab.footnotes
        assert [o.name for o in sheet.tab.object_types] == [o.name for o in tab.object_types]
        assert [s.title for s in sheet.tab.sections] == [s.title for s in tab.sections]
        assert [[label_key(c.display) for c in r] for s in sheet.tab.sections for r in s.rows] == [
            [label_key(c.display) for c in r] for s in tab.sections for r in s.rows
        ]
    assert not refined.warnings
    for name, diff in diff_workbook(refined, spec, engine):
        assert diff.is_empty, (name, diff)


def test_round_trip_with_metadata(exported, wave1_spec):
    tabs = LayoutEngine(wave1_spec).build_all()
    _assert_round_trip(exported, wave1_spec, LayoutEngine(wave1_spec), tabs)
    refined = read_refined(exported, wave1_spec)
    assert refined.metadata is not None and len(refined.sheets[0].column_widths) == 5
    assert refined.sheets[0].column_widths[0] == 30 and refined.sheets[0].margin_width == 70
    first = refined.sheets[0]
    assert first.positions[(0, 0, 0)] == (5, 1) and first.heading_rows[0] == 4


def test_round_trip_without_metadata(tmp_path, exported, wave1_spec):
    workbook = load_workbook(exported)
    del workbook["_designer"]
    path = tmp_path / "nometa.xlsx"
    workbook.save(path)
    tabs = LayoutEngine(wave1_spec).build_all()
    refined = read_refined(path, wave1_spec)
    assert refined.metadata is None
    _assert_round_trip(path, wave1_spec, LayoutEngine(wave1_spec), tabs)


def test_round_trip_legacy_profile(tmp_path, wave1_spec):
    engine = LayoutEngine(wave1_spec, LayoutOptions(profile=LEGACY))
    tabs = engine.build_all()
    path = export_workbook(tabs, tmp_path / "legacy.xlsx", spec=wave1_spec)
    _assert_round_trip(path, wave1_spec, engine, tabs)
    workbook = load_workbook(path)
    del workbook["_designer"]
    workbook.save(tmp_path / "legacy2.xlsx")
    refined = read_refined(tmp_path / "legacy2.xlsx", wave1_spec)
    assert refined.sheets[0].tab.footnotes == tabs[0].footnotes
    assert refined.sheets[0].tab.profile is LEGACY


def test_round_trip_merged_tab_uses_metadata(tmp_path, wave1_spec):
    engine = LayoutEngine(wave1_spec)
    tab = merged_tab(wave1_spec, engine, ["Bord", "Verharding"], "Combi")
    path = export_workbook([tab], tmp_path / "merged.xlsx", spec=wave1_spec)
    refined = read_refined(path, wave1_spec)
    assert refined.sheets[0].tab.merged_from == ["Bord", "Verharding"]
    _assert_round_trip(path, wave1_spec, engine, [tab])


def test_unknown_object_type_and_foreign_sheets_warn(tmp_path, exported, wave1_spec):
    workbook = load_workbook(exported)
    workbook["Bord"]["A2"] = "Objecttypes: APV-bord, Spook"
    other = workbook.create_sheet("Notities")
    other["A1"] = "gewoon een blad"
    path = tmp_path / "w.xlsx"
    workbook.save(path)
    refined = read_refined(path, wave1_spec)
    assert any("'Spook'" in w for w in refined.sheets[0].warnings)
    assert [o.name for o in refined.sheets[0].tab.object_types] == ["APV-bord", "Spook"]
    assert any("Notities" in w for w in refined.warnings)
    assert "Bron Objecttypen" not in [s.name for s in refined.sheets]


def test_sheet_without_margin_column_and_odd_rows(tmp_path, exported, wave1_spec):
    workbook = load_workbook(exported)
    sheet = workbook["Bord"]
    for row in sheet.iter_rows(min_col=7, max_col=7):
        row[0].value = None
    sheet["B5"] = None  # rij met minder cellen / row with fewer cells
    sheet["A100"] = "extra*"  # extra veld onderaan de laatste sectie / extra field at the end of the last section
    path = tmp_path / "odd.xlsx"
    workbook.save(path)
    refined = read_refined(path, wave1_spec)
    bord = refined.sheets[0]
    assert bord.margin_column is None and any("Opmerkingen" in w for w in bord.warnings)
    assert [c.label for c in bord.tab.sections[0].rows[0]] == ["Nummer", "IMBOR Filter", "Thema", "Subthema"]
    assert bord.tab.sections[-1].rows[-1][0].label == "extra"
