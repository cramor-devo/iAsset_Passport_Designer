from __future__ import annotations

from openpyxl import load_workbook

from passport_designer.excel_export import MUTED_COLOUR, export_workbook, sheet_layout
from passport_designer.layout_engine import LayoutEngine, LayoutOptions
from passport_designer.models import AttributeFlags, norm
from passport_designer.profiles import LEGACY, ROTTERDAM_V3


def _bord_tab(spec):
    return next(t for t in LayoutEngine(spec, LayoutOptions(profile=LEGACY)).build_all() if t.name == "Bord")


def _nee_for_all_types(spec, attribute: str) -> None:
    for object_type in ("APV-bord", "Verkeersbord"):
        spec.flags.setdefault(object_type, {})[norm(attribute)] = AttributeFlags(include=False)


def test_muted_cells_grey_italic(wave1_spec):
    tab = _bord_tab(wave1_spec)
    layout = sheet_layout(tab, muted={norm("breedte")})
    fields = [c for c in layout.cells if c.value.startswith("breedte")]
    assert fields and all(c.italic and c.colour == MUTED_COLOUR for c in fields)
    others = [c for c in layout.cells if c.value.startswith("hoogte")]
    assert others and not any(c.italic or c.colour for c in others)


def test_export_all_fields_writes_muted_cells_grey_italic(tmp_path, wave1_spec):
    _nee_for_all_types(wave1_spec, "breedte")
    tab = _bord_tab(wave1_spec)
    target = export_workbook([tab], tmp_path / "all.xlsx", spec=wave1_spec, only_included=False)
    sheet = load_workbook(target)[tab.name]
    cells = [c for row in sheet.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("breedte")]
    assert cells and all(c.font.i and c.font.color.rgb.endswith(MUTED_COLOUR) for c in cells)


def test_metadata_only_included(tmp_path, wave1_spec):
    tab = _bord_tab(wave1_spec)
    for only, expected in ((True, "true"), (False, "false")):
        target = export_workbook([tab], tmp_path / f"{expected}.xlsx", spec=wave1_spec, only_included=only)
        meta = load_workbook(target)["_designer"]
        rows = {row[0].value: row[1].value for row in meta.iter_rows(min_row=2)}
        assert rows["only_included"] == expected


# --- Minimale dataset in de export / Minimal dataset in the export --------------------------------------------

from passport_designer.dataset_flags import MDS_COMMON, minimal_labels, minimal_marks  # noqa: E402


def _mds(spec, tab, flags: dict[str, list[str]]):
    for attribute, types in flags.items():
        for t in types:
            spec.flags.setdefault(t, {})[norm(attribute)] = AttributeFlags(minimal=True)
    return minimal_marks(minimal_labels(spec, tab=tab), tab_types=[o.name for o in tab.object_types])


def _v3_tab(spec):
    return next(t for t in LayoutEngine(spec, LayoutOptions(profile=ROTTERDAM_V3)).build_all() if t.name == "Bord")


def _cell(layout, prefix: str):
    return next(c for c in layout.cells if c.value.startswith(prefix))


def test_type_fill_written(wave1_spec):
    tab = _bord_tab(wave1_spec)
    marks, legend = _mds(wave1_spec, tab, {"APV-verordening": ["APV-bord"]})
    layout = sheet_layout(tab, minimal=marks, legend=legend)
    assert _cell(layout, "APV-verordening").fill == legend["APV-bord"]


def test_common_fill_written(tmp_path, wave1_spec):
    tab = _bord_tab(wave1_spec)
    marks, legend = _mds(wave1_spec, tab, {"breedte": ["APV-bord", "Verkeersbord"]})
    target = export_workbook([tab], tmp_path / "m.xlsx", spec=wave1_spec, minimal_by_tab={tab.name: (marks, legend)})
    sheet = load_workbook(target)[tab.name]
    cells = [c for row in sheet.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("breedte")]
    assert cells and all(c.fill.fgColor.rgb.endswith(MDS_COMMON) for c in cells)


def test_stripes_gradient_written(tmp_path, wave1_spec):
    from passport_designer.models import ObjectType

    wave1_spec.object_types.append(ObjectType("Zebrabord", "Bord", "Borden"))
    wave1_spec.attributes["Zebrabord"] = ["breedte", "hoogte"]
    tab = _bord_tab(wave1_spec)
    marks, legend = _mds(wave1_spec, tab, {"hoogte": ["APV-bord", "Zebrabord"]})
    assert len(marks[norm("hoogte")].colours) == 2
    target = export_workbook([tab], tmp_path / "s.xlsx", minimal_by_tab={tab.name: (marks, legend)})
    sheet = load_workbook(target)[tab.name]
    cells = [c for row in sheet.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("hoogte")]
    assert cells and all(c.fill.type == "linear" and len(c.fill.stop) == 4 for c in cells)


def test_legend_row_cells_coloured(wave1_spec):
    tab = _v3_tab(wave1_spec)
    marks, legend = _mds(wave1_spec, tab, {"breedte": ["APV-bord"]})
    layout = sheet_layout(tab, minimal=marks, legend=legend)
    for name, colour in legend.items():
        assert _cell(layout, name).fill == colour and _cell(layout, name).row == 3
    assert _cell(layout, "All types").fill == MDS_COMMON


def test_no_fill_or_legend_when_off(tmp_path, wave1_spec):
    tab = _bord_tab(wave1_spec)
    _mds(wave1_spec, tab, {"breedte": ["APV-bord"]})
    layout = sheet_layout(tab)
    assert not any(c.fill_stops or (c.fill and c.fill not in ("D9D9D9", "D9E2F3", "D9D2E9")) for c in layout.cells)
    assert not any(c.value == "All types" for c in layout.cells)
    meta = load_workbook(export_workbook([tab], tmp_path / "o.xlsx"))["_designer"]
    assert {r[0].value: r[1].value for r in meta.iter_rows(min_row=2)}["minimal_dataset_shown"] == "false"


def test_marks_and_deleted_roundtrip_through_designer_sheet(tmp_path, wave1_spec):
    import openpyxl

    from passport_designer.excel_export import VERIFY_COLOUR, export_workbook
    from passport_designer.refined_import import read_metadata

    tab = _bord_tab(wave1_spec)
    label = next(c.label for s in tab.sections for r in s.rows for c in r)
    path = tmp_path / "v.xlsx"
    export_workbook([tab], path, verify_by_tab={tab.name: {norm(label)}}, deleted_by_tab={tab.name: {"gone"}})
    sheet = openpyxl.load_workbook(path)[tab.name]
    reds = [c for row in sheet.iter_rows() for c in row if c.font.color is not None
            and str(c.font.color.rgb).endswith(VERIFY_COLOUR)]
    assert reds and str(reds[0].value).startswith(label)
    info = (read_metadata(path) or {})["sheets"][tab.name]
    assert info["verify"] == [norm(label)] and info["deleted"] == ["gone"]
