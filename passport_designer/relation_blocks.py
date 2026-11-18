"""Relatieblokken en hernoemde standaardblokken per paspoort; geen Qt.
Relation blocks and renamed standard blocks per passport; no Qt.

NL: Een relatieblok is een herhaalbare sectie waarvan het iAsset-relatietype (17-27) de gebruiker kiest. Het blok
hoort bij één paspoort (niet bij een filternaam), dus naamsbotsingen tussen waves kunnen niets lekken. De
standaardblokken (Gekoppelde objecten, Actoren en rollen, Inwinningsinformatie, Memo) kunnen per paspoort een
andere titel, andere kolomnamen en voorbeeldtekst krijgen; het relatietype (en dus de payload-id) blijft gelijk.
EN: A relation block is a repeatable section whose iAsset relation type (17-27) the user chooses. The block belongs
to one passport (not to a filter name), so name collisions between waves cannot leak anything. The standard blocks
(Gekoppelde objecten, Actoren en rollen, Inwinningsinformatie, Memo) can get another title, other column names and
sample text per passport; the relation type (and so the payload id) stays the same.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .models import Cell, PassportTab, Section, SectionStyle, norm
from .payload import ELEMENT_ACTORS, section_element

ELLIPSIS = "…"
# Relatietypen uit het paspoortsjabloon (17-23) en de extra typen die iAsset ook kent (24-27).
# Relation types from the passport template (17-23) and the extra types iAsset also knows (24-27).
TEMPLATE_RELATION_TYPES: dict[int, str] = {
    17: "Heeft deel", 18: "Is verbonden met", 19: "Is beschreven door", 20: "Bevat", 21: "Heeft begrenzing",
    22: "Voert uit", 23: "Bestaat uit",
}
EXTRA_RELATION_TYPES: dict[int, str] = {24: "Speelt", 25: "Heeft betrekking op", 26: "Beginpunt", 27: "Eindpunt"}
RELATION_TYPES: dict[int, str] = {**TEMPLATE_RELATION_TYPES, **EXTRA_RELATION_TYPES}
MAX_COLUMNS = 5  # zoals het raster van het profiel / like the profile grid
MAX_REPEAT = 5
DEFAULT_REPEAT = 2


@dataclass(frozen=True)
class RelationBlock:
    """Een door de gebruiker toegevoegd relatieblok. ``columns`` en ``samples`` lopen gelijk op (lege voorbeeldtekst
    = geen). A relation block added by the user. ``columns`` and ``samples`` run in parallel (empty sample = none)."""

    title: str
    element: int  # iAsset-relatietype 17-27 / iAsset relation type 17-27
    columns: tuple[str, ...] = ("Nummer", "Objecttype")
    samples: tuple[str, ...] = ()
    repeat: int = DEFAULT_REPEAT


@dataclass(frozen=True)
class BlockEdit:
    """Wijziging van een standaardblok: nieuwe titel (leeg = ongewijzigd), kolomnamen en voorbeeldtekst per kolom
    (lege waarde = ongewijzigd). Change of a standard block: new title (empty = unchanged), column names and sample
    text per column (empty value = unchanged)."""

    title: str = ""
    labels: tuple[str, ...] = ()
    samples: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.title.strip() and not any(x.strip() for x in (*self.labels, *self.samples))


def block_title_error(title: str, existing: set[str], current: str = "") -> str | None:
    """i18n-sleutel van de fout in een bloktitel, of None. Hergebruikt de hernoemregels van paspoorten (niet leeg,
    maximaal 50 tekens, uniek binnen het paspoort, hoofdletterongevoelig).
    i18n key of the error in a block title, or None. Reuses the passport rename rules (non-empty, at most 50
    characters, unique within the passport, case-insensitive)."""
    from .renaming import validate_rename  # lokaal: renaming importeert de engine / local: renaming imports the engine

    return validate_rename(title, current, existing)


def _clean(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(" ".join(v.split()) for v in values)


def normalised_block(block: RelationBlock) -> RelationBlock:
    """Schoon opgemaakt blok: lege kolommen weg, maximaal ``MAX_COLUMNS`` kolommen, herhalingen 1..``MAX_REPEAT``.
    Tidied block: empty columns dropped, at most ``MAX_COLUMNS`` columns, repeat 1..``MAX_REPEAT``."""
    columns = _clean(block.columns)
    samples = _clean(block.samples) + ("",) * max(0, len(columns) - len(block.samples))
    pairs = [(c, s) for c, s in zip(columns, samples, strict=False) if c][:MAX_COLUMNS]
    return replace(
        block, title=" ".join(block.title.split()), columns=tuple(c for c, _ in pairs),
        samples=tuple(s for _, s in pairs) if any(s for _, s in pairs) else (),
        repeat=max(1, min(block.repeat, MAX_REPEAT)),
    )


def _template_row(section: Section) -> list[Cell]:
    return next((r for r in section.rows if r and not all(set(c.label) <= {ELLIPSIS} for c in r)), [])


def standard_columns(section: Section) -> list[Cell]:
    """De kolommen (voorbeeldrij) van een herhaalbaar standaardblok. / The columns (sample row) of a repeatable
    standard block."""
    return _template_row(section)


def _block_section(block: RelationBlock) -> Section:
    cells = [
        Cell(label, sample=block.samples[i] if i < len(block.samples) else "")
        for i, label in enumerate(block.columns)
    ]
    rows = [list(cells) for _ in range(block.repeat)] + [[Cell(ELLIPSIS) for _ in cells]]
    return Section(block.title, SectionStyle.SEMANTIC, rows, repeater=True, element=block.element)


def _edit_section(section: Section, edit: BlockEdit, profile_element: int) -> Section:
    def pick(values: tuple[str, ...], index: int) -> str:
        return values[index].strip() if index < len(values) else ""

    rows: list[list[Cell]] = []
    for row in section.rows:
        if row and all(set(c.label) <= {ELLIPSIS} for c in row):
            rows.append(list(row))  # '…'-rij blijft / the '…' row stays
            continue
        rows.append([
            replace(c, label=pick(edit.labels, i) or c.label, sample=pick(edit.samples, i) or c.sample)
            for i, c in enumerate(row)
        ])
    return replace(section, title=" ".join(edit.title.split()) or section.title, rows=rows, element=profile_element)


def apply_blocks(
    tab: PassportTab, blocks: tuple[RelationBlock, ...], edits: tuple[tuple[str, BlockEdit], ...],
) -> PassportTab:
    """Kopie van ``tab`` met de hernoemde standaardblokken en de relatieblokken (vóór 'Actoren en rollen').
    ``edits``: (genormaliseerde gegenereerde titel, wijziging). Het relatietype van een hernoemd blok blijft dat van
    het oorspronkelijke blok. Copy of ``tab`` with the renamed standard blocks and the relation blocks (before
    'Actoren en rollen'). ``edits``: (normalised generated title, change). The relation type of a renamed block
    stays that of the original block."""
    if not blocks and not edits:
        return tab
    wanted = dict(edits)
    sections: list[Section] = []
    for section in tab.sections:
        edit = wanted.get(norm(section.title))
        if edit is not None and section.repeater and not edit.is_empty:
            section = _edit_section(section, edit, section.element or section_element(section, tab.profile))
        sections.append(section)
    if blocks:
        index = next(
            (i for i, s in enumerate(sections) if s.repeater and (s.element or section_element(s)) == ELEMENT_ACTORS),
            None,
        )
        if index is None:
            index = next((i for i, s in enumerate(sections) if s.style is SectionStyle.NOTES), len(sections))
        sections[index:index] = [_block_section(normalised_block(b)) for b in blocks]
    return replace(tab, sections=sections)
