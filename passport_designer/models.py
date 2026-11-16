"""Gegevensmodellen (geen Qt): specificatie, paspoortontwerp en validatiemeldingen.
Data models (no Qt): specification, passport design and validation issues."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from .profiles import DEFAULT_PROFILE, DesignProfile

log = logging.getLogger(__name__)

# Kolommen die standaard als filter dienen, in volgorde van voorkeur (Wave 1: Filter/Zoekfilter, Wave 2: Fase).
# Columns used as filter by default, in order of preference (Wave 1: Filter/Zoekfilter, Wave 2: Fase).
DEFAULT_FILTER_COLUMNS = ("filter", "zoekfilter", "fase")


def norm(name: str) -> str:
    """Genormaliseerde sleutel voor vergelijken (hoofdletters, spaties, voetnootnummers negeren).
    Normalised key for comparison (ignores case, whitespace and footnote numbers)."""
    return " ".join(name.casefold().split())


@dataclass(frozen=True)
class ObjectType:
    """Objecttype uit het tabblad 'Objecttypen'. / Object type from the 'Objecttypen' sheet."""

    name: str
    filter: str
    group: str = ""
    phase: str = ""
    geometry: str = ""
    # Alle kolommen van de rij (genormaliseerde kopnaam -> waarde), voor een andere filterkolom (bijv. Fase).
    # All columns of the row (normalised header -> value), for choosing another filter column (e.g. Fase).
    values: tuple[tuple[str, str], ...] = ()

    def value(self, column: str) -> str:
        """Waarde in een kolom van het tabblad 'Objecttypen'. / Value in a column of the 'Objecttypen' sheet."""
        key = norm(column)
        return next((v for k, v in self.values if k == key), "")


@dataclass
class RawSheet:
    """Ongewijzigde kopie van een specificatieblad (kopregel + rijen) uit één bronbestand.
    Unmodified copy of a specification sheet (header row + rows) from one source file."""

    source: str
    header: list[str]
    rows: list[tuple[object, ...]] = field(default_factory=list)


@dataclass(frozen=True)
class AttributeFlags:
    """Vlaggen van één attribuut uit het tabblad 'Attributen'; None = kolom of waarde ontbreekt.
    Flags of one attribute from the 'Attributen' sheet; None = column or value missing.

    include: Opnemen (Ja = True, Nee = False). minimal: MinimaleDataset (Ja = True, Nee = False).
    """

    include: bool | None = None
    minimal: bool | None = None


@dataclass
class SpecModel:
    """Ingelezen specificatie: objecttypen en hun attributen. / Loaded specification: object types and attributes."""

    sources: list[str] = field(default_factory=list)
    object_types: list[ObjectType] = field(default_factory=list)
    attributes: dict[str, list[str]] = field(default_factory=dict)
    # Attributen die in de bron op "Nee" staan (In paspoort tonen / Opnemen), per objecttype, genormaliseerd.
    # Attributes marked "Nee" in the source (In paspoort tonen / Opnemen), per object type, normalised.
    excluded: dict[str, set[str]] = field(default_factory=dict)
    # Vlaggen per objecttype en genormaliseerd attribuut (Opnemen en MinimaleDataset).
    # Flags per object type and normalised attribute (Opnemen and MinimaleDataset).
    flags: dict[str, dict[str, AttributeFlags]] = field(default_factory=dict)
    # Kopnamen van het tabblad 'Objecttypen' (zonder 'Objecttype') en de gekozen filterkolom ("" = 'Filter' of de
    # eerste beschikbare van Filter/Zoekfilter/Fase bij het inlezen).
    # Headers of the 'Objecttypen' sheet (without 'Objecttype') and the chosen filter column ("" = 'Filter' or the
    # first available of Filter/Zoekfilter/Fase at read time).
    columns: list[str] = field(default_factory=list)
    filter_column: str = ""
    # Ruwe bladen per bron, sleutel 'objecttypen' of 'attributen' (leeg bij een in het geheugen opgebouwde spec).
    # Raw sheets per source, key 'objecttypen' or 'attributen' (empty for a spec built in memory).
    raw_sheets: dict[str, list[RawSheet]] = field(default_factory=dict)

    def filters(self) -> dict[str, list[ObjectType]]:
        """Objecttypen per filter (waarde in de gekozen filterkolom), in volgorde van voorkomen.
        Object types per filter (value in the chosen filter column), in order of appearance."""
        result: dict[str, list[ObjectType]] = {}
        for object_type in self.object_types:
            name = (object_type.value(self.filter_column) if self.filter_column else "") or object_type.filter
            if not name:
                continue
            members = result.setdefault(name, [])
            if all(o.name != object_type.name for o in members):
                members.append(object_type)
        return result

    def orphan_types(self) -> list[str]:
        """Objecttypen met attributen maar zonder regel in Objecttypen. / Object types with attributes but no row in
        Objecttypen."""
        known = {norm(o.name) for o in self.object_types}
        return sorted((n for n, attrs in self.attributes.items() if attrs and norm(n) not in known), key=str.casefold)

    @property
    def has_minimal_flags(self) -> bool:
        """Heeft minstens één attribuut een MinimaleDataset-waarde? / Does any attribute have a MinimaleDataset value?
        """
        return any(f.minimal is not None for attrs in self.flags.values() for f in attrs.values())

    def flag(self, *, object_type: str, attribute: str) -> AttributeFlags:
        """Vlaggen van een attribuut, of lege vlaggen als het niet bekend is.
        Flags of an attribute, or empty flags when it is unknown."""
        return self.flags.get(object_type, {}).get(norm(attribute), AttributeFlags())

    def resolve_filter_column(self, preferred: str = "") -> str:
        """Kolomnaam (zoals in het bestand) die als filter dient: ``preferred`` als die bestaat, anders de eerste
        van Filter/Zoekfilter/Fase. / Column name (as in the file) used as filter: ``preferred`` when it exists,
        otherwise the first of Filter/Zoekfilter/Fase."""
        by_key = {norm(c): c for c in self.columns}
        for key in (norm(preferred), *DEFAULT_FILTER_COLUMNS):
            if key in by_key:
                return by_key[key]
        return ""

    def merge(self, other: SpecModel) -> None:
        """Voeg een tweede specificatie toe (bijv. Wave 2 bovenop Wave 1); bestaande objecttypen blijven staan.
        Vlaggen (Opnemen/MinimaleDataset): bij een verschil wint de latere bron en er wordt gelogd; een attribuut
        dat daarna Opnemen=Ja heeft, verdwijnt uit ``excluded``. Dit is een bewuste wijziging t.o.v. de vereniging.
        Add a second specification (e.g. Wave 2 on top of Wave 1); existing object types are kept.
        Flags (Opnemen/MinimaleDataset): on a difference the later source wins and is logged; an attribute that then
        has Opnemen=Ja is removed from ``excluded``. A deliberate change compared with the plain union.
        """
        known = {(o.name, o.filter, o.values) for o in self.object_types}
        for object_type in other.object_types:
            if (object_type.name, object_type.filter, object_type.values) not in known:
                self.object_types.append(object_type)
        seen_columns = {norm(c) for c in self.columns}
        self.columns.extend(c for c in other.columns if norm(c) not in seen_columns)
        for name, attrs in other.attributes.items():
            target = self.attributes.setdefault(name, [])
            seen = {norm(a) for a in target}
            target.extend(a for a in attrs if norm(a) not in seen)
        for name, names in other.excluded.items():
            self.excluded.setdefault(name, set()).update(names)
        for name, attrs in other.flags.items():
            target_flags = self.flags.setdefault(name, {})
            for key, new_flags in attrs.items():
                old_flags = target_flags.get(key)
                if old_flags is not None and old_flags != new_flags:
                    log.warning(
                        "Conflicting flags for %s / %s: %s (%s) overridden by %s (%s)",
                        name, key, old_flags, ", ".join(self.sources), new_flags, ", ".join(other.sources),
                    )
                target_flags[key] = new_flags
                if new_flags.include:
                    self.excluded.get(name, set()).discard(key)
        self.sources.extend(s for s in other.sources if s not in self.sources)
        for key, sheets in other.raw_sheets.items():
            target_sheets = self.raw_sheets.setdefault(key, [])
            known_sources = {sheet.source for sheet in target_sheets}
            target_sheets.extend(sheet for sheet in sheets if sheet.source not in known_sources)


class SectionStyle(Enum):
    """Opmaaktype van een sectiekop. / Style type of a section heading."""

    PLAIN = "plain"
    SEMANTIC = "semantic"  # (Sem.rel) / (Sem.) -> zachtpaars / soft purple
    NOTES = "notes"


@dataclass(frozen=True)
class Cell:
    """Eén veld in het raster. / One field in the grid.

    label is de naam zonder voetnoot; footnote is het volgnummer (of None); annotation staat tussen haakjes in het
    Excel-ontwerp (bijv. de beheergroep); sample is voorbeeldtekst voor de mockup.
    label is the name without footnote; footnote is the sequence number (or None); annotation goes in brackets in
    the Excel design (e.g. the management group); sample is mockup preview text.
    """

    label: str
    footnote: int | None = None
    block: str = ""
    sample: str = ""
    annotation: str = ""

    @property
    def display(self) -> str:
        """Veldnaam zoals in de Excel-ontwerpbladen. / Field name as in the Excel design sheets."""
        if self.footnote:
            return f"{self.label} ({self.footnote})"
        return f"{self.label} ({self.annotation})" if self.annotation else self.label


Row = list[Cell]


@dataclass
class Section:
    """Sectie met raster; een lege rij (``[]``) is een witregel. ``margin`` bevat de opmerking naast een rij
    (rij-index -> tekst). / Section with grid; an empty row is a blank line. ``margin`` = remark beside a row."""

    title: str
    style: SectionStyle = SectionStyle.PLAIN
    rows: list[Row] = field(default_factory=list)
    repeater: bool = False  # herhaalbare voorbeeldrijen (Actoren, Memo) / repeatable sample rows
    margin: dict[int, str] = field(default_factory=dict)
    # Door de gebruiker toegevoegde sectie (Ontwerpblad, slepen en neerzetten) / section added by the user
    added: bool = False


@dataclass
class PassportTab:
    """Paspoorttabblad voor één filter. / Passport tab for one filter."""

    name: str
    group: str
    object_types: list[ObjectType]
    sections: list[Section] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    footnotes: dict[int, list[str]] = field(default_factory=dict)
    merged_from: list[str] = field(default_factory=list)  # oorspronkelijke filters / original filters
    data_gaps: list[str] = field(default_factory=list)  # objecttypen zonder attributen / types without attributes
    profile: DesignProfile = DEFAULT_PROFILE

    def applicable(self, label: str, object_type: str) -> bool:
        """Geldt het veld voor dit objecttype? (voetnoot-velden gelden voor een deel)
        Does the field apply to this object type? (footnoted fields apply to a subset)"""
        for section in self.sections:
            for row in section.rows:
                for cell in row:
                    if norm(cell.label) == norm(label) and cell.footnote:
                        return object_type in self.footnotes.get(cell.footnote, [])
        return True


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Issue:
    """Validatiemelding bij het genereren van de API-payload. / Validation issue while generating the API payload."""

    severity: Severity
    code: str
    message: str
