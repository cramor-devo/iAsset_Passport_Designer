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
