"""Tests voor relatieblokken en hernoemde standaardblokken (kern, payload, uitvoer). / Tests for relation blocks and
renamed standard blocks (core, payload, output)."""

from __future__ import annotations

import pytest

from passport_designer.excel_export import sheet_layout
from passport_designer.layout_engine import LayoutEngine, LayoutOptions
from passport_designer.layout_overrides import (
    LayoutFileError,
    LayoutRefused,
    TabOverride,
    add_block,
    apply_override,
    delete_block,
    from_json,
    move_block,
    reset_block_edit,
    set_block_edit,
    to_json,
    update_block,
    with_capture,
)
from passport_designer.models import ObjectType, SpecModel
from passport_designer.payload import build_tab_payload
from passport_designer.profiles import ROTTERDAM_V3
from passport_designer.relation_blocks import BlockEdit, RelationBlock

ACTORS = "Actoren en rollen (Sem.Rel)"


def _tab(name: str = "Constructie"):
    spec = SpecModel()
    spec.object_types = [ObjectType("Rioolbuis", name, "Riolering")]
    spec.attributes = {"Rioolbuis": ["diameter"]}
    return next(t for t in LayoutEngine(spec, LayoutOptions(profile=ROTTERDAM_V3)).build_all() if t.name == name)


def _titles(tab) -> list[str]:
    return [s.title for s in tab.sections]


def _titles_set(tab) -> set[str]:
    return set(_titles(tab))


def _block(title: str = "Heeft deel (Sem.Rel)", element: int = 17, **kw) -> RelationBlock:
    return RelationBlock(title, element, **kw)


def _with_block(tab, block=None) -> TabOverride:
    return add_block(TabOverride(), block=block or _block(), existing_titles=_titles_set(tab))


def _body_elements(tab) -> list[tuple[str, int]]:
    return [(f["label"], f["field_id"]) for f in build_tab_payload(tab).body["fields"] if f["field_type"] == 2]


def test_add_block_goes_before_actors_and_is_a_semantic_repeater():
    tab = _tab()
    shown = apply_override(tab, _with_block(tab, _block(columns=("Nummer", "Objecttype"))))[0]
    titles = _titles(shown)
    assert titles.index("Heeft deel (Sem.Rel)") == titles.index(ACTORS) - 1
    section = next(s for s in shown.sections if s.title == "Heeft deel (Sem.Rel)")
    assert section.repeater and section.element == 17
    assert [c.label for c in section.rows[0]] == ["Nummer", "Objecttype"] and section.rows[-1][0].label == "…"


def test_block_belongs_to_the_passport_not_to_a_filter_name():
    other = _tab("Paal")
    assert "Heeft deel (Sem.Rel)" not in _titles(apply_override(other, TabOverride())[0])
    assert "Heeft deel (Sem.Rel)" in _titles(apply_override(other, _with_block(other))[0])


def test_payload_uses_the_chosen_relation_type_without_assumed_warning():
    tab = _tab()
    block = _block("Voert uit (Sem.Rel)", 22)
    shown = apply_override(tab, _with_block(tab, block))[0]
    assert ("Voert uit (Sem.Rel)", 22) in _body_elements(shown)
    payload = build_tab_payload(shown)
    assumed = [i.message for i in payload.issues if i.code == "assumed-relation-type"]
    assert not any("Voert uit" in message for message in assumed)
    assert not any("visibilities" in str(f) for f in payload.body["fields"])  # nooit uitgezonden / never emitted


@pytest.mark.parametrize("element", [17, 20, 23, 24, 27])
def test_every_offered_relation_type_maps_to_its_id(element):
    tab = _tab()
    shown = apply_override(tab, _with_block(tab, _block("Eigen blok", element)))[0]
    assert ("Eigen blok", element) in _body_elements(shown)


def test_invalid_type_and_names_are_refused():
    tab = _tab()
    titles = _titles_set(tab)
    with pytest.raises(LayoutRefused):
        add_block(TabOverride(), block=_block(element=99), existing_titles=titles)
    with pytest.raises(LayoutRefused):
        add_block(TabOverride(), block=_block(title="  "), existing_titles=titles)
    with pytest.raises(LayoutRefused):
        add_block(TabOverride(), block=_block(title="x" * 51), existing_titles=titles)
    with pytest.raises(LayoutRefused):  # dubbel, hoofdletterongevoelig / duplicate, case-insensitive
        add_block(TabOverride(), block=_block(title=ACTORS.upper()), existing_titles=titles)
    with pytest.raises(LayoutRefused):
        add_block(TabOverride(), block=_block(columns=()), existing_titles=titles)


def test_update_and_delete_block():
    tab = _tab()
    override = _with_block(tab)
    changed = update_block(
        override, index=0, block=_block("Bevat (Sem.Rel)", 20, columns=("Code",)), existing_titles=_titles_set(tab),
    )
    shown = apply_override(tab, changed)[0]
    assert "Bevat (Sem.Rel)" in _titles(shown) and "Heeft deel (Sem.Rel)" not in _titles(shown)
    assert delete_block(changed, index=0).blocks == () and delete_block(changed, index=0).is_empty
    with pytest.raises(LayoutRefused):
        delete_block(changed, index=3)


def test_rename_own_block_to_its_own_title_is_allowed():
    tab = _tab()
    override = _with_block(tab)
    titles = _titles_set(apply_override(tab, override)[0])
    update_block(override, index=0, block=_block(repeat=3), existing_titles=titles)


