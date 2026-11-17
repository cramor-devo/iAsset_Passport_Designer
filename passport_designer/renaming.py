"""Hernoemen van paspoorttabbladen: validatie en toepassen (zonder UI).
Renaming passport tabs: validation and applying (no UI).

NL: De naam van een tabblad is de sleutel voor markeringen, indelingen, exports en samenvoegingen. Een hernoeming
(oorspronkelijke naam -> eigen naam) leeft alleen in de sessie, net als samenvoegingen, en wordt na het samenvoegen
op de lijst met paspoorten toegepast.
EN: The name of a tab is the key for marks, layouts, exports and merges. A rename (original name -> custom name)
only lives in the session, like merges, and is applied after merging to the list of passports.
"""

from __future__ import annotations

from .excel_export import sheet_title
from .layout_engine import LayoutEngine
from .merge_advisor import validate_merge_name
from .models import PassportTab


def validate_rename(new_name: str, current: str, existing: set[str]) -> str | None:
    """Geef een i18n-sleutel met de fout, of None als ``new_name`` mag. De huidige naam (ook met andere
    hoofdletters) is toegestaan; een andere bestaande naam niet (hoofdletterongevoelig).
    Return an i18n key with the error, or None if ``new_name`` is allowed. The current name (also with other
    capitals) is allowed; another existing name is not (case-insensitive)."""
    others = {e for e in existing if e.casefold() != current.casefold()}
    return validate_merge_name(new_name, others)


def sheet_name_adjusted(name: str) -> bool:
    """Wordt de naam als Excel-tabbladnaam ingekort of aangepast (>31 tekens of []:*?/\\)?
    Is the name shortened or changed as an Excel sheet name (>31 chars or []:*?/\\)?"""
    stripped = name.strip()
    return bool(stripped) and sheet_title(stripped, set()) != stripped


def apply_renames(engine: LayoutEngine, tabs: list[PassportTab], renames: dict[str, str]) -> list[PassportTab]:
    """Geef ``tabs`` met de eigen namen; samengevoegde tabbladen blijven ongemoeid (hun naam zit in de samenvoeging).
    Een hernoemd tabblad wordt opnieuw opgebouwd en onthoudt zijn oorspronkelijke naam in ``original_name``.
    Return ``tabs`` with the custom names; merged tabs are left alone (their name lives in the merge). A renamed tab
    is rebuilt and remembers its original name in ``original_name``."""
    result: list[PassportTab] = []
    for tab in tabs:
        new = renames.get(tab.name)
        if new is None or tab.merged_from or new == tab.name:
            result.append(tab)
            continue
        renamed = engine.build(new, tab.object_types, source_filters=[tab.name])
        renamed.original_name = tab.name
        result.append(renamed)
    return result


def original_name(tab: PassportTab) -> str:
    """De oorspronkelijke (gegenereerde) naam van een tabblad. / The original (generated) name of a tab."""
    return tab.original_name or tab.name
