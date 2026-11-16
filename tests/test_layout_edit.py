"""Tests voor slepen en neerzetten (kern, uitvoer). / Tests for drag and drop (core, output)."""

from __future__ import annotations

import pytest
from openpyxl import load_workbook

from passport_designer.excel_export import export_workbook, sheet_layout
from passport_designer.layout_overrides import (
    CellRef,
    LayoutFileError,
    LayoutRefused,
    TabOverride,
    add_section,
    apply_layout,
    apply_override,
    capture,
    delete_empty_row,
    delete_fields,
    from_json,
    insert_row,
    move_cell,
    rename_section,
    renumber_footnotes,
    reset_layout,
    to_json,
    with_capture,
)
from passport_designer.models import Cell, PassportTab, Section, SectionStyle
from passport_designer.payload import build_tab_payload


def _tab() -> PassportTab:
    algemeen = Section(
        "Algemeen", SectionStyle.PLAIN,
        rows=[[Cell("Breedte"), Cell("Hoogte")], [Cell("Kleur", footnote=2)], [Cell("Dikte", footnote=1)]],
    )
    algemeen.margin[1] = "opmerking"
    extra = Section("Extra", SectionStyle.PLAIN, rows=[[Cell("Los")]])
    lijst = Section("Lijst", SectionStyle.PLAIN, rows=[[Cell("Rij1")]], repeater=True)
    tab = PassportTab("Bord", "", [])
    tab.sections = [algemeen, extra, lijst]
    tab.footnotes = {1: ["A"], 2: ["B"]}
    return tab


def _labels(tab: PassportTab) -> list[list[list[str]]]:
    return [[[c.label for c in row] for row in s.rows] for s in tab.sections]


def _edited(tab: PassportTab, change) -> tuple[PassportTab, TabOverride]:
    override = change(with_capture(TabOverride(), tab))
    return apply_override(tab, override)[0], override


def test_capture_then_apply_is_identity():
    tab = _tab()
    applied, warnings, infos = apply_layout(tab, with_capture(TabOverride(), tab))
    assert _labels(applied) == _labels(tab) and warnings == [] and infos == []


def test_move_within_a_row_inserts_before_target():
    tab, _ = _edited(_tab(), lambda o: move_cell(o, source=CellRef(0, 0, 1), target=CellRef(0, 0, 0), max_columns=5))
    assert _labels(tab)[0][0] == ["Hoogte", "Breedte"]


def test_move_across_rows_removes_emptied_source_row():
    tab, _ = _edited(_tab(), lambda o: move_cell(o, source=CellRef(0, 1, 0), target=CellRef(0, 0, 1), max_columns=5))
    assert _labels(tab)[0] == [["Breedte", "Kleur", "Hoogte"], ["Dikte"]]


def test_move_across_sections_and_margin_stays_with_its_row():
    tab, _ = _edited(_tab(), lambda o: move_cell(o, source=CellRef(0, 0, 0), target=CellRef(1, 0, 1), max_columns=5))
    assert _labels(tab)[1] == [["Los", "Breedte"]]
    assert tab.sections[0].margin == {1: "opmerking"}


def test_drop_on_heading_appends_to_the_section():
    tab, _ = _edited(_tab(), lambda o: move_cell(o, source=CellRef(1, 0, 0), target=CellRef(0, -1, 0), max_columns=5))
    assert _labels(tab)[0][-1] == ["Dikte", "Los"]


def test_full_row_is_refused():
    override = with_capture(TabOverride(), _tab())
    with pytest.raises(LayoutRefused) as info:
        move_cell(override, source=CellRef(0, 1, 0), target=CellRef(0, 0, 0), max_columns=2)
    assert info.value.code == "full"


def test_locked_repeater_section_is_refused_as_source_and_target():
    override = with_capture(TabOverride(), _tab())
    for source, target in ((CellRef(2, 0, 0), CellRef(0, 0, 0)), (CellRef(0, 0, 0), CellRef(2, 0, 0))):
        with pytest.raises(LayoutRefused) as info:
            move_cell(override, source=source, target=target, max_columns=5)
        assert info.value.code == "locked"


def test_insert_and_delete_empty_row():
    tab, override = _edited(_tab(), lambda o: insert_row(o, section=0, row=1))
    assert _labels(tab)[0][1] == []
    assert _labels(apply_override(tab, delete_empty_row(with_capture(override, tab), section=0, row=1))[0])[0] == [
        ["Breedte", "Hoogte"], ["Kleur"], ["Dikte"],
    ]
    with pytest.raises(LayoutRefused):
        delete_empty_row(override, section=0, row=0)


def test_new_section_can_receive_a_field_and_is_hidden_while_empty():
    override = add_section(with_capture(TabOverride(), _tab()), after=0, title="Nieuw", style=SectionStyle.PLAIN)
    assert [s.title for s in apply_override(_tab(), override)[0].sections] == ["Algemeen", "Extra", "Lijst"]
    assert [s.title for s in apply_override(_tab(), override, keep_empty=True)[0].sections][1] == "Nieuw"
    moved = move_cell(override, source=CellRef(0, 0, 1), target=CellRef(1, -1, 0), max_columns=5)
    result = apply_override(_tab(), moved)[0]
    assert (result.sections[1].title, _labels(result)[1], result.sections[1].added) == ("Nieuw", [["Hoogte"]], True)


