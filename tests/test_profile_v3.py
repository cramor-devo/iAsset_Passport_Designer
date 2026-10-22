"""Tests voor het profiel 'rotterdam_v3' (handmatig bijgewerkt eindresultaat) en de vergelijkingstool.
Tests for the 'rotterdam_v3' profile (manually tuned end result) and the comparison tool."""

from __future__ import annotations

from conftest import make_spec
from openpyxl import load_workbook

from passport_designer.compare import compare_sheet, read_manual
from passport_designer.excel_export import export_workbook
from passport_designer.layout_engine import LayoutEngine, LayoutOptions
from passport_designer.merge_advisor import merged_tab
from passport_designer.models import ObjectType, SectionStyle, SpecModel
from passport_designer.payload import build_tab_payload
from passport_designer.profiles import PROFILES, ROTTERDAM_V3


def v3_tab(spec: SpecModel, name: str):
    return next(t for t in LayoutEngine(spec, LayoutOptions(profile=ROTTERDAM_V3)).build_all() if t.name == name)


def test_section_order_and_basis(wave1_spec):
    tab = v3_tab(wave1_spec, "Bord")
    titles = [s.title for s in tab.sections]
    assert titles[:4] == ["Basis", "Object informatie", "Locatie informatie", "Beleidsinformatie"]
    assert titles[-4:] == ["Actoren en rollen (Sem.Rel)", "Memo (Sem.Rel)", "Overige informatie", "Geometrie"]
    assert [c.label for c in tab.sections[0].rows[0]] == ["Nummer", "Objecttype", "IMBOR Filter*", "Thema", "Subthema"]
    assert "IMBOR filter zit niet" in tab.sections[0].margin[0]


def test_grid_is_five_wide_with_blank_row_between_rows(wave1_spec):
    spec = wave1_spec
    spec.attributes["APV-bord"] += [f"breedte{i}" for i in range(12)]
    rows = v3_tab(spec, "Bord").sections[1].rows
    assert max(len(r) for r in rows) == 5
    assert all(a or b for a, b in zip(rows, rows[1:], strict=False)), "never two blank rows in a row"
    assert [bool(r) for r in rows[::2]] == [True] * len(rows[::2]) and not any(rows[1::2])


def test_administrative_fields_are_not_object_information(wave1_spec):
    spec = wave1_spec
    spec.attributes["APV-bord"] += ["geostatus", "in onderzoek", "status", "nummer", "kwaliteitsniveau", "modelnaam"]
    labels = {c.label for r in v3_tab(spec, "Bord").sections[1].rows for c in r}
    assert not labels & {"geostatus", "in onderzoek", "status", "nummer", "kwaliteitsniveau"}
    assert "modelnaam" in labels  # in v3 een gewoon objectveld / a normal object field in v3


def test_repeater_sections_and_semantic_style(wave1_spec):
    sections = {s.title: s for s in v3_tab(wave1_spec, "Bord").sections}
    actors = sections["Actoren en rollen (Sem.Rel)"]
    assert actors.repeater and len(actors.rows) == 3 and actors.rows[-1][0].label == "…"
    assert actors.style is SectionStyle.SEMANTIC
    assert sections["Geometrie"].style is SectionStyle.PLAIN


def test_relation_sections_follow_the_filters(wave1_spec):
    bord = [s.title for s in v3_tab(wave1_spec, "Bord").sections]
    verharding = [s.title for s in v3_tab(wave1_spec, "Verharding").sections]
    assert "Drager informatie (Sem. rel)" in bord and "Drager informatie (Sem. rel)" not in verharding
    assert "Constructielagen (Sem.Rel)" in verharding
    assert bord.index("Drager informatie (Sem. rel)") < bord.index("Actoren en rollen (Sem.Rel)")


