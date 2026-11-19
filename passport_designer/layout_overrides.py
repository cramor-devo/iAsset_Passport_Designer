"""Handmatige aanpassingen per paspoort: velden markeren ('controleren met klant') of verwijderen; geen Qt.
Manual adjustments per passport: mark fields ('verify with customer') or delete them; no Qt."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, replace

from .models import Cell, PassportTab, Section, SectionStyle, norm
from .relation_blocks import (
    RELATION_TYPES,
    BlockEdit,
    RelationBlock,
    apply_blocks,
    block_title_error,
    normalised_block,
)

MAX_SECTION_TITLE = 60  # tekens in een nieuwe sectietitel / characters in a new section title
LAYOUT_VERSION = 1


class LayoutRefused(Exception):
    """Een indelingswijziging die niet mag; ``code`` is het i18n-achtervoegsel (``layout.<code>``).
    A layout change that is not allowed; ``code`` is the i18n suffix (``layout.<code>``)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class LayoutFileError(Exception):
    """Een indelingsbestand dat niet te lezen is; ``str(error)`` is de melding voor de gebruiker.
    A layout file that cannot be read; ``str(error)`` is the user message."""


@dataclass(frozen=True)
class CellRef:
    """Positie in een PassportTab; ``row`` -1 = de sectiekop, ``col`` mag voorbij het einde van de rij wijzen.
    Position in a PassportTab; ``row`` -1 = the section heading, ``col`` may point past the end of the row."""

    section: int
    row: int
    col: int


@dataclass(frozen=True)
class RowLayout:
    """Eén rij: genormaliseerde veldnamen (leeg = witregel) en de opmerking ernaast.
    One row: normalised field names (empty = blank row) and the remark beside it."""

    keys: tuple[str, ...] = ()
    margin: str = ""


@dataclass(frozen=True)
class SectionLayout:
    """Eén sectie van de gebruikersindeling. ``fixed`` (herhaalbaar/notities): alleen als geheel te verplaatsen.
    One section of the user layout. ``fixed`` (repeatable/notes): can only move as a whole."""

    title: str
    style: SectionStyle = SectionStyle.PLAIN
    rows: tuple[RowLayout, ...] = ()
    added: bool = False
    fixed: bool = False


@dataclass(frozen=True)
class TabOverride:
    """Gemarkeerde en verwijderde velden en de indeling van één paspoort (genormaliseerde veldnamen). ``layout`` is
    None zolang de gegenereerde volgorde geldt; ``known`` zijn alle velden die de indeling kent (ook verwijderde).
    Marked and deleted fields and the layout of one passport (normalised field names). ``layout`` is None while the
    generated order applies; ``known`` are all fields the layout knows about (deleted ones too)."""

    verify: frozenset[str] = frozenset()
    deleted: frozenset[str] = frozenset()
    layout: tuple[SectionLayout, ...] | None = None
    known: frozenset[str] = frozenset()
    # Relatieblokken en hernoemde standaardblokken (zie relation_blocks) / relation blocks and renamed standard blocks
    blocks: tuple[RelationBlock, ...] = ()
    block_edits: tuple[tuple[str, BlockEdit], ...] = ()

    @property
    def is_empty(self) -> bool:
        return (
            not self.verify and not self.deleted and self.layout is None and not self.blocks and not self.block_edits
        )


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


def apply_override(
    tab: PassportTab, override: TabOverride, *, keep_empty: bool = False,
) -> tuple[PassportTab, set[str]]:
    """Kopie van ``tab`` met de gebruikersindeling en zonder de verwijderde velden (rijen sluiten op, lege rijen en
    secties verdwijnen), plus de gemarkeerde veldnamen die erin voorkomen. Velden in herhaalbare secties blijven
    staan. ``keep_empty``: laat lege secties staan (om erin te kunnen slepen).
    Copy of ``tab`` with the user layout and without the deleted fields (rows close up, empty rows and sections
    disappear), plus the marked field names that occur in it. Fields in repeatable sections stay. ``keep_empty``:
    keep empty sections (so that fields can be dragged into them)."""
    tab = apply_blocks(tab, override.blocks, override.block_edits)
    if override.layout is not None:
        tab = apply_layout(tab, override, keep_empty=keep_empty)[0]
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


