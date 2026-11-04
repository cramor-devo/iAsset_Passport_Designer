from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings

from passport_designer.field_map import FieldIdMap, FieldMapError
from passport_designer.layout_engine import LayoutEngine, LayoutOptions
from passport_designer.models import Cell, PassportTab, Section, Severity
from passport_designer.payload import (
    BLANK_LABEL,
    PayloadOptions,
    build_tab_payload,
    flatten,
    section_element,
    to_compact_json,
    to_form_lines,
    to_json,
)
from passport_designer.profiles import LEGACY, ROTTERDAM_V3
from passport_designer.settings import AppSettings


@pytest.fixture
def bord_tab(wave1_spec):
    return next(t for t in LayoutEngine(wave1_spec, LayoutOptions(profile=LEGACY)).build_all() if t.name == "Bord")


def full_map(tab) -> FieldIdMap:
    ids = FieldIdMap()
    number = 100
    for section in tab.sections:
        for row in section.rows:
            for cell in row:
                number += 1
                ids.add(cell.label, number)
    return ids


def test_each_filled_row_is_one_group_with_children(bord_tab):
    result = build_tab_payload(bord_tab, full_map(bord_tab), PayloadOptions(separators=False))
    fields = result.body["fields"]
    first = fields[0]
    assert first["label"] == "Basis" and (first["field_type"], first["field_id"]) == (2, 10)
    assert [c["label"] for c in first["children"]] == ["Beheergroep", "IMBOR Filter", "Objecttype", "naam"]
    assert [c["order"] for c in first["children"]] == [1, 2, 3, 4]
    assert [(c["field_type"], c["field_id"]) for c in first["children"]][3] == (0, 2)
    assert fields[1]["label"] == BLANK_LABEL


def test_body_has_required_api_properties(bord_tab):
    body = build_tab_payload(bord_tab, full_map(bord_tab), PayloadOptions(theme_id=7)).body
    assert {"name", "theme", "fields"} <= body.keys()
    assert body["name"] == "Bord" and body["theme"] == 7
    for group in body["fields"]:
        assert {"label", "field_type", "field_id", "order"} <= group.keys()
        for child in group["children"]:
            assert {"label", "field_type", "field_id", "order"} <= child.keys()


def test_footnote_numbers_never_leak_into_labels(bord_tab):
    result = build_tab_payload(bord_tab, full_map(bord_tab))
    labels = [c["label"] for g in result.body["fields"] for c in g["children"]]
    assert "APV-verordening" in labels
    assert not any("(1)" in label for label in labels)


def test_without_ids_everything_is_unresolved_error(bord_tab):
    result = build_tab_payload(bord_tab)
    system = [c for g in result.body["fields"] for c in g["children"] if c["field_type"] == 0]
    assert result.resolved_count == len(system) and result.unresolved_count > 0
    assert result.has_errors()
    assert all(c["field_id"] is None for g in result.body["fields"] for c in g["children"] if c["field_type"] == 1)


def test_with_ids_resolved_has_no_errors(bord_tab):
    result = build_tab_payload(bord_tab, full_map(bord_tab))
    assert result.unresolved_count == 0 and not result.has_errors()


def test_partial_mapping_gives_warning(bord_tab):
    ids = FieldIdMap()
    ids.add("bordcode", 5)
    result = build_tab_payload(bord_tab, ids)
    assert any(i.code == "unresolved-field-ids" and i.severity is Severity.WARNING for i in result.issues)


def test_long_labels_are_truncated_with_warning(bord_tab):
    bord_tab.sections[1].rows[0][0] = type(bord_tab.sections[1].rows[0][0])("x" * 60)
    result = build_tab_payload(bord_tab, full_map(bord_tab))
    assert any(i.code == "label-too-long" for i in result.issues)
    first_child = next(f for f in result.body["fields"] if f["children"] and f["children"][0]["label"][0] == "x")[
        "children"
    ][0]
    assert len(first_child["label"]) == 50


def test_json_round_trips_and_is_valid(bord_tab):
    body = build_tab_payload(bord_tab, full_map(bord_tab)).body
    assert json.loads(to_json(body)) == body
    compact = to_compact_json(body)
    assert "\n" not in compact and json.loads(compact) == body


