"""Kruisverwijzing: vergelijkt een ingelezen (handmatig bijgewerkt) ontwerp met een vers gegenereerd ontwerp uit de
specificatie en meldt toegevoegde, verwijderde, verplaatste en hernoemde velden en velden die niet in de spec staan.
Cross-reference: compares an imported (manually refined) design with a freshly generated design from the
specification and reports added, removed, moved and renamed fields and fields that are not in the spec."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from .compare import ELLIPSIS_CHARS, clean_title
from .design_rules import SECTION_OBJECT
from .merge_advisor import merged_tab
from .models import PassportTab, SpecModel, norm
from .refined_import import RefinedWorkbook, split_label

if TYPE_CHECKING:
    from .layout_engine import LayoutEngine

ADDED, REMOVED, MOVED, RENAMED, NOT_IN_SPEC = "added", "removed", "moved", "renamed", "not-in-spec"
RENAME_RATIO = 0.85
# Voorrang bij markeren van één veldnaam met meerdere meldingen. / Precedence when one label has several entries.
PRECEDENCE = (RENAMED, NOT_IN_SPEC, MOVED, ADDED, REMOVED)


@dataclass(frozen=True)
class DiffEntry:
    """Eén verschil. ``label`` is de naam in het import-ontwerp (bij 'removed' de naam in het gegenereerde ontwerp);
    ``from_section`` is de sectie in het gegenereerde ontwerp, ``to_section`` die in het import-ontwerp;
    ``other_label`` is bij 'renamed' de oorspronkelijke (gegenereerde) naam.
    One difference. ``label`` is the name in the imported design (for 'removed' the name in the generated design);
    ``from_section`` is the section in the generated design, ``to_section`` the one in the imported design;
    ``other_label`` is the original (generated) name for 'renamed'."""

    label: str
    kind: str
    from_section: str = ""
    to_section: str = ""
    other_label: str = ""
    detail: str = ""


@dataclass
class TabDiff:
    """Verschillen voor één ontwerpblad. / Differences for one design sheet."""

    entries: list[DiffEntry] = field(default_factory=list)
    added_sections: list[str] = field(default_factory=list)
    removed_sections: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.entries or self.added_sections or self.removed_sections)

    def of_kind(self, kind: str) -> list[DiffEntry]:
        return [e for e in self.entries if e.kind == kind]


def label_key(label: str) -> str:
    """Genormaliseerde veldnaam: zonder voetnootnummer en sterretjes, hoofdletterongevoelig, spaties samengevoegd.
    Normalised field name: without footnote number and asterisks, case-insensitive, whitespace collapsed."""
    return norm(split_label(label)[0])


def _fields(tab: PassportTab) -> list[tuple[str, str, str]]:
    """(sectietitel, sleutel, weergavenaam) per veld in leesvolgorde, zonder weglatingstekens.
    (section title, key, display name) per field in reading order, without ellipsis cells."""
    result: list[tuple[str, str, str]] = []
    for section in tab.sections:
        title = clean_title(section.title)
        for row in section.rows:
            for cell in row:
                if not cell.label or set(cell.label) <= ELLIPSIS_CHARS:
                    continue
                display = f"{cell.label} ({cell.annotation})" if cell.annotation and not cell.footnote else cell.label
                result.append((title, label_key(display), display))
    return result


def _titles(tab: PassportTab) -> dict[str, str]:
    return {clean_title(s.title): s.title for s in tab.sections}


def _spec_attributes(tab: PassportTab, spec: SpecModel) -> set[str]:
    """Genormaliseerde attributen van de objecttypen van ``tab``; een objecttype zonder eigen attributen erft van het
    objecttype waarop de naam eindigt. Normalised attributes of the tab's object types; a type without own
    attributes inherits from the type its name ends with."""
    result: set[str] = set()
    for object_type in tab.object_types:
        source = object_type.name
        if not spec.attributes.get(source):
            name = norm(source)
            candidates = [
                c
                for c, attrs in spec.attributes.items()
                if attrs and c != source and len(c) >= 3 and name.endswith(norm(c))
            ]
            source = max(candidates, key=len, default=source)
        result.update(norm(a) for a in spec.attributes.get(source, []))
    return result


def diff_tab(imported: PassportTab, generated: PassportTab, spec: SpecModel | None = None) -> TabDiff:
    """Vergelijk een ingelezen ontwerp met het gegenereerde ontwerp. Verplaatst = in een andere sectie, of een andere
    volgorde binnen de sectie (LCS, zodat één invoeging niet alles erna markeert). Hernoemd = verwijderd + toegevoegd
    met gelijkenis >= 0,85. Niet-in-spec = veld in 'Object informatie' dat geen attribuut van de objecttypen is.
    Compare an imported design with the generated one. Moved = in another section, or another order within the
    section (LCS, so one insertion does not flag everything after it). Renamed = removed + added with similarity
    >= 0.85. Not-in-spec = field in 'Object informatie' that is not an attribute of the object types."""
    result = TabDiff()
    imp, gen = _fields(imported), _fields(generated)
    imp_sections: dict[str, set[str]] = {}
    gen_sections: dict[str, set[str]] = {}
    imp_names: dict[str, str] = {}
    gen_names: dict[str, str] = {}
    for title, key, display in imp:
        imp_sections.setdefault(key, set()).add(title)
        imp_names.setdefault(key, display)
    for title, key, display in gen:
        gen_sections.setdefault(key, set()).add(title)
        gen_names.setdefault(key, display)
    imp_titles, gen_titles = _titles(imported), _titles(generated)
    imp_first = {key: next(t for t, k, _ in imp if k == key) for key in imp_sections}
    gen_first = {key: next(t for t, k, _ in gen if k == key) for key in gen_sections}

    result.added_sections = [t for k, t in imp_titles.items() if k not in gen_titles]
    result.removed_sections = [t for k, t in gen_titles.items() if k not in imp_titles]

    added = [k for k in imp_sections if k not in gen_sections]
    removed = [k for k in gen_sections if k not in imp_sections]
    renamed: dict[str, str] = {}  # sleutel import -> sleutel gegenereerd / imported key -> generated key
    pairs = sorted(
        ((SequenceMatcher(None, a, r).ratio(), a, r) for a in added for r in removed), key=lambda p: -p[0],
    )
    used_removed: set[str] = set()
    for ratio, a, r in pairs:
        if ratio < RENAME_RATIO:
            break
        if a not in renamed and r not in used_removed:
            renamed[a] = r
            used_removed.add(r)

    entries = result.entries
    for key in added:
        section = imp_titles.get(imp_first[key], imp_first[key])
        if key in renamed:
            other = renamed[key]
            entries.append(DiffEntry(
                imp_names[key], RENAMED, gen_titles.get(gen_first[other], gen_first[other]), section,
                gen_names[other], f"'{gen_names[other]}' -> '{imp_names[key]}'",
            ))
        else:
            entries.append(DiffEntry(imp_names[key], ADDED, "", section))
    entries.extend(
        DiffEntry(gen_names[key], REMOVED, gen_titles.get(gen_first[key], gen_first[key]))
        for key in removed
        if key not in used_removed
    )
    entries.extend(_moved(imp, gen, imp_sections, gen_sections, imp_names, imp_titles, gen_titles))

    if spec is not None:
        allowed = _spec_attributes(imported, spec)
        object_section = clean_title(SECTION_OBJECT)
        if allowed:
            seen: set[str] = set()
            for title, key, display in imp:
                if title == object_section and key not in allowed and key not in seen:
                    seen.add(key)
                    entries.append(DiffEntry(display, NOT_IN_SPEC, "", imp_titles.get(title, title)))
    return result


def _moved(
    imp: list[tuple[str, str, str]], gen: list[tuple[str, str, str]], imp_sections: dict[str, set[str]],
    gen_sections: dict[str, set[str]], imp_names: dict[str, str], imp_titles: dict[str, str],
    gen_titles: dict[str, str],
) -> list[DiffEntry]:
    entries: list[DiffEntry] = []
    common = [k for k in imp_sections if k in gen_sections]
    stay = {k for k in common if imp_sections[k] & gen_sections[k]}
    for key in common:
        if key in stay:
            continue
        to_title = next(t for t, k, _ in imp if k == key)
        from_title = next(t for t, k, _ in gen if k == key)
        entries.append(DiffEntry(
            imp_names[key], MOVED, gen_titles.get(from_title, from_title), imp_titles.get(to_title, to_title),
            detail=f"{gen_titles.get(from_title, from_title)} -> {imp_titles.get(to_title, to_title)}",
        ))
    for title in dict.fromkeys(t for t, _, _ in gen):
        wanted = [k for t, k, _ in gen if t == title and k in stay and title in imp_sections[k]]
        found = [k for t, k, _ in imp if t == title and k in stay and title in gen_sections[k]]
        wanted, found = list(dict.fromkeys(wanted)), list(dict.fromkeys(found))
        matcher = SequenceMatcher(None, wanted, found, autojunk=False)
        kept: set[str] = set()
        for block in matcher.get_matching_blocks():
            kept.update(wanted[block.a : block.a + block.size])
        for key in found:
            if key not in kept:
                section = imp_titles.get(title, title)
                detail = f"position {wanted.index(key) + 1} -> {found.index(key) + 1}"
                entries.append(DiffEntry(imp_names[key], MOVED, section, section, detail=detail))
    return entries


def changed_labels(diff: TabDiff) -> dict[str, str]:
    """Genormaliseerde veldnaam -> soort verschil, voor markeren in het voorbeeld (voorrang: renamed, not-in-spec,
    moved, added, removed). Normalised label -> kind of difference, for highlighting in the preview."""
    result: dict[str, str] = {}
    for entry in diff.entries:
        key = label_key(entry.label)
        current = result.get(key)
        if current is None or PRECEDENCE.index(entry.kind) < PRECEDENCE.index(current):
            result[key] = entry.kind
    return result


def generated_for(sheet_tab: PassportTab, spec: SpecModel, engine: LayoutEngine) -> PassportTab:
    """Genereer het ontwerp dat bij een ingelezen blad hoort. Generate the design that belongs to an imported sheet."""
    types = list(sheet_tab.object_types)
    filters = spec.filters()
    if sheet_tab.merged_from and all(m in filters for m in sheet_tab.merged_from):
        merged = merged_tab(spec, engine, sheet_tab.merged_from, sheet_tab.name)
        if not types or {o.name for o in merged.object_types} == {o.name for o in types}:
            return merged
    return engine.build(sheet_tab.name, types, source_filters=sheet_tab.merged_from or None)


def diff_workbook(refined: RefinedWorkbook, spec: SpecModel, engine: LayoutEngine) -> list[tuple[str, TabDiff]]:
    """Verschillen per ingelezen blad (bladnaam, verschil). Differences per imported sheet (sheet name, diff)."""
    return [
        (sheet.name, diff_tab(sheet.tab, generated_for(sheet.tab, spec, engine), spec)) for sheet in refined.sheets
    ]