# --- indeling: vastleggen en toepassen / layout: capture and apply ---------------------------------------------


def capture(tab: PassportTab) -> tuple[SectionLayout, ...]:
    """Leg de huidige indeling van ``tab`` vast (herhaalbare en notitiesecties als vaste blokken).
    Capture the current layout of ``tab`` (repeatable and notes sections as fixed blocks)."""
    result: list[SectionLayout] = []
    for section in tab.sections:
        if _is_protected(section):
            result.append(SectionLayout(section.title, section.style, fixed=True, added=section.added))
            continue
        rows = tuple(
            RowLayout(tuple(norm(c.label) for c in row), section.margin.get(index, ""))
            for index, row in enumerate(section.rows)
        )
        result.append(SectionLayout(section.title, section.style, rows, added=section.added))
    return tuple(result)


def with_capture(override: TabOverride, displayed: PassportTab) -> TabOverride:
    """Zet de indeling van het getoonde paspoort in ``override`` en onthoud alle bekende velden.
    Put the layout of the displayed passport into ``override`` and remember all known fields."""
    known = override.known | override.deleted | frozenset(tab_labels(displayed))
    return replace(override, layout=capture(displayed), known=known)


def _place_leftover(sections: list[Section], origin: str, cell: Cell, columns: int) -> None:
    """Voeg een nieuw/hersteld veld achteraan zijn oorspronkelijke sectie toe. / Append a new/restored field to the
    end of its original section."""
    free = [s for s in sections if not _is_protected(s)]
    target = next((s for s in free if s.title == origin), free[-1] if free else None)
    if target is None:
        target = Section(origin)
        sections.append(target)
    if target.rows and target.rows[-1] and len(target.rows[-1]) < columns:
        target.rows[-1].append(cell)
    else:
        target.rows.append([cell])


def apply_layout(
    tab: PassportTab, override: TabOverride, *, keep_empty: bool = False,
) -> tuple[PassportTab, list[str], list[str]]:
    """Pas de indeling toe: (nieuw paspoort, waarschuwingen, info). Velden die niet meer bestaan worden weggelaten
    (waarschuwing); nieuwe velden komen achteraan hun sectie (info). Voetnoten worden opnieuw genummerd.
    Apply the layout: (new passport, warnings, info). Fields that no longer exist are dropped (warning); new fields
    go to the end of their section (info). Footnotes are renumbered."""
    layout = override.layout
    if layout is None:
        return tab, [], []
    columns = tab.profile.grid_columns
    pool: dict[str, list[Cell]] = {}
    origin: dict[str, str] = {}
    order: list[str] = []
    fixed_pool: list[Section] = []
    for section in tab.sections:
        if _is_protected(section):
            fixed_pool.append(section)
            continue
        for row in section.rows:
            for cell in row:
                key = norm(cell.label)
                pool.setdefault(key, []).append(cell)
                origin.setdefault(key, section.title)
                order.append(key)
    warnings: list[str] = []
    sections: list[Section] = []
    for planned in layout:
        if planned.fixed:
            match = next((s for s in fixed_pool if s.title == planned.title), None)
            if match is not None:
                fixed_pool.remove(match)
                sections.append(match)
            continue
        rows: list[list[Cell]] = []
        margin: dict[int, str] = {}
        for row_layout in planned.rows:
            if not row_layout.keys:
                rows.append([])
                continue
            cells: list[Cell] = []
            for key in row_layout.keys:
                if pool.get(key):
                    cells.append(pool[key].pop(0))
                else:
                    warnings.append(f'Layout: field "{key}" no longer in specification')
            if cells:
                if row_layout.margin:
                    margin[len(rows)] = row_layout.margin
                rows.append(cells)
        had_keys = any(r.keys for r in planned.rows)
        if not keep_empty and not any(rows) and (planned.added or had_keys):
            continue
        sections.append(Section(planned.title, planned.style, rows, margin=margin, added=planned.added))
    infos: list[str] = []
    for key in order:
        if pool.get(key):
            cell = pool[key].pop(0)
            _place_leftover(sections, origin[key], cell, columns)
            if key not in override.known:
                infos.append(f'Layout: new field "{cell.label}" added at the end of "{origin[key]}"')
    sections.extend(fixed_pool)  # onbekende vaste secties blijven staan / unknown fixed sections stay
    return renumber_footnotes(replace(tab, sections=sections)), sorted(set(warnings)), infos


