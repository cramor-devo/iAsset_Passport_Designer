"""Vlaggen per veld uit de specificatie (Opnemen) voor weergave en export; geen Qt.
Flags per field from the specification (Opnemen) for display and export; no Qt."""

from __future__ import annotations

from dataclasses import dataclass

from .models import PassportTab, SpecModel, norm


def source_type(spec: SpecModel, object_type: str) -> str:
    """Objecttype zonder eigen attributen erft van het objecttype waarop de naam eindigt (Piramideblok -> Blok).
    An object type without own attributes inherits from the type its name ends with (Piramideblok -> Blok)."""
    if spec.attributes.get(object_type):
        return object_type
    name = norm(object_type)
    candidates = [
        c
        for c, attrs in spec.attributes.items()
        if attrs and c != object_type and len(c) >= 3 and name.endswith(norm(c))
    ]
    return max(candidates, key=len, default=object_type)


def excluded_labels(spec: SpecModel, *, tab: PassportTab) -> set[str]:
    """Genormaliseerde veldnamen die voor **alle** objecttypen van ``tab`` op Opnemen = Nee staan. Een veld dat voor
    sommige objecttypen wel geldt, telt niet mee (dan blijft het gewoon zichtbaar).
    Normalised field names that are Opnemen = Nee for **all** object types of ``tab``. A field that applies to some
    of the object types is not counted (it stays visible).

    Objecttypen zonder eigen attributen gebruiken de vlaggen van hun bronobjecttype (zie ``source_type``).
    Object types without own attributes use the flags of their source type (see ``source_type``).
    """
    per_type: list[set[str]] = []
    for object_type in tab.object_types:
        source = source_type(spec, object_type.name)
        attributes = spec.attributes.get(source, [])
        per_type.append(
            {norm(a) for a in attributes if spec.flag(object_type=source, attribute=a).include is False},
        )
    return set.intersection(*per_type) if per_type else set()


# --- Minimale dataset (MDS): kleuren per objecttype / Minimal dataset (MDS): colours per object type ---------------

MDS_COMMON = "C6EFCE"  # groen: MDS voor alle objecttypen / green: MDS for all object types
# Vaste volgorde van lichte tinten; geen groen, rood, kopgrijs D9D9D9 of Sem.Rel-blauw D9E2F3.
# Fixed order of light tints; no green, red, heading grey D9D9D9 or Sem.Rel blue D9E2F3.
MDS_TYPE_COLOURS: tuple[str, ...] = (
    "FFE699", "F8CBAD", "CCC0DA", "B7DEE8", "FFCCFF", "D9C3A5", "C9C9F5", "E2E2B5",
)


@dataclass(frozen=True)
class MinimalMark:
    """Kleur(en) en objecttypen van een veld in de minimale dataset; Ã©Ã©n kleur = vlak, meer = strepen.
    Colour(s) and object types of a field in the minimal dataset; one colour = solid, several = stripes."""

    colours: tuple[str, ...]
    types: tuple[str, ...]


def minimal_labels(spec: SpecModel, *, tab: PassportTab, object_type: str | None = None) -> dict[str, list[str]]:
    """Genormaliseerde veldnaam -> objecttypen (van ``tab``, of alleen ``object_type``) waarvoor MinimaleDataset = Ja.
    Objecttypen zonder eigen attributen gebruiken hun bronobjecttype (``source_type``).
    Normalised field name -> object types (of ``tab``, or only ``object_type``) with MinimaleDataset = Ja.
    Object types without own attributes use their source type (``source_type``)."""
    result: dict[str, list[str]] = {}
    for item in tab.object_types:
        if object_type and item.name != object_type:
            continue
        source = source_type(spec, item.name)
        for attribute in spec.attributes.get(source, []):
            if spec.flag(object_type=source, attribute=attribute).minimal is True:
                result.setdefault(norm(attribute), []).append(item.name)
    return result


def type_colours(tab_types: list[str]) -> dict[str, str]:
    """Kleur per objecttype in volgorde van het paspoort (herhaalt na 8). / Colour per object type in passport order
    (cycles after 8)."""
    return {name: MDS_TYPE_COLOURS[index % len(MDS_TYPE_COLOURS)] for index, name in enumerate(tab_types)}


def minimal_marks(
    labels: dict[str, list[str]], *, tab_types: list[str],
) -> tuple[dict[str, MinimalMark], dict[str, str]]:
    """(veldnaam -> markering, objecttype -> kleur voor de legenda). Alle typen of Ã©Ã©n type in het paspoort: groen;
    precies Ã©Ã©n type: de kleur van dat type; enkele typen: strepen in paspoortvolgorde.
    (field name -> mark, object type -> colour for the legend). All types or a single type in the passport: green;
    exactly one type: that type's colour; several types: stripes in passport order."""
    colours = type_colours(tab_types)
    marks: dict[str, MinimalMark] = {}
    for label, names in labels.items():
        ordered = tuple(t for t in tab_types if t in names)
        if not ordered:
            continue
        if len(tab_types) <= 1 or len(ordered) == len(tab_types):
            marks[label] = MinimalMark((MDS_COMMON,), ordered)
        else:
            marks[label] = MinimalMark(tuple(colours[t] for t in ordered), ordered)
    return marks, colours if len(tab_types) > 1 else {}