def test_move_block_changes_the_order():
    tab = _tab()
    override = _with_block(tab, _block("A (Sem.Rel)", 17))
    override = add_block(
        override, block=_block("B (Sem.Rel)", 18), existing_titles=_titles_set(apply_override(tab, override)[0]),
    )
    first = _titles(apply_override(tab, move_block(override, index=1, delta=-1))[0])
    assert first.index("B (Sem.Rel)") < first.index("A (Sem.Rel)")
    with pytest.raises(LayoutRefused):
        move_block(override, index=0, delta=-1)


def test_block_keeps_its_place_in_a_captured_layout_and_follows_rename_and_delete():
    tab = _tab()
    override = with_capture(TabOverride(), tab)
    override = add_block(override, block=_block(), existing_titles=_titles_set(tab))
    titles = _titles(apply_override(tab, override)[0])
    assert titles.index("Heeft deel (Sem.Rel)") == titles.index(ACTORS) - 1
    renamed = update_block(
        override,
        index=0,
        block=_block("Eigen naam", 17),
        existing_titles=_titles_set(apply_override(tab, override)[0]),
    )
    titles = _titles(apply_override(tab, renamed)[0])
    assert titles.index("Eigen naam") == titles.index(ACTORS) - 1
    assert "Eigen naam" not in _titles(apply_override(tab, delete_block(renamed, index=0))[0])


def test_rename_standard_block_title_labels_and_samples_keeps_type_id():
    tab = _tab()
    edit = BlockEdit("Betrokkenen", ("Functie", "", "", ""), ("", "", "Jansen", ""))
    override = set_block_edit(TabOverride(), original_title=ACTORS, edit=edit, existing_titles=_titles_set(tab))
    shown = apply_override(tab, override)[0]
    section = next(s for s in shown.sections if s.title == "Betrokkenen")
    assert [c.label for c in section.rows[0]] == ["Functie", "Rol gedetailleerd", "Actor", "Actor Gedetailleerd"]
    assert section.rows[0][2].sample == "Jansen" and section.rows[-1][0].label == "…"
    assert ("Betrokkenen", 11) in _body_elements(shown), "Actoren en rollen keeps element 11 after a rename"


def test_renamed_memo_keeps_memo_type_and_other_blocks_stay():
    tab = _tab()
    override = set_block_edit(
        TabOverride(), original_title="Memo (Sem.Rel)", edit=BlockEdit("Opmerkingen"), existing_titles=_titles_set(tab),
    )
    shown = apply_override(tab, override)[0]
    assert ("Opmerkingen", 19) in _body_elements(shown)
    assert {"Gekoppelde objecten (Sem.Rel)", ACTORS} <= _titles_set(shown)


def test_reset_to_standard_restores_everything():
    tab = _tab()
    override = set_block_edit(
        TabOverride(), original_title=ACTORS, edit=BlockEdit("Anders", ("X",)), existing_titles=_titles_set(tab),
    )
    assert reset_block_edit(override, original_title=ACTORS).is_empty
    assert apply_override(tab, reset_block_edit(override, original_title=ACTORS))[0].sections == tab.sections
    assert set_block_edit(
        override, original_title=ACTORS, edit=BlockEdit(), existing_titles=_titles_set(tab),
    ).is_empty


def test_standard_rename_keeps_place_in_layout_and_rejects_duplicates():
    tab = _tab()
    override = with_capture(TabOverride(), tab)
    renamed = set_block_edit(
        override, original_title=ACTORS, edit=BlockEdit("Anders"), existing_titles=_titles_set(tab)
    )
    shown = _titles(apply_override(tab, renamed)[0])
    assert shown == [("Anders" if t == ACTORS else t) for t in _titles(tab)]
    back = _titles(apply_override(tab, reset_block_edit(renamed, original_title=ACTORS))[0])
    assert back == _titles(tab)
    with pytest.raises(LayoutRefused):
        set_block_edit(
            override, original_title=ACTORS, edit=BlockEdit("memo (sem.rel)"), existing_titles=_titles_set(tab),
        )


def test_sample_data_shows_in_excel_design_from_second_row():
    tab = _tab()
    block = _block(columns=("Nummer", "Naam"), samples=("", "Voorbeeld"), repeat=2)
    shown = apply_override(tab, _with_block(tab, block))[0]
    values = [c.value for c in sheet_layout(shown).cells]
    assert values.count("Voorbeeld") == 1 and "Naam" in values


def test_json_round_trip_keeps_blocks_and_edits():
    tab = _tab()
    override = _with_block(tab, _block(columns=("A", "B"), samples=("", "s"), repeat=3))
    override = set_block_edit(override, original_title=ACTORS, edit=BlockEdit("Anders", ("X",)), existing_titles=set())
    loaded = from_json(to_json({"rotterdam_v3|Constructie": override}))["rotterdam_v3|Constructie"]
    assert loaded == override
    assert apply_override(tab, loaded)[0].sections == apply_override(tab, override)[0].sections


def test_file_with_invalid_relation_type_is_refused():
    bad = '{"version": 1, "tabs": {"k": {"blocks": [{"title": "x", "element": 99, "columns": ["a"]}]}}}'
    with pytest.raises(LayoutFileError):
        from_json(bad)


def test_override_without_blocks_is_unchanged_behaviour():
    tab = _tab()
    assert apply_override(tab, TabOverride())[0] is tab