def renumber_footnotes(tab: PassportTab) -> PassportTab:
    """Nummer de voetnoten opnieuw in leesvolgorde; de tabel met voetnoten volgt. / Renumber the footnotes in
    reading order; the footnote table follows."""
    mapping: dict[int, int] = {}
    for section in tab.sections:
        for row in section.rows:
            for cell in row:
                if cell.footnote and cell.footnote not in mapping:
                    mapping[cell.footnote] = len(mapping) + 1
    if all(old == new for old, new in mapping.items()):
        return tab
    sections = [
        replace(s, rows=[[replace(c, footnote=mapping[c.footnote]) if c.footnote else c for c in r] for r in s.rows])
        for s in tab.sections
    ]
    footnotes = {mapping[n]: names for n, names in tab.footnotes.items() if n in mapping}
    return replace(tab, sections=sections, footnotes=dict(sorted(footnotes.items())))


# --- indeling: bewerkingen (zuivere functies) / layout: edits (pure functions) ----------------------------------


def _layout(override: TabOverride) -> list[list[RowLayout]]:
    if override.layout is None:
        raise LayoutRefused("invalid")
    return [list(s.rows) for s in override.layout]


def _commit(override: TabOverride, rows: list[list[RowLayout]]) -> TabOverride:
    assert override.layout is not None
    sections = tuple(replace(s, rows=tuple(r)) for s, r in zip(override.layout, rows, strict=True))
    return replace(override, layout=sections)


def _editable(override: TabOverride, index: int) -> SectionLayout:
    if override.layout is None or not 0 <= index < len(override.layout):
        raise LayoutRefused("invalid")
    section = override.layout[index]
    if section.fixed:
        raise LayoutRefused("locked")
    return section


def move_cell(override: TabOverride, *, source: CellRef, target: CellRef, max_columns: int) -> TabOverride:
    """Verplaats een veld (invoegen vóór het doelveld). Weigert vaste secties en een volle rij.
    Move a field (insert before the target field). Refuses fixed sections and a full row."""
    _editable(override, source.section)
    _editable(override, target.section)
    rows = _layout(override)
    if not 0 <= source.row < len(rows[source.section]) or not (
        0 <= source.col < len(rows[source.section][source.row].keys)
    ):
        raise LayoutRefused("invalid")
    origin = rows[source.section][source.row]
    key = origin.keys[source.col]
    remaining = origin.keys[: source.col] + origin.keys[source.col + 1:]
    emptied = not remaining
    if emptied:
        del rows[source.section][source.row]
    else:
        rows[source.section][source.row] = RowLayout(remaining, origin.margin)
    t_sec, t_row, t_col = target.section, target.row, target.col
    if t_row == -1:  # sectiekop: achteraan de sectie / heading: at the end of the section
        last = rows[t_sec][-1] if rows[t_sec] else None
        if last is not None and last.keys and len(last.keys) < max_columns:
            rows[t_sec][-1] = RowLayout((*last.keys, key), last.margin)
        else:
            rows[t_sec].append(RowLayout((key,)))
        return _commit(override, rows)
    if emptied and t_sec == source.section:
        if t_row == source.row:
            return override  # op zichzelf neergezet / dropped on itself
        if t_row > source.row:
            t_row -= 1
    if not 0 <= t_row < len(rows[t_sec]):
        raise LayoutRefused("invalid")
    same_row = t_sec == source.section and t_row == source.row
    row = rows[t_sec][t_row]
    if same_row and t_col > source.col:
        t_col -= 1
    if not same_row and len(row.keys) >= max_columns:
        raise LayoutRefused("full")
    t_col = max(0, min(t_col, len(row.keys)))
    rows[t_sec][t_row] = RowLayout((*row.keys[:t_col], key, *row.keys[t_col:]), row.margin)
    return _commit(override, rows)


