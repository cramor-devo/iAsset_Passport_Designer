"""Kern van de bulk-export van PNG's: welke bestanden komen waar, onder welke naam (geen Qt).
Core of the bulk PNG export: which files go where, under which name (no Qt)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\s]+')


def safe_filename(name: str) -> str:
    """Bestandsnaam zonder verboden tekens. / File name without forbidden characters."""
    return UNSAFE_FILENAME.sub("_", name).strip("_") or "passport"


@dataclass(frozen=True)
class ExportJob:
    """Eén af te beelden PNG: een heel paspoort (``object_type`` is None) of één objecttype van een paspoort.
    One PNG to write: a whole passport (``object_type`` is None) or one object type of a passport."""

    passport: str
    object_type: str | None
    path: Path

    @property
    def label(self) -> str:
        return self.object_type or self.passport


def _unique(folder: Path, stem: str, passport: str, taken: set[str]) -> Path:
    """Kies een vrije naam: ``stem``, dan ``stem (paspoort)``, dan ``stem (paspoort) (2)``…
    Pick a free name: ``stem``, then ``stem (passport)``, then ``stem (passport) (2)``…"""
    candidates = [stem, f"{stem} ({passport})"]
    for name in candidates:
        if name.casefold() not in taken:
            taken.add(name.casefold())
            return folder / f"{name}.png"
    counter = 2
    while f"{candidates[-1]} ({counter})".casefold() in taken:
        counter += 1
    name = f"{candidates[-1]} ({counter})"
    taken.add(name.casefold())
    return folder / f"{name}.png"


def plan_jobs(
    *, selection: Mapping[str, set[str | None]], tab_folder: Path | None, type_folder: Path | None,
) -> list[ExportJob]:
    """Maak de takenlijst. ``selection`` koppelt een paspoortnaam aan een set; ``None`` in die set is het paspoort
    zelf (``<tab>.png`` in ``tab_folder``), een tekst is een objecttype (``<type>.png`` in ``type_folder``). Bij een
    botsing komt het paspoort tussen haakjes erachter. Een ontbrekende map voor een gekozen soort geeft ValueError.
    Build the job list. ``selection`` maps a passport name to a set; ``None`` in the set is the passport itself
    (``<tab>.png`` in ``tab_folder``), a string is an object type (``<type>.png`` in ``type_folder``). On a
    collision the passport is appended in brackets. A missing folder for a selected kind raises ValueError."""
    wants_tabs = any(None in kinds for kinds in selection.values())
    wants_types = any(kind is not None for kinds in selection.values() for kind in kinds)
    if wants_tabs and tab_folder is None:
        raise ValueError("tab_folder is required")
    if wants_types and type_folder is None:
        raise ValueError("type_folder is required")
    taken: dict[Path, set[str]] = {}
    jobs: list[ExportJob] = []
    for passport, kinds in selection.items():
        ordered = sorted(kinds, key=lambda k: (k is not None, (k or "").casefold()))
        for kind in ordered:
            folder = tab_folder if kind is None else type_folder
            if folder is None:
                continue
            stem = safe_filename(passport if kind is None else kind)
            path = _unique(folder, stem, safe_filename(passport), taken.setdefault(folder, set()))
            jobs.append(ExportJob(passport, kind, path))
    return jobs


def existing(jobs: list[ExportJob]) -> list[ExportJob]:
    """De taken waarvan het bestand al bestaat. / The jobs whose file already exists."""
    return [job for job in jobs if job.path.exists()]
