"""Tests voor de kruisverwijzing (diff tussen import en gegenereerd ontwerp). Alles offline.
Tests for the cross-reference (diff between import and generated design). Everything offline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook

from passport_designer.crossref import (
    ADDED,
    MOVED,
    NOT_IN_SPEC,
    REMOVED,
    RENAMED,
    changed_labels,
    diff_tab,
    diff_workbook,
)
from passport_designer.excel_export import export_workbook
from passport_designer.layout_engine import LayoutEngine
from passport_designer.models import Cell, ObjectType, PassportTab, Section
from passport_designer.refined_import import read_refined
from tests.conftest import make_spec


def _tab(sections: dict[str, list[str]]) -> PassportTab:
    tab = PassportTab("T", "", [ObjectType("X", "T")])
    for title, labels in sections.items():
        tab.sections.append(Section(title, rows=[[Cell(label) for label in labels]]))
    return tab


def _kinds(diff) -> dict[str, str]:
    return {e.label: e.kind for e in diff.entries}


def test_identical_tabs_have_empty_diff():
    tab = _tab({"Basis": ["a", "b"], "Object informatie": ["breedte (1)", "hoogte"]})
    assert diff_tab(tab, tab).is_empty


def test_normalisation_ignores_footnote_star_case_and_whitespace():
    generated = _tab({"Object informatie": ["Breedte", "Hoogte  cm"]})
    imported = _tab({"object informatie": ["breedte*", "hoogte cm"]})
    imported.sections[0].rows[0][0] = Cell("breedte", 3)
    assert diff_tab(imported, generated).is_empty


def test_insertion_does_not_flag_following_fields_as_moved():
    generated = _tab({"Object informatie": ["a", "b", "c", "d", "e"]})
    imported = _tab({"Object informatie": ["a", "nieuw", "b", "c", "d", "e"]})
    assert _kinds(diff_tab(imported, generated)) == {"nieuw": ADDED}


def test_removal_does_not_flag_others():
    generated = _tab({"Object informatie": ["alpha", "bravo", "charlie", "delta"]})
    imported = _tab({"Object informatie": ["alpha", "charlie", "delta"]})
    assert _kinds(diff_tab(imported, generated)) == {"bravo": REMOVED}


def test_move_to_other_section_and_swap_within_section():
    generated = _tab({"Basis": ["a", "b"], "Object informatie": ["c", "d", "e", "f"]})
    imported = _tab({"Basis": ["a", "b", "e"], "Object informatie": ["d", "c", "f"]})
    diff = diff_tab(imported, generated)
    kinds = _kinds(diff)
    assert kinds["e"] == MOVED
    moved_entry = next(e for e in diff.entries if e.label == "e")
    assert (moved_entry.from_section, moved_entry.to_section) == ("Object informatie", "Basis")
    assert (kinds.get("c") == MOVED) != (kinds.get("d") == MOVED)  # één van het paar / one of the pair
    assert "f" not in kinds and "a" not in kinds and "b" not in kinds


def test_rename_reported_once_and_unrelated_labels_stay_added_removed():
    generated = _tab({"Object informatie": ["primaire kleur", "dikte"]})
    imported = _tab({"Object informatie": ["primaire kleuren", "zzz"]})
    diff = diff_tab(imported, generated)
    renamed = diff.of_kind(RENAMED)
    assert len(renamed) == 1 and renamed[0].label == "primaire kleuren" and renamed[0].other_label == "primaire kleur"
    assert _kinds(diff) == {"primaire kleuren": RENAMED, "zzz": ADDED, "dikte": REMOVED}


def test_added_and_removed_sections():
    diff = diff_tab(_tab({"Basis": ["a"], "Nieuw": ["x"]}), _tab({"Basis": ["a"], "Oud": ["y"]}))
    assert diff.added_sections == ["Nieuw"] and diff.removed_sections == ["Oud"]
    assert _kinds(diff) == {"x": ADDED, "y": REMOVED}


def test_not_in_spec_only_for_object_information():
    spec = make_spec()
    generated = _tab({"Basis": ["a"], "Object informatie": ["breedte"]})
    generated.object_types = [ObjectType("Verkeersbord", "Bord")]
    imported = _tab({"Basis": ["a", "vrij veld"], "Object informatie": ["breedte", "Bordcode", "onbekend veld"]})
    imported.object_types = generated.object_types
    diff = diff_tab(imported, generated, spec)
    not_in_spec = {e.label for e in diff.of_kind(NOT_IN_SPEC)}
    assert not_in_spec == {"onbekend veld"}
    assert changed_labels(diff)["onbekend veld"] == NOT_IN_SPEC and changed_labels(diff)["vrij veld"] == ADDED


def test_changed_labels_precedence():
    diff = diff_tab(_tab({"Object informatie": ["abcdefghij"]}), _tab({"Object informatie": ["abcdefghijk"]}))
    assert changed_labels(diff) == {"abcdefghij": RENAMED}


@pytest.fixture
def edited(tmp_path, wave1_spec):
    engine = LayoutEngine(wave1_spec)
    tabs = engine.build_all()
    path = export_workbook(tabs, tmp_path / "base.xlsx", spec=wave1_spec)
    return engine, path


def _find(sheet: Any, text: str) -> Any:
    return next(c for row in sheet.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith(text))


def test_excel_edits_are_detected(tmp_path: Path, wave1_spec, edited):
    engine, path = edited
    workbook = load_workbook(path)
    sheet: Any = workbook["Bord"]
    removed = _find(sheet, "hoogte")
    removed.value = None
    _find(sheet, "primaire kleur").value = "primaire kleuren"
    breedte, aanleg = _find(sheet, "breedte"), _find(sheet, "aanlegjaar")
    sheet.cell(row=aanleg.row, column=3, value="spookveld")
    breedte.value, aanleg.value = aanleg.value, breedte.value
    path2 = tmp_path / "edited.xlsx"
    workbook.save(path2)

    refined = read_refined(path2, wave1_spec)
    diffs = dict(diff_workbook(refined, wave1_spec, engine))
    kinds = {(e.label, e.kind) for e in diffs["Bord"].entries}
    assert ("hoogte", REMOVED) in kinds
    assert ("primaire kleuren", RENAMED) in kinds
    assert ("spookveld", ADDED) in kinds and ("spookveld", NOT_IN_SPEC) in kinds
    moved = {label for label, kind in kinds if kind == MOVED}
    assert len(moved) == 1 and moved <= {"breedte", "aanlegjaar"}
    assert {label for label, _ in kinds} <= {"hoogte", "primaire kleuren", "spookveld", "breedte", "aanlegjaar"}
    assert diffs["Verharding"].is_empty