def insert_row(override: TabOverride, *, section: int, row: int) -> TabOverride:
    """Voeg een lege rij in op positie ``row``. / Insert an empty row at position ``row``."""
    _editable(override, section)
    rows = _layout(override)
    rows[section].insert(max(0, min(row, len(rows[section]))), RowLayout())
    return _commit(override, rows)


def delete_empty_row(override: TabOverride, *, section: int, row: int) -> TabOverride:
    """Verwijder een lege rij; een rij met velden niet. / Delete an empty row; a row with fields is refused."""
    _editable(override, section)
    rows = _layout(override)
    if not 0 <= row < len(rows[section]) or rows[section][row].keys:
        raise LayoutRefused("not_empty")
    del rows[section][row]
    return _commit(override, rows)


def _clean_title(title: str) -> str:
    title = " ".join(title.split())
    if not title or len(title) > MAX_SECTION_TITLE:
        raise LayoutRefused("title")
    return title


def add_section(override: TabOverride, *, after: int, title: str, style: SectionStyle) -> TabOverride:
    """Nieuwe, lege sectie onder sectie ``after``. / New empty section below section ``after``."""
    if override.layout is None:
        raise LayoutRefused("invalid")
    new = SectionLayout(_clean_title(title), style, added=True)
    at = max(0, min(after + 1, len(override.layout)))
    return replace(override, layout=(*override.layout[:at], new, *override.layout[at:]))


def rename_section(
    override: TabOverride, *, section: int, title: str, style: SectionStyle | None = None,
) -> TabOverride:
    """Hernoem een sectie (en wijzig desgewenst de stijl). / Rename a section (and optionally change the style)."""
    current = _editable(override, section)
    assert override.layout is not None
    changed = replace(current, title=_clean_title(title), style=style or current.style)
    return replace(override, layout=(*override.layout[:section], changed, *override.layout[section + 1:]))


def reset_layout(override: TabOverride) -> TabOverride:
    """Terug naar de gegenereerde volgorde; markeringen en verwijderingen blijven. / Back to the generated order;
    marks and deletions stay."""
    return replace(override, layout=None, known=frozenset())


# --- relatieblokken en hernoemde standaardblokken / relation blocks and renamed standard blocks ----------------


def _retitle_layout(override: TabOverride, old: str, new: str) -> TabOverride:
    """Zet de titel van een vast blok ook in de bewaarde indeling om, zodat het zijn plek behoudt.
    Also rename a fixed block in the stored layout so that it keeps its place."""
    if override.layout is None or old == new:
        return override
    layout = tuple(replace(s, title=new) if s.fixed and s.title == old else s for s in override.layout)
    return replace(override, layout=layout)


def _checked_block(block: RelationBlock, existing: set[str], current: str = "") -> RelationBlock:
    block = normalised_block(block)
    if block.element not in RELATION_TYPES or not block.columns:
        raise LayoutRefused("invalid")
    if block_title_error(block.title, existing, current):
        raise LayoutRefused("title")
    return block


def add_block(override: TabOverride, *, block: RelationBlock, existing_titles: set[str]) -> TabOverride:
    """Voeg een relatieblok toe aan dit paspoort. ``existing_titles``: de titels die het paspoort nu toont.
    Add a relation block to this passport. ``existing_titles``: the titles the passport shows now."""
    block = _checked_block(block, existing_titles)
    result = replace(override, blocks=(*override.blocks, block))
    if result.layout is not None:
        # Ook een hernoemd 'Actoren en rollen' (via block_edits) is het ankerblok. / A renamed 'Actoren en rollen'
        # (via block_edits) is the anchor block too.
        renamed = {norm(e.title) for k, e in result.block_edits if k.startswith("actoren en rollen") and e.title}
        at = next(
            (
                i for i, s in enumerate(result.layout)
                if s.fixed and (norm(s.title).startswith("actoren en rollen") or norm(s.title) in renamed)
            ),
            next((i for i, s in enumerate(result.layout) if s.style is SectionStyle.NOTES), len(result.layout)),
        )
        entry = SectionLayout(block.title, SectionStyle.SEMANTIC, fixed=True)
        result = replace(result, layout=(*result.layout[:at], entry, *result.layout[at:]))
    return result


