from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from passport_designer.models import AttributeFlags
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


def _attrs_file(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    workbook = Workbook()
    types = workbook.active
    assert types is not None
    types.title = "Objecttypen"
    types.append(["Objecttype", "Filter"])
    types.append(["Aansluitput", "Putten"])
    attrs = workbook.create_sheet("Attributen")
    attrs.append(["Titel"])  # rij 1 is een titel; de kopregel staat op rij 2 / row 2 holds the header
    attrs.append(header)
    for row in rows:
        attrs.append(row)
    workbook.save(path)
    return path


def test_reads_opnemen_and_minimal_dataset(tmp_path: Path):
    path = _attrs_file(
        tmp_path / "flags.xlsx",
        ["Objecttype", "Attribuut", "Opnemen", "MinimaleDataset"],
        [["Aansluitput", "diameter", "Ja", "Ja"], ["Aansluitput", "geheim", "Nee", "Nee"],
         ["Aansluitput", "kleur", "Ja", "Nee"]],
    )
    spec = read_spec(path)
    assert spec.flag(object_type="Aansluitput", attribute="diameter") == AttributeFlags(True, True)
    assert spec.flag(object_type="Aansluitput", attribute="geheim") == AttributeFlags(False, False)
    assert spec.flag(object_type="Aansluitput", attribute="kleur") == AttributeFlags(True, False)
    assert spec.excluded["Aansluitput"] == {"geheim"}
    assert spec.has_minimal_flags is True


@pytest.mark.parametrize("header", ["Minimale dataset", "MINIMALEDATASET"])
def test_minimal_dataset_header_variants(tmp_path: Path, header: str):
    path = _attrs_file(tmp_path / "mds.xlsx", ["Objecttype", "Attribuut", header], [["Aansluitput", "diameter", "Ja"]])
    spec = read_spec(path)
    assert spec.flag(object_type="Aansluitput", attribute="diameter").minimal is True


def test_missing_mds_column_gives_none(tmp_path: Path):
    path = _attrs_file(
        tmp_path / "old.xlsx", ["Objecttype", "Attribuut", "Opnemen"], [["Aansluitput", "geheim", "Nee"]],
    )
    spec = read_spec(path)
    assert spec.flag(object_type="Aansluitput", attribute="geheim") == AttributeFlags(False, None)
    assert spec.has_minimal_flags is False


def test_duplicate_rows_with_trailing_space_keep_flags(tmp_path: Path):
    path = _attrs_file(
        tmp_path / "dup.xlsx",
        ["Objecttype", "Attribuut", "Opnemen", "MinimaleDataset"],
        [["Aansluitput", "diameter ", "Ja", "Ja"], ["Aansluitput", "diameter", "Ja", "Ja"]],
    )
    spec = read_spec(path)
    assert spec.flag(object_type="Aansluitput", attribute="Diameter") == AttributeFlags(True, True)
    assert spec.attributes["Aansluitput"] == ["diameter"]
    assert spec.excluded.get("Aansluitput", set()) == set()


def test_merge_flags_later_wins_and_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    first = read_spec(_attrs_file(tmp_path / "a.xlsx", ["Objecttype", "Attribuut", "Opnemen"],
                                  [["Aansluitput", "geheim", "Nee"]]))
    second = read_spec(_attrs_file(tmp_path / "b.xlsx", ["Objecttype", "Attribuut", "Opnemen"],
                                   [["Aansluitput", "geheim", "Ja"]]))
    first.merge(second)
    assert first.flag(object_type="Aansluitput", attribute="geheim") == AttributeFlags(True, None)
    assert "geheim" not in first.excluded["Aansluitput"]
    assert "Conflicting flags" in caplog.text
    assert "b.xlsx" in caplog.text
