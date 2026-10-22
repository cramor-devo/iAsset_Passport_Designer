"""Bouwt per filter een paspoortontwerp (PassportTab) uit een SpecModel volgens een ontwerpprofiel.
Builds a passport design (PassportTab) per filter from a SpecModel according to a design profile."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .design_rules import (
    BLOCK_ORDER,
    SECTION_BASIS,
    SECTION_NOTES,
    SECTION_OBJECT,
    classify_block,
)
from .models import Cell, ObjectType, PassportTab, Row, Section, SectionStyle, SpecModel, norm
from .profiles import DEFAULT_PROFILE, ELLIPSIS, DesignProfile, FixedSection, RelationSection

SEMANTIC_SUFFIX = re.compile(r"\(sem\.\s*(rel)?\)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class LayoutOptions:
    """Opties voor het genereren. / Options for generation."""

    only_flagged: bool = True  # alleen attributen die in de bron niet op "Nee" staan / skip attributes marked "Nee"
    profile: DesignProfile = DEFAULT_PROFILE


def semantic_style(title: str) -> SectionStyle:
    """Kopjes met (Sem.rel), (Sem. rel) of (Sem.) krijgen de semantische kleur.
    Headings ending in (Sem.rel), (Sem. rel) or (Sem.) get the semantic colour."""
    return SectionStyle.SEMANTIC if SEMANTIC_SUFFIX.search(title.strip()) else SectionStyle.PLAIN


def chunk(cells: list[Cell], columns: int = 4) -> list[Row]:
    """Verdeel velden horizontaal over rijen van maximaal ``columns``. / Spread fields over rows of ``columns`` max."""
    return [cells[i : i + columns] for i in range(0, len(cells), columns)]


def _blank_after_rows(rows: list[Row], every: int) -> list[Row]:
    """Witregel na elke ``every`` rijen (niet aan het einde). / Blank row after every ``every`` rows (not last)."""
    result: list[Row] = []
    for index, row in enumerate(rows, start=1):
        result.append(row)
        if index % every == 0 and index < len(rows):
            result.append([])
    return result


def _blank_between(rows: list[Row]) -> list[Row]:
    """Witregel tussen elke twee rijen. / A blank row between every two rows."""
    result: list[Row] = []
    for index, row in enumerate(rows):
        if index:
            result.append([])
        result.append(row)
    return result


class LayoutEngine:
    """Zet een specificatie om in paspoortontwerpen. / Turns a specification into passport designs."""

    def __init__(self, spec: SpecModel, options: LayoutOptions | None = None) -> None:
        self.spec = spec
        self.options = options or LayoutOptions()

    @property
    def profile(self) -> DesignProfile:
        return self.options.profile

    def build_all(self) -> list[PassportTab]:
        return [self.build(name, types) for name, types in self.spec.filters().items()]

    def _source_type(self, object_type: str) -> str:
        """Objecttype zonder eigen attributen erft van het objecttype waarop de naam eindigt (Piramideblok -> Blok).
        An object type without own attributes inherits from the type its name ends with (Piramideblok -> Blok)."""
        if self.spec.attributes.get(object_type):
            return object_type
        name = norm(object_type)
        candidates = [
            c
            for c, attrs in self.spec.attributes.items()
            if attrs and c != object_type and len(c) >= 3 and name.endswith(norm(c))
        ]
        return max(candidates, key=len, default=object_type)

    def _attributes_of(self, object_type: str) -> list[str]:
        source = self._source_type(object_type)
        attributes = self.spec.attributes.get(source, [])
        if not self.options.only_flagged:
            return attributes
        excluded = self.spec.excluded.get(source, set())
        return [a for a in attributes if norm(a) not in excluded]

    def build(
        self, filter_name: str, object_types: list[ObjectType], source_filters: list[str] | None = None,
    ) -> PassportTab:
        profile = self.profile
        group = next((o.group for o in object_types if o.group), "")
        tab = PassportTab(name=filter_name, group=group, object_types=object_types, profile=profile)
        tab.sections.append(self._basis(filter_name, group))
        object_section, footnotes = self._object_information(object_types)
        tab.sections.append(object_section)
        tab.footnotes = footnotes
        tab.data_gaps = [o.name for o in object_types if not self._attributes_of(o.name)]
        present = {norm(a) for o in object_types for a in self._attributes_of(o.name)}
        sections = [self._fixed(fixed, present) for fixed in profile.after_object]
        relations = [self._relation(r) for r in profile.relations_for(source_filters or [filter_name])]
        # Relatiesecties staan vóór 'Actoren en rollen'. / Relation sections come before 'Actoren en rollen'.
        index = next((i for i, s in enumerate(profile.after_object) if s.repeater), len(sections))
        tab.sections.extend([*sections[:index], *relations, *sections[index:]])
        tab.notes = [f"({number}) Objecttype: {', '.join(names)}" for number, names in sorted(footnotes.items())]
        return tab

    # --- secties / sections ----------------------------------------------------------------------------------

    def _basis(self, filter_name: str, group: str) -> Section:
        profile = self.profile
        rows: list[Row] = []
        for labels in profile.basis_rows:
            row: Row = []
            for label in labels:
                key = norm(label)
                sample = ""
                annotation = ""
                if "imbor filter" in key:
                    sample = filter_name
                elif key.startswith("beheergroep"):
                    sample = group
                    annotation = group if profile.basis_group_annotation else ""
                elif key == "thema":
                    sample = group
                row.append(Cell(label, sample=sample, annotation=annotation))
            rows.append(row)
        section = Section(SECTION_BASIS, SectionStyle.PLAIN, rows)
        if profile.margin_notes and profile.basis_remark:
            section.margin[0] = profile.basis_remark
        return section

    def _spread(self, rows: list[Row], section: Section) -> None:
        """Voeg rijen toe met de witregels die het profiel voorschrijft. / Add rows with the profile's blank lines."""
        spaced = _blank_between(rows) if self.profile.blank_between_rows else rows
        section.rows.extend(spaced)

    def _fixed(self, fixed: FixedSection, present: set[str]) -> Section:
        rows: list[Row] = []
        for labels in fixed.rows:
            cells = [Cell(x) for x in labels if norm(x) not in fixed.optional or norm(x) in present]
            if cells:
                rows.append(cells)
        style = SectionStyle.PLAIN if fixed.grey else semantic_style(fixed.title)
        section = Section(fixed.title, style, [], repeater=fixed.repeater)
        if fixed.repeater and rows:
            section.rows = [rows[0] for _ in range(fixed.repeat)] + [[Cell(ELLIPSIS) for _ in rows[0]]]
        else:
            self._spread(rows, section)
        return section

    def _relation(self, relation: RelationSection) -> Section:
        rows: list[Row] = [[Cell(x) for x in labels] for labels in relation.rows]
        section = Section(relation.title, semantic_style(relation.title), [], repeater=relation.repeater)
        if relation.repeater and rows:
            section.rows = [rows[0] for _ in range(relation.repeat)] + [[Cell(ELLIPSIS) for _ in rows[0]]]
        else:
            self._spread(rows, section)
        for row_index, text in relation.remarks:
            section.margin[row_index] = text
        return section

    def attribute_sets(self, object_types: list[ObjectType]) -> tuple[dict[str, set[str]], dict[str, str]]:
        """Attributen (zonder vaste velden) per objecttype als genormaliseerde sleutels + weergavenamen.
        Attributes (excluding fixed fields) per object type as normalised keys + display names."""
        fixed = self.profile.fixed_names
        per_type: dict[str, set[str]] = {}
        display: dict[str, str] = {}
        for object_type in object_types:
            keys: set[str] = set()
            for attribute in self._attributes_of(object_type.name):
                key = norm(attribute)
                if key in fixed:
                    continue
                keys.add(key)
                display.setdefault(key, attribute)
            per_type[object_type.name] = keys
        return per_type, display

    def _object_information(self, object_types: list[ObjectType]) -> tuple[Section, dict[int, list[str]]]:
        profile = self.profile
        with_attributes = [o.name for o in object_types if self._attributes_of(o.name)]
        names = with_attributes or [o.name for o in object_types]
        per_type, display = self.attribute_sets(object_types)

        counts = Counter(key for keys in per_type.values() for key in keys)
        partial = sorted((k for k, n in counts.items() if n < len(names)), key=lambda k: display[k].casefold())
        footnote_numbers = {key: number for number, key in enumerate(partial, start=1)}
        footnotes = {footnote_numbers[key]: [n for n in names if key in per_type[n]] for key in partial}

        blocks: dict[str, list[Cell]] = {block: [] for block in BLOCK_ORDER}
        for key in sorted(counts, key=lambda k: display[k].casefold()):
            label = display[key]
            block = classify_block(label)
            blocks[block].append(Cell(label, footnote_numbers.get(key), block))

        section = Section(SECTION_OBJECT, SectionStyle.PLAIN)
        if profile.blank_between_rows:
            rows = [row for block in BLOCK_ORDER for row in chunk(blocks[block], profile.grid_columns)]
            section.rows = _blank_between(rows)
        else:
            for block in BLOCK_ORDER:
                cells = blocks[block]
                if not cells:
                    continue
                if section.rows:
                    section.rows.append([])
                section.rows.extend(_blank_after_rows(chunk(cells, profile.grid_columns), profile.rows_before_blank))
        if profile.margin_notes:
            for index, row in enumerate(section.rows):
                text = "; ".join(
                    f"({c.footnote}) Objecttype: {', '.join(footnotes[c.footnote])}" for c in row if c.footnote
                )
                if text:
                    section.margin[index] = text
        return section, footnotes


def notes_section(tab: PassportTab) -> Section | None:
    """Sectie 'Notities / Uitzonderingen' onderaan (alleen profielen zonder opmerkingen naast de rij).
    Notes section at the bottom (only for profiles without remarks beside the row)."""
    if tab.profile.margin_notes:
        return None
    notes = list(tab.notes)
    if tab.merged_from:
        notes.append(f"Samengevoegd uit filters: {', '.join(tab.merged_from)}")
    if not notes:
        return None
    return Section(SECTION_NOTES, SectionStyle.NOTES, [[Cell(note)] for note in notes])
