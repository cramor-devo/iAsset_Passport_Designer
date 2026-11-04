"""Tests voor de iAsset-stijl mockup (offscreen). / Tests for the iAsset-style mockup (offscreen)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QGridLayout, QLabel, QWidget  # noqa: E402

from passport_designer.layout_engine import LayoutEngine  # noqa: E402
from passport_designer.ui.mockup import EXPORT_WIDTH, PassportMockup  # noqa: E402
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
        for row_index, row in enumerate(section.rows):
            assert mockup.row_stretch(index, row_index, list(range(len(row)))) == [1] * len(row)
            if row:
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
