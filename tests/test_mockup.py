"""Tests voor de iAsset-stijl mockup (offscreen). / Tests for the iAsset-style mockup (offscreen)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QCheckBox, QGridLayout, QHBoxLayout, QLabel, QWidget  # noqa: E402

from passport_designer.i18n import tr  # noqa: E402
from passport_designer.layout_engine import LayoutEngine  # noqa: E402
from passport_designer.models import Cell, PassportTab, Section  # noqa: E402
from passport_designer.profiles import ROTTERDAM_V3  # noqa: E402
from passport_designer.ui.mockup import EXPORT_WIDTH, PassportMockup, is_relation_table  # noqa: E402
from passport_designer.ui.theme import DARK, KIND_COLOURS, LIGHT  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def first_grid(mockup: PassportMockup) -> QGridLayout:
    grid = mockup.findChildren(QWidget, "mockRow")[0].layout()
    assert isinstance(grid, QGridLayout)
    return grid


@pytest.fixture
def tab(app, wave1_spec):
    return LayoutEngine(wave1_spec).build_all()[0]


def row_grids(mockup: PassportMockup) -> list[QGridLayout]:
    grids = [w.layout() for w in mockup.findChildren(QWidget, "mockRow")]
    return [g for g in grids if isinstance(g, QGridLayout)]


def test_row_with_n_fields_has_n_full_width_columns(tab):
    mockup = PassportMockup()
    mockup.show_tab(tab, "", DARK)
    sizes = set()
    for index, section in enumerate(tab.sections):
        plain = not section.repeater and not is_relation_table(section, tab.profile)
        for row_index, row in enumerate(section.rows):
            assert mockup.row_stretch(index, row_index, list(range(len(row)))) == [1] * len(row)
            if row and plain:
                sizes.add(len(row))
    grids = row_grids(mockup)
    counts = {g.columnCount() for g in grids}
    assert counts == sizes and len(sizes) > 1  # rijen met 3 en 4 velden / rows with 3 and 4 fields
    for grid in grids:
        assert {grid.columnStretch(i) for i in range(grid.columnCount())} == {1}
        assert grid.count() == 2 * grid.columnCount()  # kop + waarde per veld, geen lege plekken


def test_excel_widths_of_occupied_columns_become_stretch_factors(tab):
    mockup = PassportMockup()
    positions = {(0, 0, 0): (4, 1), (0, 0, 1): (4, 3), (0, 0, 2): (4, 4)}
    mockup.show_tab(tab, "", LIGHT, column_widths=[10.0, 20.0, 0.0, 40.0], positions=positions)
    assert mockup.row_stretch(0, 0, [0, 1, 2]) == [100, round(8.43 * 10), 400]
    grid = row_grids(mockup)[0]
    assert [grid.columnStretch(i) for i in range(3)] == [100, round(8.43 * 10), 400]


def test_styling_elements_and_extra_tabs(tab):
    mockup = PassportMockup()
    mockup.show_tab(tab, "", DARK)
    assert mockup.findChildren(QLabel, "mockTabActive")[0].text() == tab.name
    assert len(mockup.findChildren(QLabel, "mockTab")) == 3
    assert mockup.findChildren(QLabel, "mockSection") and mockup.findChildren(QLabel, "mockHead")
    mockup.show_extra_tabs = False
    mockup.show_tab(tab, "", DARK)
    assert not mockup.findChildren(QLabel, "mockTab")


def test_footnote_markers_stay_visible(tab):
    mockup = PassportMockup()
    mockup.show_tab(tab, "", DARK)
    heads = [h.text() for h in mockup.findChildren(QLabel, "mockHead")]
    assert any(h.endswith("(1)") for h in heads)


def test_highlights_outline_only_when_given(tab):
    plain = PassportMockup()
    plain.show_tab(tab, "", DARK)
    marked = PassportMockup()
    marked.show_tab(tab, "", DARK, highlights={"bordcode": "added"})
    colour = KIND_COLOURS["added"]
    assert not any(colour in w.styleSheet() for w in plain.findChildren(QLabel))
    assert any(colour in w.styleSheet() for w in marked.findChildren(QLabel, "mockValue"))
    assert marked.render_pixmap().width() == EXPORT_WIDTH


def test_labels_are_centred_and_value_boxes_sit_centred_under_them(tab):
    mockup = PassportMockup()
    mockup.show_tab(tab, "", DARK)
    for head in mockup.findChildren(QLabel, "mockHead"):
        assert head.alignment() & Qt.AlignmentFlag.AlignHCenter
    for value in mockup.findChildren(QLabel, "mockValue"):
        assert value.alignment() & Qt.AlignmentFlag.AlignLeft  # tekst in het vak links / text inside is left
    for holder in mockup.findChildren(QWidget, "mockValueHolder"):
        layout = holder.layout()
        assert isinstance(layout, QHBoxLayout) and layout.count() == 3
        assert layout.stretch(0) == layout.stretch(2) > 0 and layout.stretch(1) > layout.stretch(0)
    for grid in row_grids(mockup):
        assert grid.contentsMargins().left() == grid.contentsMargins().right()


def test_remark_lines_are_centred(tab):
    mockup = PassportMockup()
    mockup.show_tab(tab, "", DARK)
    notes = [n for n in mockup.findChildren(QLabel) if n.text().startswith("*IMBOR")]
    assert notes and all(n.alignment() & Qt.AlignmentFlag.AlignHCenter for n in notes)


def test_repeater_has_one_header_band_and_three_value_rows(tab):
    mockup = PassportMockup()
    mockup.show_tab(tab, "", DARK)
    section = next(s for s in tab.sections if s.title.startswith("Actoren en rollen"))
    assert section.repeater
    block = [b for b in mockup.findChildren(QWidget, "mockRepeater")]
    assert len(block) >= 1
    actors = next(b for b in block if any(h.text() == "Rol" for h in b.findChildren(QLabel, "mockHead")))
    assert len(actors.findChildren(QWidget, "mockRepeatHead")) == 1
    assert len(actors.findChildren(QLabel, "mockHead")) == 4
    rows = actors.findChildren(QWidget, "mockRepeatRow")
    assert len(rows) == 3
    assert all(len(r.findChildren(QLabel, "mockValue")) == 4 for r in rows)
    assert "…" not in [h.text() for h in actors.findChildren(QLabel, "mockHead")]
    zebra = [r.styleSheet() for r in rows]
    assert zebra[0] != zebra[1] and zebra[0] == zebra[2]
    pill = actors.findChildren(QLabel, "mockValue")[0].styleSheet()
    assert DARK.header_band in pill and "padding: 2px 10px" in pill


def test_memo_is_a_table_with_search_boxes_and_pager(tab):
    mockup = PassportMockup()
    mockup.show_tab(tab, "", DARK)
    tables = mockup.findChildren(QWidget, "mockTable")
    assert len(tables) >= 1
    table = next(t for t in tables if t.findChildren(QLabel, "mockNoData"))
    assert [t.text() for t in table.findChildren(QLabel, "mockTableHead")] == ["Nummer", "Memo veld"]
    assert all(t.alignment() & Qt.AlignmentFlag.AlignLeft for t in table.findChildren(QLabel, "mockTableHead"))
    assert [b.text() for b in table.findChildren(QLabel, "mockSearch")] == ["Zoeken op nummer", "Zoeken op memo veld"]
    assert len(table.findChildren(QLabel, "mockTableIcon")) == 3
    assert table.findChildren(QLabel, "mockNoData")[0].text() == tr("mock.no_data")
    assert table.findChildren(QLabel, "mockPagerText")[0].text() == tr("mock.pager")
    assert len(table.findChildren(QLabel, "mockPagerButton")) == 4
    assert not table.findChildren(QLabel, "mockHead")  # geen donkere band / no dark band


def test_table_sections_are_configurable_per_profile(tab):
    assert tab.profile.is_table_section("Memo (Sem.Rel)") and not tab.profile.is_table_section("Actoren (Sem.Rel)")


def _relation_tab() -> PassportTab:
    sections = [
        Section("Drager informatie (Sem.Rel)", rows=[[Cell(x) for x in ("Nummer", "Naam", "Thema", "Subthema")]],
                repeater=True),
        Section("Constructielagen (Sem.Rel)", rows=[[Cell("Laagnummer"), Cell("Objecttype")], [Cell("…")] * 2],
                repeater=True),
        Section("Memo (Sem.Rel)", rows=[[Cell("Nummer"), Cell("Memo veld")]], repeater=True),
        Section("Actoren en rollen (Sem.Rel)", rows=[[Cell("Rol"), Cell("Actor")]], repeater=True),
    ]
    return PassportTab("Drager", "", [], sections, profile=ROTTERDAM_V3)


def test_relation_sections_render_as_tables_with_sample_rows(app):
    mockup = PassportMockup()
    for palette in (DARK, LIGHT):
        mockup.show_tab(_relation_tab(), "", palette)
        tables = mockup.findChildren(QWidget, "mockTable")
        assert len(tables) == 3  # twee relaties + memo; Actoren blijft repeater / actors stays repeater
        drager, lagen, memo = tables
        assert [b.text() for b in drager.findChildren(QLabel, "mockSearch")] == ["Zoeken op nummer", "Zoeken op naam"]
        dropdowns = drager.findChildren(QWidget, "mockDropdown")
        assert len(dropdowns) == 2
        assert all([x.text() for x in d.findChildren(QLabel)] == ["Alle", "⌄"] for d in dropdowns)
        assert len(lagen.findChildren(QWidget, "mockDropdown")) == 1  # Objecttype
        rows = drager.findChildren(QWidget, "mockTableRow")
        assert len(rows) == 3 and len(rows[0].findChildren(QCheckBox)) == 1
        assert len(drager.findChildren(QCheckBox)) == 4  # 3 rijen + filterrij / 3 rows + filter row
        assert drager.findChildren(QLabel, "mockPagerText")[0].text() == tr("mock.pager_rows")
        assert [x.text() for x in drager.findChildren(QLabel, "mockLink")] == ["<u>n.v.t.</u>"] * 3
        assert memo.findChildren(QLabel, "mockNoData")[0].text() == tr("mock.no_data")
        assert memo.findChildren(QLabel, "mockPagerText")[0].text() == tr("mock.pager")
        assert not memo.findChildren(QCheckBox)
        assert len(mockup.findChildren(QWidget, "mockRepeatHead")) == 1
    assert not mockup.render_pixmap().isNull()


def test_extra_table_prefixes_still_work():
    profile = ROTTERDAM_V3.__class__(**{**ROTTERDAM_V3.__dict__, "table_sections": ("Memo", "Foo")})
    assert is_relation_table(Section("Foo bar"), profile) and not is_relation_table(Section("Basis"), profile)
