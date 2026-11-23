"""Tests voor objecttypen verplaatsen/verwijderen en extra (blauwe) velden (0.5.6). Alles offline.
Tests for moving/deleting object types and extra (blue) fields (0.5.6). Everything offline."""

from __future__ import annotations

from pathlib import Path

import openpyxl
from conftest import make_spec

from passport_designer.excel_export import EXTRA_COLOUR, VERIFY_COLOUR, export_workbook
from passport_designer.layout_engine import LayoutEngine, LayoutOptions
from passport_designer.layout_overrides import (
    TabOverride,
    extra_in,
    override_from_dict,
    override_to_dict,
    tab_labels,
    toggle_extra,
)
from passport_designer.refined_import import read_metadata, read_refined
from passport_designer.type_edits import apply_type_edits


def _tabs():
    engine = LayoutEngine(make_spec(), LayoutOptions(only_flagged=False))
    return engine, engine.build_all()


def _names(tab):
    return [o.name for o in tab.object_types]


def _tab(tabs, name):
    return next(t for t in tabs if t.name == name)


def test_move_type_rebuilds_both_tabs():
    engine, tabs = _tabs()
    result = apply_type_edits(engine, tabs, {"Asfalt": "Bord"}, [])
    bord = _tab(result, "Bord")
    assert "Asfalt" in _names(bord)
    assert "laagdikte" in {label.lower() for label in tab_labels(bord)}
    assert all("Asfalt" not in _names(t) for t in result if t.name != "Bord")


def test_delete_type_removes_it_and_drops_empty_tab():
    engine, tabs = _tabs()
    result = apply_type_edits(engine, tabs, {}, ["Verkeersbord"])
    assert all("Verkeersbord" not in _names(t) for t in result)
    solo = apply_type_edits(engine, tabs, {}, ["Asfalt"])
    assert "Verharding" not in {t.name for t in solo} or "Asfalt" not in _names(_tab(solo, "Verharding"))


def test_move_to_unknown_tab_is_ignored_and_no_edits_is_identity():
    engine, tabs = _tabs()
    assert apply_type_edits(engine, tabs, {}, []) is tabs
    result = apply_type_edits(engine, tabs, {"Asfalt": "Nope"}, [])
    assert [_names(t) for t in result] == [_names(t) for t in tabs]


def test_extra_toggle_roundtrip_and_is_empty():
    override = toggle_extra(TabOverride(), labels=["a"])
    assert not override.is_empty and override.extra == {"a"}
    assert toggle_extra(override, labels=["a"]).is_empty
    restored = override_from_dict(override_to_dict(override))
    assert restored.extra == override.extra


def test_extra_export_blue_red_wins_and_roundtrips(tmp_path: Path):
    _, tabs = _tabs()
    tab = tabs[0]
    labels = list(tab_labels(tab))
    blue_label, both_label = labels[0], labels[1]
    assert extra_in(tab, toggle_extra(TabOverride(), labels=[blue_label])) == {blue_label}
    path = tmp_path / "e.xlsx"
    export_workbook(
        [tab], path, extra_by_tab={tab.name: {blue_label, both_label}}, verify_by_tab={tab.name: {both_label}},
    )
    sheet = openpyxl.load_workbook(path)[tab.name]
    colours = {
        str(c.value).split(" ")[0]: str(c.font.color.rgb) for row in sheet.iter_rows() for c in row
        if c.value and c.font.color is not None and c.font.color.rgb
    }
    assert any(v.endswith(EXTRA_COLOUR) for v in colours.values())
    assert any(v.endswith(VERIFY_COLOUR) for v in colours.values())
    info = (read_metadata(path) or {})["sheets"][tab.name]
    assert blue_label in info["extra"]
    sheets = read_refined(path).sheets
    assert any(blue_label in s.extra for s in sheets)
