from __future__ import annotations

from passport_designer.dataset_flags import excluded_labels
from passport_designer.layout_engine import LayoutEngine, LayoutOptions
from passport_designer.models import AttributeFlags, norm
from passport_designer.profiles import LEGACY


def _bord_tab(spec):
    return next(t for t in LayoutEngine(spec, LayoutOptions(profile=LEGACY)).build_all() if t.name == "Bord")


def _set_nee(spec, object_type: str, attribute: str) -> None:
    spec.flags.setdefault(object_type, {})[norm(attribute)] = AttributeFlags(include=False)


def test_excluded_labels_all_types_nee(wave1_spec):
    _set_nee(wave1_spec, "APV-bord", "breedte")
    _set_nee(wave1_spec, "Verkeersbord", "breedte")
    assert norm("breedte") in excluded_labels(wave1_spec, tab=_bord_tab(wave1_spec))


def test_partial_nee_not_muted(wave1_spec):
    # 'geheim' staat alleen bij APV-bord op Nee; Verkeersbord heeft het niet: het blijft zichtbaar.
    # 'geheim' is Nee only for APV-bord; Verkeersbord does not have it, so it stays visible.
    assert norm("geheim") not in excluded_labels(wave1_spec, tab=_bord_tab(wave1_spec))


def test_excluded_labels_empty_without_nee(wave1_spec):
    assert excluded_labels(wave1_spec, tab=_bord_tab(wave1_spec)) == set()


# --- Minimale dataset / Minimal dataset --------------------------------------------------------------------------

from passport_designer.dataset_flags import (  # noqa: E402
    MDS_COMMON,
    MDS_TYPE_COLOURS,
    minimal_labels,
    minimal_marks,
    type_colours,
)


def _set_minimal(spec, object_type: str, attribute: str) -> None:
    spec.flags.setdefault(object_type, {})[norm(attribute)] = AttributeFlags(minimal=True)


def _marks(spec, types: list[str] | None = None, object_type: str | None = None):
    tab = _bord_tab(spec)
    labels = minimal_labels(spec, tab=tab, object_type=object_type)
    return minimal_marks(labels, tab_types=types or [o.name for o in tab.object_types])


def test_all_types_common_green(wave1_spec):
    for t in ("APV-bord", "Verkeersbord"):
        _set_minimal(wave1_spec, t, "breedte")
    marks, _legend = _marks(wave1_spec)
    assert marks[norm("breedte")].colours == (MDS_COMMON,)


def test_single_type_gets_type_colour(wave1_spec):
    _set_minimal(wave1_spec, "APV-bord", "APV-verordening")
    marks, legend = _marks(wave1_spec)
    assert marks[norm("APV-verordening")].colours == (legend["APV-bord"],)
    assert marks[norm("APV-verordening")].types == ("APV-bord",)


def test_subset_gets_stripes_in_tab_order():
    labels = {"x": ["C", "A"]}
    marks, legend = minimal_marks(labels, tab_types=["A", "B", "C"])
    assert marks["x"].colours == (legend["A"], legend["C"]) and marks["x"].types == ("A", "C")


def test_single_selected_type_is_green(wave1_spec):
    _set_minimal(wave1_spec, "APV-bord", "breedte")
    marks, legend = _marks(wave1_spec, types=["APV-bord"], object_type="APV-bord")
    assert marks[norm("breedte")].colours == (MDS_COMMON,) and legend == {}


def test_palette_excludes_reserved_colours():
    reserved = {MDS_COMMON, "D9D9D9", "D9E2F3", "FF0000", "C00000"}
    assert not reserved & set(MDS_TYPE_COLOURS) and len(set(MDS_TYPE_COLOURS)) == len(MDS_TYPE_COLOURS)
    for colour in MDS_TYPE_COLOURS:  # niet groen / not green
        r, g, b = (int(colour[i:i + 2], 16) for i in (0, 2, 4))
        assert not (g > r + 20 and g > b + 20)


def test_more_than_8_types_cycles():
    colours = type_colours([f"T{i}" for i in range(10)])
    assert colours["T8"] == colours["T0"] and colours["T9"] == colours["T1"]


def test_inherited_type_resolved(wave1_spec):
    from passport_designer.models import ObjectType

    wave1_spec.object_types.append(ObjectType("Piramideverkeersbord", "Bord", "Borden"))
    _set_minimal(wave1_spec, "Verkeersbord", "hoogte")
    tab = _bord_tab(wave1_spec)
    assert "Piramideverkeersbord" in minimal_labels(wave1_spec, tab=tab)[norm("hoogte")]


def test_no_flags_returns_empty(wave1_spec):
    assert minimal_labels(wave1_spec, tab=_bord_tab(wave1_spec)) == {}