def update_block(
    override: TabOverride, *, index: int, block: RelationBlock, existing_titles: set[str],
) -> TabOverride:
    """Wijzig relatieblok ``index`` (titel, type, kolommen, voorbeeldtekst). / Change relation block ``index``."""
    if not 0 <= index < len(override.blocks):
        raise LayoutRefused("invalid")
    old = override.blocks[index]
    block = _checked_block(block, existing_titles, current=old.title)
    blocks = (*override.blocks[:index], block, *override.blocks[index + 1:])
    return _retitle_layout(replace(override, blocks=blocks), old.title, block.title)


def delete_block(override: TabOverride, *, index: int) -> TabOverride:
    """Verwijder relatieblok ``index`` (ook uit de bewaarde indeling). / Delete relation block ``index`` (also from
    the stored layout)."""
    if not 0 <= index < len(override.blocks):
        raise LayoutRefused("invalid")
    gone = override.blocks[index]
    result = replace(override, blocks=(*override.blocks[:index], *override.blocks[index + 1:]))
    if result.layout is not None:
        layout = tuple(s for s in result.layout if not (s.fixed and s.title == gone.title))
        result = replace(result, layout=layout)
    return result


def move_block(override: TabOverride, *, index: int, delta: int) -> TabOverride:
    """Verplaats relatieblok ``index`` ``delta`` plaatsen (-1 omhoog, 1 omlaag) t.o.v. de andere relatieblokken.
    Move relation block ``index`` by ``delta`` places (-1 up, 1 down) relative to the other relation blocks."""
    target = index + delta
    if not (0 <= index < len(override.blocks) and 0 <= target < len(override.blocks)):
        raise LayoutRefused("invalid")
    blocks = list(override.blocks)
    blocks[index], blocks[target] = blocks[target], blocks[index]
    result = replace(override, blocks=tuple(blocks))
    if result.layout is not None:
        layout = list(result.layout)
        spots = {s.title: i for i, s in enumerate(layout) if s.fixed}
        a, b = spots.get(override.blocks[index].title), spots.get(override.blocks[target].title)
        if a is not None and b is not None:
            layout[a], layout[b] = layout[b], layout[a]
            result = replace(result, layout=tuple(layout))
    return result


def block_edit_of(override: TabOverride, original_title: str) -> BlockEdit | None:
    """De wijziging van het standaardblok met deze gegenereerde titel. / The change of the standard block with this
    generated title."""
    return dict(override.block_edits).get(norm(original_title))


def set_block_edit(
    override: TabOverride, *, original_title: str, edit: BlockEdit, existing_titles: set[str],
) -> TabOverride:
    """Hernoem een standaardblok (titel, kolomnamen, voorbeeldtekst); een lege wijziging herstelt het standaardblok.
    Rename a standard block (title, column names, sample text); an empty change restores the standard block."""
    previous = block_edit_of(override, original_title)
    shown = (previous.title.strip() if previous else "") or original_title
    clean = BlockEdit(
        " ".join(edit.title.split()), tuple(" ".join(x.split()) for x in edit.labels),
        tuple(" ".join(x.split()) for x in edit.samples),
    )
    if clean.is_empty:
        return reset_block_edit(override, original_title=original_title, existing_titles=existing_titles)
    if clean.title and block_title_error(clean.title, existing_titles, current=shown):
        raise LayoutRefused("title")
    key = norm(original_title)
    kept = tuple((k, e) for k, e in override.block_edits if k != key)
    result = replace(override, block_edits=(*kept, (key, clean)))
    return _retitle_layout(result, shown, clean.title or original_title)


def reset_block_edit(
    override: TabOverride, *, original_title: str, existing_titles: set[str] | None = None,
) -> TabOverride:
    """Zet een standaardblok terug naar de standaard. Met ``existing_titles`` wordt de teruggezette titel gecontroleerd
    (``LayoutRefused("title")`` bij een dubbele titel). Put a standard block back to the standard. With
    ``existing_titles`` the restored title is validated (``LayoutRefused("title")`` on a duplicate)."""
    previous = block_edit_of(override, original_title)
    if previous is None:
        return override
    if existing_titles is not None and previous.title.strip() and block_title_error(
        original_title, existing_titles, current=previous.title.strip(),
    ):
        raise LayoutRefused("title")
    key = norm(original_title)
    result = replace(override, block_edits=tuple((k, e) for k, e in override.block_edits if k != key))
    return _retitle_layout(result, previous.title or original_title, original_title)


