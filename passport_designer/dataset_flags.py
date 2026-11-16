"""Vlaggen per veld uit de specificatie (Opnemen) voor weergave en export; geen Qt.
Flags per field from the specification (Opnemen) for display and export; no Qt."""

from __future__ import annotations

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
