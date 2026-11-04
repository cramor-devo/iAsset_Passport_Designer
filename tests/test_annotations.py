"""Tests voor de controle en het herstel van voetnoten en opmerkingen. Alles offline.
Tests for the check and repair of footnotes and margin remarks. Everything offline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from passport_designer.annotations import check_annotations, fix_annotations
from passport_designer.excel_export import export_workbook
from passport_designer.layout_engine import LayoutEngine, LayoutOptions
from passport_designer.models import ObjectType, SpecModel
from passport_designer.profiles import LEGACY
from passport_designer.refined_import import read_refined

COMMON = ["breedte", "hoogte"]


@pytest.fixture
def spec() -> SpecModel:
    result = SpecModel()
    result.object_types = [ObjectType(n, "Bord", "Borden") for n in ("A", "B", "C")]
    result.attributes = {
        "A": [*COMMON, "alfa", "beta", "gamma"],
        "B": [*COMMON, "alfa", "gamma", "delta"],
        "C": [*COMMON, "gamma", "delta"],
    }
    return result


@pytest.fixture
def design(tmp_path: Path, spec: SpecModel) -> Path:
    return export_workbook(LayoutEngine(spec).build_all(), tmp_path / "design.xlsx", spec=spec)


def _find(path: Path, text: str):
    sheet = load_workbook(path)["Bord"]
    for row in sheet.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith(text):
                return cell
    raise AssertionError(text)


def _edit(path: Path, action) -> Path:
    workbook = load_workbook(path)
    action(workbook["Bord"])
    workbook.save(path)
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _numbers_in_reading_order(path: Path) -> list[int]:
    refined = read_refined(path).sheets[0]
    cells = sorted(
        ((pos, refined.tab.sections[s].rows[r][c]) for (s, r, c), pos in refined.positions.items()),
        key=lambda item: item[0],
    )
    return [c.footnote for _, c in cells if c.footnote]


def _remarks(path: Path) -> dict[int, str]:
    sheet = load_workbook(path)["Bord"]
    values = {r: sheet.cell(row=r, column=7).value for r in range(5, sheet.max_row + 1)}
    return {r: str(v) for r, v in values.items() if v}


def test_clean_export_is_ok(design, spec):
    report = check_annotations(design, spec)
    assert report.ok and report.sheets_checked == ["Bord"]
    assert report.for_sheet("Bord") == [] and report.for_sheet("x") == []
    assert check_annotations(design, None).ok


def test_move_field_is_detected_and_fixed(design, spec):
    original = _digest(design)
    source = _find(design, "alfa")
    last = load_workbook(design)["Bord"].max_row

    def move(sheet):
        cell = sheet[source.coordinate]
        sheet.cell(row=last + 2, column=1, value=cell.value)
        cell.value = None

    moved = _edit(design, move)
    moved_hash = _digest(moved)
    report = check_annotations(moved, spec)
    kinds = {i.kind for i in report.issues}
    assert not report.ok and {"margin-missing", "margin-orphan"} <= kinds

    before = load_workbook(moved)["Bord"]
    style = (before["A1"].font.b, before["A1"].font.sz, before["A4"].fill.fgColor.rgb)
    widths = {k: v.width for k, v in before.column_dimensions.items()}
    result = fix_annotations(moved, spec)
    assert _digest(moved) == moved_hash and moved_hash != original
    assert result.out_path.name == "design_fixed.xlsx" and result.changes
    assert result.report_after.ok

    numbers = _numbers_in_reading_order(result.out_path)
    assert sorted(set(numbers)) == list(range(1, len(set(numbers)) + 1))
    assert [n for i, n in enumerate(numbers) if n not in numbers[:i]] == sorted(set(numbers))
    refined = read_refined(result.out_path).sheets[0]
    for (s, r, c), (_row, _col) in refined.positions.items():
        number = refined.tab.sections[s].rows[r][c].footnote
        if number:
            assert f"({number}) Objecttype:" in refined.tab.sections[s].margin[r]
    after = load_workbook(result.out_path)["Bord"]
    assert (after["A1"].font.b, after["A1"].font.sz, after["A4"].fill.fgColor.rgb) == style
    assert {k: v.width for k, v in after.column_dimensions.items()} == widths


def test_renumber_in_reading_order(design, spec):
    def swap(sheet):
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.endswith("(1)"):
                    cell.value = cell.value[:-3] + "(9)"

    result = fix_annotations(_edit(design, swap), spec)
    assert result.report_after.ok
    assert _numbers_in_reading_order(result.out_path)[0] == 1
    metadata = read_refined(result.out_path).metadata
    assert metadata is not None
    footnotes = metadata["sheets"]["Bord"]["footnotes"]
    assert set(footnotes) == set(range(1, len(footnotes) + 1))
    assert footnotes[1] == read_refined(result.out_path).sheets[0].tab.footnotes[1]


def test_wrong_types_vs_spec(design, spec):
    def tamper(sheet):
        for row in sheet.iter_rows(min_col=7, max_col=7):
            for cell in row:
                if isinstance(cell.value, str) and "Objecttype: A, B" in cell.value:
                    cell.value = cell.value.replace("A, B", "A, C", 1)

    tampered = _edit(design, tamper)
    report = check_annotations(tampered, spec)
    assert any(i.kind == "wrong-types" and i.severity == "error" for i in report.issues)
    result = fix_annotations(tampered, spec)
    assert result.report_after.ok
    assert not any(i.kind == "wrong-types" for i in check_annotations(result.out_path, spec).issues)


def test_removed_marker_is_missing_and_fix_adds_it(design, spec):
    cell = _find(design, "alfa")

    def strip(sheet):
        sheet[cell.coordinate].value = "alfa"

    stripped = _edit(design, strip)
    assert any(i.kind == "missing-marker" for i in check_annotations(stripped, spec).issues)
    result = fix_annotations(stripped, spec)
    assert result.report_after.ok
    assert str(load_workbook(result.out_path)["Bord"][cell.coordinate].value).startswith("alfa (")


def test_unexpected_marker_removed(design, spec):
    cell = _find(design, "breedte")
    stars = _edit(design, lambda s: setattr(s[cell.coordinate], "value", "breedte (7) *"))
    assert any(i.kind == "unexpected-marker" for i in check_annotations(stars, spec).issues)
    result = fix_annotations(stars, spec)
    assert result.report_after.ok
    assert load_workbook(result.out_path)["Bord"][cell.coordinate].value == "breedte *"


def test_no_spec_mode(design):
    cell = _find(design, "alfa")
    assert str(cell.value).endswith("(1)")
    edited = _edit(design, lambda s: setattr(s[cell.coordinate], "value", "alfa (5)"))
    kinds = {i.kind for i in check_annotations(edited, None).issues}
    assert "gap" in kinds and "wrong-types" not in kinds
    result = fix_annotations(edited, None)
    assert result.report_after.ok
    assert _numbers_in_reading_order(result.out_path)[0] == 1


def test_unknown_label_is_info(design, spec):
    last = load_workbook(design)["Bord"]
    row = next(c.row for c in last["A"] if c.value == "Object informatie") + 1
    edited = _edit(design, lambda s: setattr(s.cell(row=row, column=5), "value", "mysterie"))
    report = check_annotations(edited, spec)
    assert any(i.kind == "unknown-label" and i.severity == "info" for i in report.issues)
    assert report.ok


def test_fixed_name_collision_and_explicit_path(design, spec, tmp_path):
    first = fix_annotations(design, spec)
    second = fix_annotations(design, spec)
    assert (first.out_path.name, second.out_path.name) == ("design_fixed.xlsx", "design_fixed_2.xlsx")
    explicit = fix_annotations(design, spec, out_path=tmp_path / "x.xlsx")
    assert explicit.out_path.name == "x.xlsx"
    with pytest.raises(ValueError):
        fix_annotations(design, spec, out_path=design)


def test_metadata_footnotes_updated(design, spec):
    def drop_first(sheet):
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.endswith("(1)"):
                    cell.value = cell.value[:-4]

    result = fix_annotations(_edit(design, drop_first), spec)
    rows = load_workbook(result.out_path)["_designer"].iter_rows(min_row=2)
    info = json.loads(str(next(r[1].value for r in rows if r[0].value == "sheet:Bord")))
    assert result.report_after.ok
    assert "1" in info["footnotes"]
    assert _remarks(result.out_path)


def _section_labels(path: Path, skip_object: bool) -> list[tuple[str, str, int | None]]:
    refined = read_refined(path).sheets[0]
    return [
        (section.title, cell.label, cell.footnote)
        for section in refined.tab.sections
        if (section.title != "Object informatie") == skip_object
        for row in section.rows
        for cell in row
    ]


def test_fresh_merged_export_has_no_findings_in_relation_sections(tmp_path, wave1_spec):
    from passport_designer.merge_advisor import merged_tab

    engine = LayoutEngine(wave1_spec)
    tab = merged_tab(wave1_spec, engine, ["Bord", "Verharding"], "Combi")
    assert "aanlegjaar" in {c.label.lower() for s in tab.sections for r in s.rows for c in r if c.footnote}
    path = export_workbook([tab], tmp_path / "merged.xlsx", spec=wave1_spec)
    relation = [s for s in tab.sections if s.title.startswith(("Constructielagen", "Wegvak informatie"))]
    assert relation  # relatiesecties met veldnamen als 'aanlegjaar' / relation sections with names like 'aanlegjaar'
    report = check_annotations(path, wave1_spec)
    assert report.ok and not [i for i in report.issues if i.severity in ("error", "warning")]
    result = fix_annotations(path, wave1_spec)
    assert result.report_after.ok
    assert _section_labels(result.out_path, True) == _section_labels(path, True)
    assert not any("Constructielagen" in c or "Wegvak" in c for c in result.changes)


def test_fix_gives_each_footnoted_field_its_own_number(tmp_path):
    spec = SpecModel()
    spec.object_types = [ObjectType(n, "Bord", "Borden") for n in ("A", "B", "C")]
    spec.attributes = {
        "A": ["gamma", "alfa", "epsilon"],
        "B": ["gamma", "alfa", "epsilon", "delta"],
        "C": ["gamma", "delta"],
    }
    path = export_workbook(LayoutEngine(spec).build_all(), tmp_path / "own.xlsx", spec=spec)

    def shuffle(sheet):
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.rstrip("* ").endswith(("(1)", "(2)", "(3)")):
                    cell.value = cell.value.rsplit("(", 1)[0] + "(7)"  # alles dezelfde stale nummer

    result = fix_annotations(_edit(path, shuffle), spec)
    numbers = _numbers_in_reading_order(result.out_path)
    assert numbers == list(range(1, len(numbers) + 1)) and len(numbers) == 3  # alfa, delta, epsilon
    assert result.report_after.ok


def test_fix_warns_about_drawings_and_still_writes(design, spec):
    from openpyxl.chart import BarChart, Reference

    def add_chart(sheet):
        chart = BarChart()
        chart.add_data(Reference(sheet, min_col=1, min_row=1, max_row=3))
        sheet.add_chart(chart, "J2")

    path = _edit(design, add_chart)
    result = fix_annotations(path, spec)
    assert result.out_path.exists() and result.warnings
    assert "Bord" in result.warnings[0] or "tekening" in result.warnings[0]
    assert fix_annotations(_clean(design, spec), spec).warnings == []


def _clean(design: Path, spec: SpecModel) -> Path:
    return export_workbook(LayoutEngine(spec).build_all(), design.with_name("clean.xlsx"), spec=spec)


def _legacy_design(tmp_path: Path, spec: SpecModel) -> Path:
    engine = LayoutEngine(spec, LayoutOptions(profile=LEGACY))
    return export_workbook(engine.build_all(), tmp_path / "legacy.xlsx", spec=spec)


def _note_values(path: Path) -> list[str]:
    sheet = load_workbook(path)["Bord"]
    return [str(c.value) for row in sheet.iter_rows() for c in row if c.value and "Objecttype:" in str(c.value)]


def test_same_number_for_two_object_fields_is_duplicate(tmp_path):
    spec = SpecModel()
    spec.object_types = [ObjectType(n, "Bord", "Borden") for n in ("A", "B")]
    spec.attributes = {"A": [*COMMON, "alfa", "beta"], "B": COMMON}
    design = export_workbook(LayoutEngine(spec).build_all(), tmp_path / "same.xlsx", spec=spec)

    def reuse(sheet):
        for label, number in (("alfa", 1), ("beta", 1)):
            cell = _find_in(sheet, label)
            cell.value = f"{label} ({number})"

    report = check_annotations(_edit(design, reuse), spec)
    assert any(i.kind == "duplicate-number" and "(1)" in i.detail for i in report.issues)
    fixed = fix_annotations(design, spec)
    assert fixed.report_after.ok
    assert len(set(_numbers_in_reading_order(fixed.out_path))) == len(_numbers_in_reading_order(fixed.out_path))


def _find_in(sheet, text):
    for row in sheet.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith(text):
                return cell
    raise AssertionError(text)


def test_legacy_note_lines_follow_renumbering(tmp_path, spec):
    path = _legacy_design(tmp_path, spec)
    assert check_annotations(path, spec).ok
    before = _note_values(path)
    assert before

    def renumber(sheet):
        cell = _find_in(sheet, "alfa")
        cell.value = "alfa (7)"
        sheet.cell(row=sheet.max_row + 1, column=1, value="Eigen notitie")

    _edit(path, renumber)
    kinds = {i.kind for i in check_annotations(path, spec).issues}
    assert {"margin-missing", "margin-orphan"} <= kinds
    result = fix_annotations(path, spec)
    assert result.report_after.ok
    notes = _note_values(result.out_path)
    assert not any(n.startswith("(7)") for n in notes) and notes[0].startswith("(1) Objecttype:")
    values = [c.value for row in load_workbook(result.out_path)["Bord"].iter_rows() for c in row if c.value]
    assert "Eigen notitie" in values


def test_legacy_swapped_fields_keep_their_note_definitions(tmp_path, spec):
    path = _legacy_design(tmp_path, spec)

    def swap(sheet):
        alfa, beta = _find_in(sheet, "alfa"), _find_in(sheet, "beta")
        alfa.value, beta.value = beta.value, alfa.value
        sheet.cell(row=sheet.max_row + 1, column=1, value="Eigen notitie")

    _edit(path, swap)
    assert any(i.kind == "order" for i in check_annotations(path, spec).issues)
    result = fix_annotations(path, spec)
    assert result.report_after.ok
    sheet = load_workbook(result.out_path)["Bord"]
    notes = {}
    for line in _note_values(result.out_path):
        number, _, names = line.partition(") Objecttype:")
        notes[int(number.lstrip("("))] = [n.strip() for n in names.split(",")]
    for label, types in (("alfa", ["A", "B"]), ("beta", ["A"])):
        number = int(str(_find_in(sheet, label).value).split("(")[1].split(")")[0])
        assert notes[number] == types
    assert "Eigen notitie" in [c.value for row in sheet.iter_rows() for c in row]


def test_shared_number_with_matching_remarks_is_still_duplicate(tmp_path):
    spec = SpecModel()
    spec.object_types = [ObjectType(n, "Bord", "Borden") for n in ("A", "B")]
    spec.attributes = {"A": [*COMMON, "alfa", "beta"], "B": COMMON}
    design = export_workbook(LayoutEngine(spec).build_all(), tmp_path / "same.xlsx", spec=spec)

    def reuse(sheet):
        for label in ("alfa", "beta"):
            cell = _find_in(sheet, label)
            cell.value = f"{label} (1)"
            sheet.cell(row=cell.row, column=7, value="(1) Objecttype: A")

    report = check_annotations(_edit(design, reuse), spec)
    assert [i.kind for i in report.issues if i.severity != "info"] == ["duplicate-number"]