# --- bestand en opslag / file and storage -----------------------------------------------------------------------


def override_to_dict(override: TabOverride) -> dict[str, object]:
    """JSON-vriendelijke weergave van één paspoort. / JSON-friendly form of one passport."""
    data: dict[str, object] = {"verify": sorted(override.verify), "deleted": sorted(override.deleted)}
    if override.blocks:
        data["blocks"] = [
            {"title": b.title, "element": b.element, "columns": list(b.columns), "samples": list(b.samples),
             "repeat": b.repeat}
            for b in override.blocks
        ]
    if override.block_edits:
        data["block_edits"] = {
            key: {"title": e.title, "labels": list(e.labels), "samples": list(e.samples)}
            for key, e in override.block_edits
        }
    if override.layout is not None:
        data["known"] = sorted(override.known)
        data["layout"] = [
            {
                "title": s.title, "style": s.style.value, "added": s.added, "fixed": s.fixed,
                "rows": [{"keys": list(r.keys), "margin": r.margin} for r in s.rows],
            }
            for s in override.layout
        ]
    return data


def override_from_dict(data: object) -> TabOverride:
    """Omgekeerde van ``override_to_dict``; ``LayoutFileError`` bij onbruikbare gegevens. / Inverse of
    ``override_to_dict``; ``LayoutFileError`` for unusable data."""
    try:
        assert isinstance(data, dict)
        layout: tuple[SectionLayout, ...] | None = None
        raw = data.get("layout")
        if raw is not None:
            layout = tuple(
                SectionLayout(
                    str(s["title"]), SectionStyle(s.get("style", "plain")),
                    tuple(RowLayout(tuple(str(k) for k in r["keys"]), str(r.get("margin", ""))) for r in s["rows"]),
                    bool(s.get("added", False)), bool(s.get("fixed", False)),
                )
                for s in raw
            )
        blocks = tuple(
            normalised_block(RelationBlock(
                str(b["title"]), int(b["element"]), tuple(str(c) for c in b.get("columns", [])),
                tuple(str(s) for s in b.get("samples", [])), int(b.get("repeat", 2)),
            ))
            for b in data.get("blocks", [])
        )
        if any(b.element not in RELATION_TYPES or not b.columns for b in blocks):
            raise ValueError("relation block")
        block_edits = tuple(
            (str(key), BlockEdit(
                str(e.get("title", "")), tuple(str(x) for x in e.get("labels", [])),
                tuple(str(x) for x in e.get("samples", [])),
            ))
            for key, e in dict(data.get("block_edits", {})).items()
        )
        return TabOverride(
            frozenset(str(v) for v in data.get("verify", [])), frozenset(str(v) for v in data.get("deleted", [])),
            layout, frozenset(str(v) for v in data.get("known", [])), blocks, block_edits,
        )
    except (AssertionError, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise LayoutFileError("The layout data is not valid.") from exc


def to_json(overrides: dict[str, TabOverride]) -> str:
    """Bestandsvorm: ``{"version": 1, "tabs": {sleutel: ...}}``. / File form."""
    body = {key: override_to_dict(o) for key, o in sorted(overrides.items()) if not o.is_empty}
    return json.dumps({"version": LAYOUT_VERSION, "tabs": body}, ensure_ascii=False, indent=1)


def from_json(text: str) -> dict[str, TabOverride]:
    """Lees een indelingsbestand; ``LayoutFileError`` met een leesbare melding bij een fout. / Read a layout file;
    ``LayoutFileError`` with a readable message on error."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise LayoutFileError("The layout file is not valid JSON.") from exc
    if not isinstance(data, dict) or data.get("version") != LAYOUT_VERSION or not isinstance(data.get("tabs"), dict):
        raise LayoutFileError("The layout file has an unknown format or version.")
    return {str(key): override_from_dict(value) for key, value in data["tabs"].items()}