def test_form_lines_use_laravel_notation(bord_tab):
    body = build_tab_payload(bord_tab, full_map(bord_tab)).body
    lines = to_form_lines(body).splitlines()
    assert "name=Bord" in lines
    assert "fields[0][label]=Basis" in lines
    assert "fields[0][children][1][label]=IMBOR Filter" in lines
    assert "active=1" in lines
    assert flatten({"a": [{"b": None}]}) == [("a[0][b]", None)]


def test_field_map_from_json_csv_and_errors(tmp_path: Path):
    json_file = tmp_path / "fields.json"
    json_file.write_text(json.dumps({"data": [{"id": 5, "label": "Bordcode"}, {"id": "7", "name": "Breedte"}]}))
    ids = FieldIdMap.from_file(json_file)
    assert ids.lookup("bordcode") == 5 and ids.lookup(" BREEDTE ") == 7

    csv_file = tmp_path / "fields.csv"
    csv_file.write_text("label;id\nHoogte;9\nHoogte;10\n", encoding="utf-8")
    ids = FieldIdMap.from_file(csv_file)
    assert ids.lookup("hoogte") == 9 and ids.is_ambiguous("Hoogte")

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(FieldMapError):
        FieldIdMap.from_file(bad)
    with pytest.raises(FieldMapError):
        FieldIdMap.from_file(tmp_path / "x.txt")


def test_field_map_passport_field_list_csv(tmp_path: Path):
    values = json.dumps([{"value": "1", "label": "a;b, c"}, {"value": "2", "label": "x\ny"}])
    quoted = '"' + values.replace('"', '""') + '"'
    csv_file = tmp_path / "passport field list.csv"
    csv_file.write_text(
        "id;label;name;type;values\n"
        f"600795;bordcode;bordcode_I;select;{quoted}\n"
        "601075;Bordtekst;Bordtekst;input;\n",
        encoding="utf-8",
    )
    ids = FieldIdMap.from_file(csv_file)
    assert len(ids) == 2 and ids.lookup("Bordcode") == 600795 and ids.lookup("bordtekst") == 601075


def _rows(*rows: str) -> list[list[Cell]]:
    return [[Cell(x) for x in row.split("|")] for row in rows]


def _tab_2894() -> PassportTab:
    ell = [Cell("…")] * 4
    sections = [
        Section("Basis", rows=_rows("Nummer|Naam|Objecttype|Thema")),
        Section("Object informatie", rows=_rows("a|b|c|d", "", "e|f|g|h", "i|j (2)")),
        Section("Borden aan drager (Sem.Rel)", rows=_rows("Nummer|Objecttype"), repeater=True),
        Section("Constructielagen (Sem.Rel)", rows=_rows("Laagnummer"), repeater=True),
        Section("Actoren en rollen (Sem.Rel)",
                rows=[*_rows("Rol|Rol gedetailleerd|Actor|Actor Gedetailleerd"), ell], repeater=True),
        Section("Memo (Sem.Rel)", rows=[*_rows("Nummer|Memo veld"), [Cell("…"), Cell("…")]], repeater=True),
        Section("Overige informatie", rows=_rows("iAssetID|conversie-id")),
        Section("Geometrie", rows=_rows("geometrie")),
    ]
    return PassportTab("Drager", "Voorstel", [], sections, profile=ROTTERDAM_V3)


def _ids(*labels: str) -> FieldIdMap:
    ids = FieldIdMap()
    for n, label in enumerate(labels, start=600000):
        ids.add(label, n)
    return ids


