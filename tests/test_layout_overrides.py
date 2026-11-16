"""Tests voor markeren en verwijderen van velden. / Tests for marking and deleting fields."""

from __future__ import annotations

from passport_designer.layout_overrides import (
    TabOverride,
    apply_override,
    deletable_labels,
    delete_fields,
    restore_fields,
    toggle_verify,
)
from passport_designer.models import Cell, PassportTab, Section, SectionStyle, norm


def _tab() -> PassportTab:
    algemeen = Section("Algemeen", SectionStyle.PLAIN, rows=[[Cell("Breedte"), Cell("Hoogte")], [Cell("Kleur")]])
    algemeen.margin[1] = "opmerking"
    leeg = Section("Alleen", SectionStyle.PLAIN, rows=[[Cell("Los")]])
    herhaal = Section("Lijst", SectionStyle.PLAIN, rows=[[Cell("Rij1")]], repeater=True)
    tab = PassportTab("Bord", "", [])
    tab.sections = [algemeen, leeg, herhaal]
    return tab


def test_toggle_verify_twice_returns_to_unmarked():
    marked = toggle_verify(TabOverride(), labels=["Breedte"])
    assert marked.verify == {norm("Breedte")}
    assert toggle_verify(marked, labels=["Breedte"]).verify == frozenset()


def test_delete_then_restore_returns_original_tab():
    override = delete_fields(TabOverride(), labels=["Hoogte"])
    tab, _ = apply_override(_tab(), override)
    assert [c.label for c in tab.sections[0].rows[0]] == ["Breedte"]
    restored, _ = apply_override(_tab(), restore_fields(override, labels=["Hoogte"]))
    assert [c.label for c in restored.sections[0].rows[0]] == ["Breedte", "Hoogte"]


def test_deleting_whole_row_moves_margin_and_drops_empty_section():
    override = delete_fields(TabOverride(), labels=["Breedte", "Hoogte", "Los"])
    tab, _ = apply_override(_tab(), override)
    assert [s.title for s in tab.sections] == ["Algemeen", "Lijst"]
    assert [[c.label for c in r] for r in tab.sections[0].rows] == [["Kleur"]]
    assert tab.sections[0].margin == {0: "opmerking"}


def test_repeater_fields_cannot_be_deleted():
    assert deletable_labels(_tab(), ["Rij1", "Breedte"]) == {norm("Breedte")}
    tab, _ = apply_override(_tab(), TabOverride(deleted=frozenset({norm("Rij1")})))
    assert tab.sections[-1].rows[0][0].label == "Rij1"


def test_apply_override_reports_only_present_marks():
    _, verify = apply_override(_tab(), TabOverride(verify=frozenset({norm("Kleur"), norm("Bestaatniet")})))
    assert verify == {norm("Kleur")}
