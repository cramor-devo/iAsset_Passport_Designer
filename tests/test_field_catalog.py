"""Tests voor field_catalog en de catalogus-integratie van FieldIdMap. / Tests for field_catalog and FieldIdMap."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from passport_designer.field_catalog import CatalogError, FieldCatalog, FieldInfo, load_catalog, normalise_type
from passport_designer.field_map import FieldIdMap


def entry(cat: FieldCatalog, field_id: int) -> FieldInfo:
    info = cat.get(field_id)
    assert info is not None
    return info


def make_gui_xlsx(path: Path, with_themes: bool = True) -> Path:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Paspoort velden"
    ws.append(["Veld ID", "Label", "Veldtype", "Naam", "Achtervoegsel", "Verplicht"])
    ws.append(["1000", "Soortnaam", "pulldown", "Soortnaam", None, "Ja"])
    ws.append([1002, "Knipfactor", "cijferveld", "Knipfactor", "m", "Nee"])
    ws.append(["1003", "Raar", "verkeersborden", "Raar", None, None])
    if with_themes:
        th = wb.create_sheet("Thema Subthema")
        th.append(["Veld ID", "Thema ID", "Thema", "Subthema ID", "Subthema"])
        th.append(["1000", "2", "Groen", "8024", "Bos"])
        th.append(["1000", "2", "Groen", "8025", "Bosplantsoen"])
        th.append(["1002", "2", "Groen", "8025", "Bosplantsoen"])
    dv = wb.create_sheet("Domeinwaarden")
    dv.append(["Veld ID", "Volgorde", "Value", "Veldnaam", "Score"])
    dv.append(["1000", 1, "Eik", "Soortnaam", None])
    wb.save(path)
    return path


def make_json(path: Path, wrapped: bool = False) -> Path:
    data = [
        {"id": 11, "label": "Herkomst", "type": "select", "values": [{"value": "01", "label": "Planning"}],
         "mandatory": False, "suffix": None, "themes": [{"theme": 0, "subtheme": 8445}]},
        {"id": "12", "label": "Breedte", "type": "numeric", "mandatory": True, "themes": []},
        {"id": 13, "label": "Memo", "type": "weird"},
    ]
    path.write_text(json.dumps({"data": data} if wrapped else data), encoding="utf-8")
    return path


def test_normalise_type():
    assert normalise_type("select") == normalise_type("Pulldown") == "select"
    assert normalise_type("numeric") == normalise_type("cijferveld") == "numeric"
    assert normalise_type("input") == normalise_type("vrij tekstveld") == "text"
    assert normalise_type("verkeersborden") == "unknown"
    assert normalise_type(None) == "unknown"


@pytest.mark.parametrize("wrapped", [False, True])
def test_load_json(tmp_path: Path, wrapped: bool):
    cat = load_catalog(make_json(tmp_path / "d.json", wrapped))
    assert len(cat) == 3 and not cat.has_subtheme_names
    assert entry(cat, 11).values == ["Planning"] and entry(cat, 11).subthemes == frozenset({8445})
    assert entry(cat, 12).kind == "numeric" and entry(cat, 12).mandatory is True
    assert entry(cat, 13).kind == "unknown" and entry(cat, 13).type == "weird"
    assert [i.id for i in cat.by_label("  herkomst ")] == [11]


def test_load_gui_xlsx(tmp_path: Path):
    cat = load_catalog(make_gui_xlsx(tmp_path / "c.xlsx"), include_values=True)
    soort = entry(cat, 1000)
    assert soort.label == "Soortnaam" and soort.kind == "select" and soort.mandatory is True
    assert entry(cat, 1002).suffix == "m" and entry(cat, 1003).kind == "unknown"
    assert entry(cat, 1000).subthemes == frozenset({8024, 8025}) and cat.theme_names == {2: "Groen"}
    assert cat.has_subtheme_names and cat.subthemes_for_name("  BOS ") == {8024}
    assert entry(cat, 1000).values == ["Eik"]
    assert entry(load_catalog(tmp_path / "c.xlsx"), 1000).values == []


def test_load_errors(tmp_path: Path):
    other = tmp_path / "o.xlsx"
    Workbook().save(other)
    with pytest.raises(CatalogError):
        load_catalog(other)
    with pytest.raises(CatalogError):
        load_catalog(tmp_path / "x.txt")
    bad = tmp_path / "b.json"
    bad.write_text("{nope")
    with pytest.raises(CatalogError):
        load_catalog(bad)


def test_field_id_map_gui_xlsx_and_json(tmp_path: Path):
    ids = FieldIdMap.from_file(make_gui_xlsx(tmp_path / "c.xlsx"))
    assert ids.lookup("soortnaam") == 1000 and ids.lookup("KNIPFACTOR") == 1002
    assert ids.catalog is not None and ids.catalog.has_subtheme_names
    ids = FieldIdMap.from_file(make_json(tmp_path / "d.json", wrapped=True))
    assert ids.lookup("Breedte") == 12 and ids.catalog is not None and entry(ids.catalog, 11).kind == "select"


def test_field_id_map_csv_catalog(tmp_path: Path):
    csv_file = tmp_path / "f.csv"
    csv_file.write_text("id;label;type\n5;Hoogte;numeric\n", encoding="utf-8")
    ids = FieldIdMap.from_file(csv_file)
    assert ids.catalog is not None and entry(ids.catalog, 5).kind == "numeric"
    plain = tmp_path / "p.csv"
    plain.write_text("label;id\nHoogte;9\n", encoding="utf-8")
    assert FieldIdMap.from_file(plain).catalog is None


def test_no_network_imports():
    root = Path(__file__).resolve().parents[1] / "passport_designer"
    for name in ("field_catalog.py", "id_check.py"):
        text = (root / name).read_text(encoding="utf-8")
        for banned in ("socket", "urllib", "requests", "http.client"):
            assert banned not in text, f"{name} references {banned}"
