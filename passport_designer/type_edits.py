"""
Objecttypen verplaatsen naar een ander paspoort of uit een paspoort verwijderen; geen Qt.
Move object types to another passport or remove them from a passport; no Qt.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from .layout_engine import LayoutEngine
from .models import ObjectType, PassportTab


def apply_type_edits(
    engine: LayoutEngine, tabs: list[PassportTab], moves: Mapping[str, str], removed: Collection[str],
) -> list[PassportTab]:
    """Pas verplaatsingen (objecttype -> naam van het doelpaspoort) en verwijderingen toe. Aangepaste paspoorten worden
    opnieuw opgebouwd, zodat velden, voetnoten en annotaties meebewegen; een paspoort zonder objecttypen verdwijnt.
    Een verplaatsing naar een onbekend paspoort wordt genegeerd.
    Apply moves (object type -> name of the target passport) and removals. Changed passports are rebuilt so fields,
    footnotes and annotations follow; a passport without object types disappears. A move to an unknown passport is
    ignored."""
    if not moves and not removed:
        return tabs
    gone = set(removed)
    names = {t.name for t in tabs}
    live = {t: m for t, m in moves.items() if m in names and t not in gone}
    incoming: dict[str, list[ObjectType]] = {}
    for tab in tabs:
        for object_type in tab.object_types:
            target = live.get(object_type.name)
            if target is not None and target != tab.name:
                incoming.setdefault(target, []).append(object_type)
    result: list[PassportTab] = []
    for tab in tabs:
        kept = [
            o for o in tab.object_types
            if o.name not in gone and live.get(o.name, tab.name) == tab.name
        ]
        known = {o.name for o in kept}
        types = kept + [o for o in incoming.get(tab.name, []) if o.name not in known]
        if len(types) == len(tab.object_types) and all(a == b for a, b in zip(types, tab.object_types, strict=True)):
            result.append(tab)
            continue
        if not types:
            continue
        rebuilt = engine.build(tab.name, types, source_filters=tab.merged_from or [tab.original_name or tab.name])
        rebuilt.merged_from = list(tab.merged_from)
        rebuilt.original_name = tab.original_name
        result.append(rebuilt)
    return result
