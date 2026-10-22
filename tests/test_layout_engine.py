from __future__ import annotations

from passport_designer.design_rules import classify_block
from passport_designer.layout_engine import LayoutEngine, LayoutOptions, chunk, semantic_style
from passport_designer.models import Cell, SectionStyle
from passport_designer.profiles import LEGACY


def tab_by_name(spec, name, **options):
    options.setdefault("profile", LEGACY)
    tabs = {t.name: t for t in LayoutEngine(spec, LayoutOptions(**options)).build_all()}
    return tabs[name]


def test_fixed_sections_in_exact_order(wave1_spec):
    titles = [s.title for s in tab_by_name(wave1_spec, "Bord").sections]
    assert titles == [
        "Basis",
        "Object informatie",
        "Locatie (Sem.rel)",
        "Beleidsinformatie",
        "Beheer informatie (Sem.Rel)",
        "Drager informatie (Sem.)",
        "Overige informatie",
    ]


def test_basis_fields_and_group(wave1_spec):
    basis = tab_by_name(wave1_spec, "Bord").sections[0]
    assert [c.display for c in basis.rows[0]] == ["Beheergroep (Borden)", "IMBOR Filter", "Objecttype", "naam"]
    assert [c.label for c in basis.rows[1]] == ["volgnummer", "identificatie", "domein"]


def test_semantic_headings_are_purple(wave1_spec):
    sections = {s.title: s for s in tab_by_name(wave1_spec, "Bord").sections}
    assert sections["Locatie (Sem.rel)"].style is SectionStyle.SEMANTIC
    assert sections["Beheer informatie (Sem.Rel)"].style is SectionStyle.SEMANTIC
    assert sections["Drager informatie (Sem.)"].style is SectionStyle.SEMANTIC
    assert sections["Beleidsinformatie"].style is SectionStyle.PLAIN
    assert semantic_style("Iets (Sem.)") is SectionStyle.SEMANTIC


def test_grid_has_at_most_four_fields_per_row(wave1_spec):
    for tab in LayoutEngine(wave1_spec, LayoutOptions(profile=LEGACY)).build_all():
        for section in tab.sections:
            assert all(len(row) <= 4 for row in section.rows)


def test_fixed_fields_are_not_repeated_in_object_information(wave1_spec):
    labels = {c.label.casefold() for row in tab_by_name(wave1_spec, "Bord").sections[1].rows for c in row}
    assert "domein" not in labels and "identificatie" not in labels
    assert "bordcode" in labels


def test_footnotes_for_partial_attributes(wave1_spec):
    tab = tab_by_name(wave1_spec, "Bord")
    cells = {c.label: c for row in tab.sections[1].rows for c in row}
    assert cells["APV-verordening"].footnote == 1
    assert cells["APV-verordening"].display == "APV-verordening (1)"
    assert cells["breedte"].footnote is None
    assert tab.notes == ["(1) Objecttype: APV-bord"]
    assert tab.applicable("APV-verordening", "APV-bord")
    assert not tab.applicable("APV-verordening", "Verkeersbord")


def test_only_flagged_option(wave1_spec):
    flagged = tab_by_name(wave1_spec, "Bord")
    everything = tab_by_name(wave1_spec, "Bord", only_flagged=False)
    flagged_labels = {c.label for s in flagged.sections for r in s.rows for c in r}
    all_labels = {c.label for s in everything.sections for r in s.rows for c in r}
    assert "geheim" not in flagged_labels and "geheim" in all_labels


def test_blank_row_after_every_three_rows_and_between_blocks(wave1_spec):
    spec = wave1_spec
    spec.attributes["APV-bord"] += [f"breedte{i}" for i in range(14)]
    spec.attributes["Verkeersbord"] += [f"breedte{i}" for i in range(14)]
    rows = tab_by_name(spec, "Bord").sections[1].rows
    run = 0
    for row in rows:
        if row:
            run += 1
            assert run <= 3, "more than 3 consecutive filled rows"
        else:
            run = 0
    assert rows[0] and rows[-1], "no blank row at the start or the end"
    assert not any(not a and not b for a, b in zip(rows, rows[1:], strict=False)), "no double blank rows"


def test_chunk_and_classification():
    assert [len(r) for r in chunk([Cell(str(i)) for i in range(9)])] == [4, 4, 1]
    assert classify_block("type conservering") == "Materiaal/Specs"
    assert classify_block("type uitvoering") == "Vorm/Type"
    assert classify_block("bordafmeting") == "Dimensies"
    assert classify_block("productiejaar") == "Tijd/Plaatsing"
    assert classify_block("afstand tussen drager en maaiveld") == "Ligging"
    assert classify_block("iets onbekends") == "Overig"
