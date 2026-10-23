from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from passport_designer.spec_reader import SpecError, read_spec


def test_wave1_object_types_and_groups(wave1_spec):
    filters = wave1_spec.filters()
    assert list(filters) == ["Bord", "Verharding"]
    assert [o.name for o in filters["Bord"]] == ["APV-bord", "Verkeersbord"]
    assert filters["Bord"][0].group == "Borden"


def test_wave1_attributes_and_excluded_flags(wave1_spec):
    assert "bordcode" in wave1_spec.attributes["APV-bord"]
    assert "geheim" in wave1_spec.excluded["APV-bord"]


def test_wave2_uses_fase_as_group_and_opnemen_flag(wave2_file):
    spec = read_spec(wave2_file)
    assert [o.group for o in spec.object_types] == ["Put", "Stuw"]
    assert "diameter" in spec.excluded["Aansluitput"]


def test_merge_combines_without_duplicates(wave1_spec, wave2_file):
    before = len(wave1_spec.object_types)
    wave1_spec.merge(read_spec(wave2_file))
    wave1_spec.merge(read_spec(wave2_file))
    assert len(wave1_spec.object_types) == before + 2
    assert wave1_spec.attributes["Aansluitput"].count("aanleghoogte") == 1


def test_missing_sheets_raise_friendly_error(tmp_path: Path):
    path = tmp_path / "wrong.xlsx"
    workbook = Workbook()
    workbook.save(path)
    with pytest.raises(SpecError):
        read_spec(path)


def test_not_an_excel_file_raises_spec_error(tmp_path: Path):
    path = tmp_path / "broken.xlsx"
    path.write_text("not a zip", encoding="utf-8")
    with pytest.raises(SpecError):
        read_spec(path)


def test_objecttypen_columns_are_kept_and_filter_column_is_selectable(wave2_file):
    spec = read_spec(wave2_file)
    assert spec.columns == ["Organisatie", "Filter", "Systeem", "Fase", "Geometrietype"]
    assert list(spec.filters()) == ["RD-Obsurv", "RD-Ultimo"]
    spec.filter_column = spec.resolve_filter_column("fase")
    assert spec.filter_column == "Fase"
    assert {name: [o.name for o in types] for name, types in spec.filters().items()} == {
        "Put": ["Aansluitput"], "Stuw": ["Aflaatstuw"],
    }
    assert spec.resolve_filter_column("does not exist") == "Filter"


def _types_sheet(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    workbook = Workbook()
    types = workbook.active
    assert types is not None
    types.title = "Objecttypen"
    types.append(header)
    for row in rows:
        types.append(row)
    attrs = workbook.create_sheet("Attributen")
    attrs.append(["Objecttype", "Attribuut"])
    attrs.append(["Aansluitput", "diameter"])
    workbook.save(path)
    return path


def test_fase_is_the_filter_when_there_is_no_filter_column(tmp_path: Path):
    path = _types_sheet(
        tmp_path / "wave2.xlsx",
        ["Organisatie", "Objecttype", "Systeem", "Fase"],
        [
            ["R", "Aansluitput", "Wave 2", "Put"],
            ["R", "Inspectieput", "Wave 2", "Put"],
            ["R", "Stuw", "Wave 2", "Stuw"],
        ],
    )
    spec = read_spec(path)
    assert spec.resolve_filter_column() == "Fase"
    assert {name: [o.name for o in types] for name, types in spec.filters().items()} == {
        "Put": ["Aansluitput", "Inspectieput"], "Stuw": ["Stuw"],
    }


def test_zoekfilter_column_is_recognised(tmp_path: Path):
    path = _types_sheet(tmp_path / "old.xlsx", ["Objecttype", "Zoekfilter"], [["Aansluitput", "Putten"]])
    spec = read_spec(path)
    assert spec.resolve_filter_column() == "Zoekfilter"
    assert list(spec.filters()) == ["Putten"]


def test_objecttypen_without_any_filter_column_raise_spec_error(tmp_path: Path):
    path = _types_sheet(tmp_path / "bad.xlsx", ["Objecttype", "Systeem"], [["Aansluitput", "Wave 2"]])
    with pytest.raises(SpecError):
        read_spec(path)