@pytest.mark.parametrize("title", ["", "   ", "x" * 61])
def test_new_section_title_is_required_and_limited(title):
    with pytest.raises(LayoutRefused) as info:
        add_section(with_capture(TabOverride(), _tab()), after=0, title=title, style=SectionStyle.PLAIN)
    assert info.value.code == "title"


def test_rename_section_and_locked_rename_refused():
    override = with_capture(TabOverride(), _tab())
    assert apply_override(_tab(), rename_section(override, section=1, title="Anders"))[0].sections[1].title == "Anders"
    with pytest.raises(LayoutRefused):
        rename_section(override, section=2, title="Nee")


def test_reset_layout_keeps_marks_and_deletions():
    override = with_capture(TabOverride(verify=frozenset({"los"}), deleted=frozenset({"kleur"})), _tab())
    reset = reset_layout(override)
    assert reset.layout is None and reset.verify == {"los"} and reset.deleted == {"kleur"}


def test_missing_field_is_dropped_with_warning_and_new_field_appended_with_info():
    tab = _tab()
    override = with_capture(TabOverride(), tab)
    changed = _tab()
    changed.sections[0].rows[0] = [Cell("Hoogte"), Cell("Nieuw")]  # Breedte weg, Nieuw erbij
    applied, warnings, infos = apply_layout(changed, override)
    assert warnings == ['Layout: field "breedte" no longer in specification']
    assert "Nieuw" in infos[0] and "Algemeen" in infos[0]
    assert _labels(applied)[0][0] == ["Hoogte"] and _labels(applied)[0][-1][-1] == "Nieuw"


def test_restored_deleted_field_returns_without_info_message():
    tab = _tab()
    deleted = delete_fields(TabOverride(), labels=["Los"])
    override = with_capture(deleted, apply_override(tab, deleted)[0])
    assert "los" in override.known
    applied, _, infos = apply_layout(tab, override)
    assert infos == [] and "Los" in {c.label for s in applied.sections for r in s.rows for c in r}


def test_footnotes_are_renumbered_in_reading_order_and_table_follows():
    tab = _tab()
    moved, _ = _edited(tab, lambda o: move_cell(o, source=CellRef(0, 2, 0), target=CellRef(0, 0, 0), max_columns=5))
    notes = {c.label: c.footnote for r in moved.sections[0].rows for c in r if c.footnote}
    assert notes == {"Dikte": 1, "Kleur": 2}
    assert moved.footnotes == {1: ["A"], 2: ["B"]}
    swapped = renumber_footnotes(tab)
    assert {c.label: c.footnote for r in swapped.sections[0].rows for c in r if c.footnote} == {"Kleur": 1, "Dikte": 2}
    assert swapped.footnotes == {1: ["B"], 2: ["A"]}


def test_json_round_trip_and_corrupt_file():
    override = add_section(with_capture(TabOverride(verify=frozenset({"los"})), _tab()), after=0, title="Nieuw",
                           style=SectionStyle.SEMANTIC)
    assert from_json(to_json({"legacy|Bord": override})) == {"legacy|Bord": override}
    for text in ("{", '{"version": 9, "tabs": {}}', '{"version": 1, "tabs": {"x": {"layout": [{"nope": 1}]}}}'):
        with pytest.raises(LayoutFileError):
            from_json(text)


def test_sheet_layout_maps_cells_and_rows_back_to_the_model():
    layout = sheet_layout(_tab())
    refs = {c.value: c.ref for c in layout.cells if c.ref}
    assert refs["Hoogte"] == CellRef(0, 0, 1) and "Rij1" not in refs  # herhaalbare sectie is vergrendeld
    assert (0, -1) in layout.row_refs.values() and (0, 2) in layout.row_refs.values()


def test_override_changes_excel_cell_order(tmp_path):
    tab = _tab()
    moved, _ = _edited(tab, lambda o: move_cell(o, source=CellRef(0, 0, 1), target=CellRef(0, 0, 0), max_columns=5))
    path = export_workbook([moved], tmp_path / "x.xlsx")
    sheet = load_workbook(path)["Bord"]
    values = [c.value for row in sheet.iter_rows() for c in row if c.value in ("Breedte", "Hoogte")]
    assert values == ["Hoogte", "Breedte"]


def _flat(tab: PassportTab) -> list[tuple[str, list[str]]]:
    fields = build_tab_payload(tab, None).body["fields"]
    assert isinstance(fields, list)
    return [(f["label"], [c["label"] for c in f.get("children", [])]) for f in fields if f.get("children")]


def test_payload_follows_new_order_and_new_section_title():
    tab = _tab()
    override = add_section(with_capture(TabOverride(), tab), after=0, title="Mijn groep", style=SectionStyle.PLAIN)
    override = move_cell(override, source=CellRef(0, 0, 1), target=CellRef(1, -1, 0), max_columns=5)
    flat = _flat(apply_override(tab, override)[0])
    assert ("Mijn groep", ["Hoogte"]) in flat
    assert [t for t, _ in flat].index("Mijn groep") < [t for t, _ in flat].index("Extra")
    assert flat[0] == ("Algemeen", ["Breedte"])


def test_blank_row_is_skipped_in_payload_and_empty_in_sheet():
    tab = _tab()
    effective, _ = _edited(tab, lambda o: insert_row(o, section=0, row=1))
    assert _flat(effective) == _flat(tab)
    assert capture(effective)[0].rows[1].keys == ()