def test_payload_matches_real_template_structure():
    tab = _tab_2894()
    labels = ["Objecttype", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "Rol", "Rol gedetailleerd", "Actor",
              "Actor Gedetailleerd", "conversie-id"]
    result = build_tab_payload(tab, _ids(*labels))
    fields = result.body["fields"]
    seq = [(f["field_type"], f["field_id"], f["label"]) for f in fields]
    line = (2, 1, "Horizontale lijn")
    assert seq == [
        (2, 10, "Basis"), line,
        (2, 10, "Object informatie"), (2, 10, BLANK_LABEL), (2, 10, BLANK_LABEL), line,
        (2, 18, "Borden aan drager (Sem.Rel)"), line,
        (2, 23, "Constructielagen (Sem.Rel)"), line,
        (2, 11, "Actoren en rollen (Sem.Rel)"), line,
        (2, 19, "Memo (Sem.Rel)"), line,
        (2, 10, "Overige informatie"), line,
        (2, 4, "Geometrie"), line,
        (2, 16, "iASSET-id"),
    ]  # fmt: skip
    assert [f["order"] for f in fields] == list(range(1, len(fields) + 1))
    assert fields[0]["children"][0] == {
        "label": "Nummer", "field_type": 0, "field_id": 1, "order": 1, "inherit": False,
    }
    assert [(c["field_type"], c["field_id"]) for c in fields[0]["children"]] == [(0, 1), (0, 2), (1, 600000), (0, 3)]
    assert fields[4]["children"][1]["label"] == "j"
    actors = next(f for f in fields if f["field_id"] == 11)
    assert [(c["field_type"], c["field_id"], c["order"]) for c in actors["children"]] == [
        (1, 600011, 1), (1, 600012, 2), (1, 600013, 3), (1, 600014, 4),
    ]
    for f in fields:
        if f["field_id"] not in (10, 11):
            assert f["children"] == []
    overig = next(f for f in fields if f["label"] == "Overige informatie")
    assert [c["label"] for c in overig["children"]] == ["conversie-id"]
    labels_out = [c["label"] for f in fields for c in f["children"]]
    assert not any(label.endswith(")") and label[-3:-2] == "(" for label in labels_out)
    assert result.unresolved_count == 0


def test_separators_can_be_disabled_and_codes_configurable():
    opts = PayloadOptions(separators=False, order_start=0, group_field_id=99)
    fields = build_tab_payload(_tab_2894(), None, opts).body["fields"]
    assert all(f["label"] != "Horizontale lijn" for f in fields)
    assert fields[0]["order"] == 0 and fields[0]["field_id"] == 99


def test_empty_row_and_section_after_iasset_id_removed():
    sections = [Section("Alleen id", rows=_rows("iAsset-ID")), Section("Basis", rows=_rows("Nummer"))]
    fields = build_tab_payload(PassportTab("T", "", [], sections)).body["fields"]
    assert [f["label"] for f in fields] == ["Basis", "Horizontale lijn", "iASSET-id"]


def test_section_element_classification():
    def code(title: str, repeater: bool = False, profile=None) -> int:
        return section_element(Section(title, repeater=repeater), profile)

    assert code("Memo (Sem.Rel)") == 19 and code("Is beschreven door") == 19
    assert code("Actoren en rollen") == 11 and code("Geometrie") == 4
    assert code("Constructielagen (Sem.Rel)", profile=ROTTERDAM_V3) == 23
    assert code("Bestaat uit") == 23 and code("Eindpunt") == 27
    assert code("Onbekend (Sem.Rel)", repeater=True) == 18
    assert code("Locatie informatie") == 10
    issues = build_tab_payload(PassportTab("T", "", [], [Section("Onbekend (Sem.Rel)", repeater=True)])).issues
    assert any(i.code == "assumed-relation-type" for i in issues)


def test_settings_migration_ignores_old_defaults():
    qs = QSettings(str(Path(__file__).parent / "_unused.ini"), QSettings.Format.IniFormat)
    qs.clear()
    for key, value in (("group_field_type", 1), ("field_field_type", 0), ("group_field_id", 0)):
        qs.setValue(f"payload/{key}", value)
    settings = AppSettings(qs)
    opts = settings.payload_options()
    assert (opts.group_field_type, opts.field_field_type, opts.group_field_id) == (2, 1, 10)
    settings.save_payload_options(PayloadOptions(separators=False, line_field_id=5))
    again = settings.payload_options()
    assert again.separators is False and again.line_field_id == 5
    qs.clear()
    (Path(__file__).parent / "_unused.ini").unlink(missing_ok=True)
