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


def test_equal_columns_without_widths(tab):
    mockup = PassportMockup()
    mockup.show_tab(tab, "", DARK)
    assert set(mockup.column_stretch()) == {1}
    grid = first_grid(mockup)
    assert {grid.columnStretch(i) for i in range(5)} == {1}


def test_excel_widths_become_stretch_factors(tab):
    mockup = PassportMockup()
    mockup.show_tab(tab, "", LIGHT, column_widths=[10.0, 20.0, 0.0, 40.0])
    stretch = mockup.column_stretch()
    assert stretch[:2] == [100, 200] and stretch[3] == 400 and stretch[2] == round(8.43 * 10)
    grid = first_grid(mockup)
    assert [grid.columnStretch(i) for i in range(4)] == [100, 200, stretch[2], 400]


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
