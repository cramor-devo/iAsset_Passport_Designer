"""Tests voor id_check. / Tests for id_check."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from passport_designer.field_catalog import FieldCatalog, FieldInfo, catalog_from_records
from passport_designer.field_map import FieldIdMap
from passport_designer.id_check import (
    IdFinding,
    check_ids,
    export_id_report,
    summarize,
    summary_text,
)
from passport_designer.models import Cell, ObjectType, PassportTab, Section


def make_catalog(with_names: bool = True) -> FieldCatalog:
    cat = FieldCatalog(source="t.xlsx")
    cat.entries = {
        1000: FieldInfo(1000, "Soortnaam", "pulldown", "select", subthemes=frozenset({8024, 8025})),
        1002: FieldInfo(1002, "Knipfactor", "cijferveld", "numeric", subthemes=frozenset({8025})),
        1010: FieldInfo(1010, "Dup", "pulldown", "select"),
        1011: FieldInfo(1011, "dup", "pulldown", "select"),
    }
    if with_names:
        cat.subtheme_names = {8024: "Bos", 8025: "Bosplantsoen"}
    return cat


def make_tab(*labels: str, footnote_types: list[str] | None = None) -> PassportTab:
    cells = [Cell(label=lab) for lab in labels]
    footnotes: dict[int, list[str]] = {}
    if footnote_types is not None:
        cells[0] = Cell(label=labels[0], footnote=1)
        footnotes[1] = footnote_types
    types = [ObjectType("Bos", "F"), ObjectType("Bosplantsoen", "F"), ObjectType("Onbekend", "F")]
    return PassportTab("Tab", "G", types, [Section("Sec", rows=[cells])], footnotes=footnotes)


def by_status(findings: list[IdFinding], status: str) -> list[IdFinding]:
    return [f for f in findings if f.status == status]


def test_ok_missing_disabled_and_unmatched():
    findings = check_ids([make_tab("Soortnaam", "Soortnaam*", "Knipfactor", "Zonder")], make_catalog())
    ok = by_status(findings, "ok")
    assert [(f.label, f.field_id) for f in ok] == [("Soortnaam", 1000)]
    missing = by_status(findings, "missing-id")
    assert [f.label for f in missing] == ["Zonder"] and missing[0].severity == "error"
    disabled = by_status(findings, "subtheme-disabled")
    assert len(disabled) == 1 and disabled[0].label == "Knipfactor" and disabled[0].object_types == ["Bos"]
    unknown = by_status(findings, "subtheme-unknown")
    assert len(unknown) == 1 and unknown[0].severity == "warning" and unknown[0].object_types == ["Onbekend"]


def test_footnote_limits_object_types():
    tab = make_tab("Knipfactor", footnote_types=["Bosplantsoen"])
    assert not by_status(check_ids([tab], make_catalog()), "subtheme-disabled")


def test_ambiguous_without_id_map():
    findings = check_ids([make_tab("Dup")], make_catalog())
    assert by_status(findings, "ambiguous")[0].severity == "warning"


def test_unknown_id_and_label_mismatch():
    ids = FieldIdMap()
    ids.add("Ghost", 999)
    ids.add("Alias", 1000)
    findings = check_ids([make_tab("Ghost", "Alias")], make_catalog(), ids)
    assert by_status(findings, "unknown-id")[0].field_id == 999
    mismatch = by_status(findings, "label-mismatch")[0]
    assert mismatch.label == "Alias" and "Soortnaam" in mismatch.detail


def test_ambiguous_from_id_map():
    ids = FieldIdMap()
    ids.add("Soortnaam", 1000)
    ids.add("Soortnaam", 1001)
    assert by_status(check_ids([make_tab("Soortnaam")], make_catalog(), ids), "ambiguous")


def test_type_mismatch_between_sources():
    ids = FieldIdMap()
    ids.add("Knipfactor", 1002)
    ids.catalog = catalog_from_records([{"id": 1002, "label": "Knipfactor", "type": "select"}])
    findings = check_ids([make_tab("Knipfactor")], make_catalog(), ids)
    assert len(by_status(findings, "type-mismatch")) == 1
    ids.catalog = catalog_from_records([{"id": 1002, "label": "Knipfactor", "type": "weird"}])
    assert not by_status(check_ids([make_tab("Knipfactor")], make_catalog(), ids), "type-mismatch")
    ids.catalog = make_catalog()
    assert not by_status(check_ids([make_tab("Knipfactor")], make_catalog(), ids), "type-mismatch")


def test_subtheme_names_unknown_gives_single_info():
    findings = check_ids([make_tab("Soortnaam"), make_tab("Knipfactor")], make_catalog(with_names=False))
    unknown = by_status(findings, "subtheme-unknown")
    assert len(unknown) == 1 and unknown[0].severity == "info"
    assert not by_status(findings, "subtheme-disabled")


def test_summary_and_export(tmp_path: Path):
    findings = check_ids([make_tab("Soortnaam", "Zonder")], make_catalog())
    assert summarize(findings)["missing-id"] == 1
    assert "1 missing-id" in summary_text(findings)
    out = tmp_path / "r.xlsx"
    export_id_report(findings, out)
    ws = load_workbook(out)["ID-controle"]
    assert [c.value for c in ws[1]][:5] == ["Tab", "Section", "Label", "Field ID", "Status"]
    assert ws.max_row == len(findings) + 1 and ws.auto_filter.ref and ws.freeze_panes == "A2"
    assert {str(ws.cell(r, 5).value) for r in range(2, ws.max_row + 1)} >= {"ok", "missing-id"}


def test_id_map_resolves_duplicate_catalog_label():
    ids = FieldIdMap()
    ids.add("Dup", 1010)
    findings = check_ids([make_tab("Dup")], make_catalog(), ids)
    assert not by_status(findings, "ambiguous")
    # het gekozen ID wordt wel gevalideerd (subthema) / the chosen ID is still validated (subtheme)
    assert {(f.field_id, f.status) for f in findings if f.label == "Dup"} == {(1010, "subtheme-disabled")}
    ids = FieldIdMap()
    ids.add("Dup", 4242)
    assert by_status(check_ids([make_tab("Dup")], make_catalog(), ids), "unknown-id")
