"""Handmatige aanpassingen per paspoort: velden markeren ('controleren met klant') of verwijderen; geen Qt.
Manual adjustments per passport: mark fields ('verify with customer') or delete them; no Qt."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from .models import Cell, PassportTab, Section, SectionStyle, norm


@dataclass(frozen=True)
class TabOverride:
    """Gemarkeerde en verwijderde velden van één paspoort (genormaliseerde veldnamen).
    Marked and deleted fields of one passport (normalised field names)."""

    verify: frozenset[str] = frozenset()
    deleted: frozenset[str] = frozenset()

    @property
    def is_empty(self) -> bool:
        return not self.verify and not self.deleted


def _keys(labels: Iterable[str]) -> frozenset[str]:
    return frozenset(norm(label) for label in labels if label.strip())


def toggle_verify(override: TabOverride, *, labels: Iterable[str]) -> TabOverride:
    """Markeer de velden; staan ze al allemaal gemarkeerd, dan wordt de markering weggehaald.
    Mark the fields; when all of them are marked already, the mark is removed."""
    keys = _keys(labels)
    if not keys:
        return override
    if keys <= override.verify:
        return replace(override, verify=override.verify - keys)
    return replace(override, verify=override.verify | keys)


def delete_fields(override: TabOverride, *, labels: Iterable[str]) -> TabOverride:
    """Verwijder velden uit dit paspoort (de markering blijft bewaard voor herstellen).
    Delete fields from this passport (the mark is kept so that a restore brings it back)."""
    return replace(override, deleted=override.deleted | _keys(labels))


def restore_fields(override: TabOverride, *, labels: Iterable[str]) -> TabOverride:
    """Haal verwijderde velden terug op hun gegenereerde plek. / Bring deleted fields back at their generated spot."""
    return replace(override, deleted=override.deleted - _keys(labels))


def _is_protected(section: Section) -> bool:
    """Herhaalbare en notitiesecties blijven heel: de iAsset-payloadcodes hangen ervan af.
    Repeatable and notes sections stay intact: the iAsset payload codes depend on them."""
    return section.repeater or section.style is SectionStyle.NOTES


def deletable_labels(tab: PassportTab, labels: Iterable[str]) -> set[str]:
    """Van ``labels`` alleen de velden die niet in een herhaalbare sectie staan. / Of ``labels`` only the fields that
    are not inside a repeatable section."""
    protected = {norm(c.label) for s in tab.sections if _is_protected(s) for row in s.rows for c in row}
    return set(_keys(labels)) - protected


def tab_labels(tab: PassportTab) -> dict[str, str]:
    """Genormaliseerde veldnaam -> weergavenaam van alle velden in ``tab``. / Normalised field name -> display name
    of all fields in ``tab``."""
    sections = [s for s in tab.sections if s.style is not SectionStyle.NOTES]
    return {norm(c.label): c.label for s in sections for r in s.rows for c in r}


def apply_override(tab: PassportTab, override: TabOverride) -> tuple[PassportTab, set[str]]:
    """Kopie van ``tab`` zonder de verwijderde velden (rijen sluiten op, lege rijen en secties verdwijnen), plus de
    gemarkeerde veldnamen die erin voorkomen. Velden in herhaalbare secties blijven staan.
    Copy of ``tab`` without the deleted fields (rows close up, empty rows and sections disappear), plus the marked
    field names that occur in it. Fields in repeatable sections stay."""
    present = set(tab_labels(tab))
    verify = set(override.verify) & present
    if not override.deleted:
        return tab, verify
    sections: list[Section] = []
    for section in tab.sections:
        if _is_protected(section):
            sections.append(section)
            continue
        rows: list[list[Cell]] = []
        margin: dict[int, str] = {}
        had_fields = False
        for index, row in enumerate(section.rows):
            kept = [c for c in row if norm(c.label) not in override.deleted]
            had_fields = had_fields or bool(row)
            if row and not kept:
                continue  # hele rij weg / whole row gone
            if index in section.margin:
                margin[len(rows)] = section.margin[index]
            rows.append(kept)
        if had_fields and not any(rows):
            continue  # alle velden weg: sectie ook / all fields gone: the section too
        sections.append(replace(section, rows=rows, margin=margin))
    return replace(tab, sections=sections), verify
