"""Tests voor de bulk-export (kern). / Tests for the bulk export (core)."""

from __future__ import annotations

import pytest

from passport_designer.bulk_export import existing, plan_jobs, safe_filename


def _names(jobs) -> list[str]:
    return [j.path.name for j in jobs]


def test_passport_only_is_named_after_the_tab(tmp_path):
    jobs = plan_jobs(selection={"Dragers": {None}}, tab_folder=tmp_path, type_folder=None)
    assert _names(jobs) == ["Dragers.png"] and jobs[0].object_type is None


def test_types_only_are_named_after_the_type_in_their_folder(tmp_path):
    types = tmp_path / "t"
    jobs = plan_jobs(selection={"Dragers": {"Persleiding", "Bord"}}, tab_folder=None, type_folder=types)
    assert _names(jobs) == ["Bord.png", "Persleiding.png"] and {j.path.parent for j in jobs} == {types}


def test_both_kinds_use_their_own_folders(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    jobs = plan_jobs(selection={"Dragers": {None, "Bord"}}, tab_folder=a, type_folder=b)
    assert [j.path for j in jobs] == [a / "Dragers.png", b / "Bord.png"]


def test_missing_type_folder_raises(tmp_path):
    with pytest.raises(ValueError, match="folder"):
        plan_jobs(selection={"P": {"Bord"}}, tab_folder=tmp_path, type_folder=None)


def test_missing_tab_folder_raises(tmp_path):
    with pytest.raises(ValueError, match="folder"):
        plan_jobs(selection={"P": {None}}, tab_folder=None, type_folder=tmp_path)


def test_unneeded_folder_may_be_missing(tmp_path):
    assert plan_jobs(selection={"P": {None}}, tab_folder=tmp_path, type_folder=None)


def test_unsafe_characters_are_replaced():
    assert safe_filename('a/b:c*d?"e') == "a_b_c_d_e"


def test_same_type_in_two_passports_gets_passport_in_brackets(tmp_path):
    jobs = plan_jobs(selection={"Dragers": {"Bord"}, "Overig": {"Bord"}}, tab_folder=None, type_folder=tmp_path)
    assert _names(jobs) == ["Bord.png", "Bord (Overig).png"]


def test_type_named_like_a_tab_in_the_same_folder_gets_brackets(tmp_path):
    jobs = plan_jobs(selection={"Bord": {None, "Bord"}}, tab_folder=tmp_path, type_folder=tmp_path)
    assert _names(jobs) == ["Bord.png", "Bord (Bord).png"]


def test_remaining_duplicates_get_a_counter(tmp_path):
    jobs = plan_jobs(selection={"A": {"x", "X"}}, tab_folder=None, type_folder=tmp_path)
    assert _names(jobs) == ["X.png", "x (A).png"] or len(set(_names(jobs))) == 2
    three = plan_jobs(selection={"A": {"x", "X", "x "}}, tab_folder=None, type_folder=tmp_path)
    assert len({n.casefold() for n in _names(three)}) == 3


def test_existing_lists_only_present_files(tmp_path):
    jobs = plan_jobs(selection={"A": {None}, "B": {None}}, tab_folder=tmp_path, type_folder=None)
    (tmp_path / "A.png").write_bytes(b"x")
    assert [j.passport for j in existing(jobs)] == ["A"]
