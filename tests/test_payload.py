from __future__ import annotations

import json
from pathlib import Path

import pytest

from passport_designer.field_map import FieldIdMap, FieldMapError
from passport_designer.layout_engine import LayoutEngine, LayoutOptions
from passport_designer.models import Severity
from passport_designer.payload import (
    BLANK_LABEL,
    PayloadOptions,
    build_tab_payload,
    flatten,
    to_compact_json,
    to_form_lines,
    to_json,
)
from passport_designer.profiles import LEGACY


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
    result = build_tab_payload(bord_tab, full_map(bord_tab))
    fields = result.body["fields"]
    filled_rows = sum(1 for s in bord_tab.sections for r in s.rows if r)
    assert len(fields) == filled_rows
    first = fields[0]
    assert first["label"] == "Basis"
    assert [c["label"] for c in first["children"]] == ["Beheergroep", "IMBOR Filter", "Objecttype", "naam"]
    assert [c["order"] for c in first["children"]] == [1, 2, 3, 4]
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
    assert result.resolved_count == 0 and result.unresolved_count == result.field_count > 0
    assert result.has_errors()
    assert all(c["field_id"] is None for g in result.body["fields"] for c in g["children"])


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
    first_child = result.body["fields"][2]["children"][0]
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
