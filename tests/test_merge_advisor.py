from __future__ import annotations

import os

from conftest import make_spec
from openpyxl import load_workbook

from passport_designer.excel_export import export_merge_report
from passport_designer.layout_engine import LayoutEngine
from passport_designer.merge_advisor import (
    apply_merges,
    field_matrix,
    jaccard,
    suggest_merges,
)
from passport_designer.models import SpecModel  # noqa: F401


def test_jaccard():
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3
    assert jaccard(set(), set()) == 0.0


def test_similar_filters_in_same_group_are_suggested():
    spec = make_spec()
    suggestions = suggest_merges(spec, LayoutEngine(spec), threshold=0.6, same_group=True)
    assert [s.members for s in suggestions] == [["Bord", "Informatiebord"]]
    suggestion = suggestions[0]
    assert suggestion.name == "Borden" and suggestion.group == "Borden"
    assert suggestion.object_type_count == 3 and suggestion.passports_saved == 1
    assert suggestion.total_fields == suggestion.common_fields + suggestion.partial_fields
    assert suggestion.partial_fields == 3  # bordcode, APV-verordening, tekst


def test_group_restriction_can_be_switched_off():
    spec = make_spec()
    members = [s.members for s in suggest_merges(spec, LayoutEngine(spec), 0.6, same_group=False)]
    assert len(members) == 1 and set(members[0]) == {"Bord", "Informatiebord", "Paal"}


def test_high_threshold_gives_no_suggestions():
    spec = make_spec()
    assert suggest_merges(spec, LayoutEngine(spec), threshold=1.0) == []


def test_merged_tab_annotates_partial_fields_per_object_type():
    spec = make_spec()
    suggestion = suggest_merges(spec, LayoutEngine(spec))[0]
    tab = suggestion.tab
    assert tab is not None and tab.merged_from == ["Bord", "Informatiebord"]
    matrix = {label: (types, everywhere) for label, types, everywhere in field_matrix(tab)}
    assert matrix["breedte"][1] is True
    assert matrix["APV-verordening"] == (["APV-bord"], False)
    assert sorted(matrix["bordcode"][0]) == ["APV-bord", "Verkeersbord"]
    assert any(note.endswith("Objecttype: APV-bord") for note in tab.notes)


def test_apply_merges_replaces_members_with_one_tab():
    spec = make_spec()
    engine = LayoutEngine(spec)
    suggestion = suggest_merges(spec, engine)[0]
    tabs = apply_merges(spec, engine, engine.build_all(), [(suggestion.name, suggestion.members)])
    assert [t.name for t in tabs] == ["Borden", "Paal", "Verharding"]
    assert len(tabs[0].object_types) == 3
    already_merged = apply_merges(spec, engine, tabs, [("X", ["Bord", "Informatiebord"])])
    assert already_merged == tabs


def test_merge_report_has_summary_and_matrix(tmp_path):
    spec = make_spec()
    suggestions = suggest_merges(spec, LayoutEngine(spec))
    target = export_merge_report(suggestions, tmp_path / "advies.xlsx")
    workbook = load_workbook(target)
    assert workbook.sheetnames == ["Samenvatting", "Borden"]
    assert workbook["Samenvatting"]["A2"].value == "Borden"
    sheet = workbook["Borden"]
    header = [c.value for c in sheet[1]]
    assert header[:2] == ["Veld", "Geldt voor alle"] and "APV-bord" in header
    rows = {r[0].value: [c.value for c in r] for r in sheet.iter_rows(min_row=2)}
    assert rows["breedte"][1] == "Ja"
    assert rows["APV-verordening"][1] == "Nee"
    assert rows["APV-verordening"][2 + header[2:].index("APV-bord")] == "✓"
    assert os.path.getsize(target) > 0