def test_optional_fixed_fields_only_when_attribute_exists(wave1_spec):
    spec = wave1_spec
    without = v3_tab(spec, "Bord").sections
    beleid = next(s for s in without if s.title == "Beleidsinformatie")
    assert [c.label for c in beleid.rows[0]] == ["structuurniveau", "structuurgebied", "kwaliteitsniveau", "bestemming"]
    spec.attributes["APV-bord"].append("wegcategorie duurzaam veilig")
    beleid = next(s for s in v3_tab(spec, "Bord").sections if s.title == "Beleidsinformatie")
    assert len(beleid.rows[0]) == 5


def test_object_type_without_attributes_inherits_from_parent_name():
    spec = SpecModel()
    spec.object_types = [
        ObjectType("Blok", "Weginrichtingsobject", "Wegen"),
        ObjectType("Piramideblok", "Blok", "Wegen"),
        ObjectType("Verkeersgeleidebol", "Blok", "Wegen"),
    ]
    spec.attributes = {"Blok": ["breedte", "hoogte"]}
    tab = v3_tab(spec, "Blok")
    labels = [c.label for r in tab.sections[1].rows for c in r]
    assert labels == ["breedte", "hoogte"]
    assert tab.data_gaps == ["Verkeersgeleidebol"]
    assert tab.footnotes == {}, "a type without data must not turn every field into a footnote"
    issues = build_tab_payload(tab).issues
    assert any(i.code == "no-attributes" for i in issues)


def test_payload_collapses_repeaters_and_strips_asterisks(wave1_spec):
    tab = v3_tab(wave1_spec, "Bord")
    body = build_tab_payload(tab).body
    labels = [c["label"] for g in body["fields"] for c in g["children"]]
    assert "IMBOR Filter" in labels and not any(label.endswith("*") for label in labels)
    assert "…" not in labels
    assert labels.count("Rol") == 1
    codes = {i.code for i in build_tab_payload(tab).issues}
    assert {"repeater-sections", "open-design-questions"} <= codes


def test_excel_layout_matches_manual_style(tmp_path, wave1_spec):
    tabs = LayoutEngine(wave1_spec, LayoutOptions(profile=ROTTERDAM_V3)).build_all()
    sheet = load_workbook(export_workbook(tabs, tmp_path / "v3.xlsx"))["Bord"]
    assert sheet["A1"].value == "Bord" and sheet["A1"].font.b and sheet["A1"].font.sz == 18
    assert sheet["A2"].value.startswith("Objecttypes: APV-bord")
    assert sheet["A4"].value == "Basis" and sheet["G4"].value == "Opmerkingen"
    assert "IMBOR filter zit niet" in sheet["G5"].value
    assert sheet["A5"].value == "Nummer" and not sheet["A5"].font.b
    semantic = next(c for c in sheet["A"] if c.value == "Actoren en rollen (Sem.Rel)")
    assert semantic.fill.fgColor.rgb.endswith("D9E2F3")


def test_compare_with_own_export_is_perfect(tmp_path, wave1_spec):
    engine = LayoutEngine(wave1_spec, LayoutOptions(profile=ROTTERDAM_V3))
    tab = merged_tab(wave1_spec, engine, ["Bord"], "Bord")
    path = export_workbook([tab], tmp_path / "manual.xlsx")
    manual = read_manual(path)["Bord"]
    result = compare_sheet(manual, tab)
    assert result.recall == 1.0 and result.precision == 1.0
    assert not result.missing_sections and not result.extra_sections


def test_compare_detects_removed_and_added_fields(tmp_path, wave1_spec):
    engine = LayoutEngine(wave1_spec, LayoutOptions(profile=ROTTERDAM_V3))
    tab = merged_tab(wave1_spec, engine, ["Bord"], "Bord")
    path = export_workbook([tab], tmp_path / "manual.xlsx")
    workbook = load_workbook(path)
    sheet = workbook["Bord"]
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value == "bordcode":
                cell.value = "handmatig toegevoegd"
    workbook.save(path)
    result = compare_sheet(read_manual(path)["Bord"], tab)
    assert result.object_info.missing == ["handmatig toegevoegd"]
    assert result.object_info.extra == ["bordcode"]


def test_profiles_registry_and_default():
    assert set(PROFILES) == {"rotterdam_v3", "legacy"}
    assert make_spec() is not None
