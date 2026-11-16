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
