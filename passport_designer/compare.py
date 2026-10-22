"""Vergelijkt gegenereerde paspoortontwerpen met een handmatig bijgewerkt Excel-bestand.
Compares generated passport designs with a manually tuned Excel workbook.

Gebruik / Usage:
    python -m passport_designer.compare --spec wave1.xlsx --manual handmatig.xlsx [--profile rotterdam_v3]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .layout_engine import LayoutEngine, LayoutOptions
from .merge_advisor import merged_tab
from .models import PassportTab, norm
from .profiles import DEFAULT_PROFILE, PROFILES
from .spec_reader import read_spec

MARGIN_COLUMN = 6  # kolom G en verder = opmerkingen / column G onwards = remarks
ELLIPSIS_CHARS = set("&.…")
SUFFIX = re.compile(r"\s*(\(\d+\)|\*+)$")
SEM_SPACE = re.compile(r"\(sem\.\s*rel\)", re.IGNORECASE)
FOOTNOTE_LINE = re.compile(r"^(\(\d+\)\s*Objecttype|\*)")

# Tabblad in het handmatige bestand -> filters. / Sheet in the manual file -> filters.
ROTTERDAM_V3_SHEETS: dict[str, list[str]] = {
    "Beheerzone": ["Beheerzone"],
    "Verharding": ["Verharding"],
    "Constructie": ["Constructie"],
    "Blok": ["Blok"],
    "Weginrichtingsobject": ["Weginrichtingsobject"],
    "Verkeerskundige zone": ["Verkeerskundige zone"],
    "Markering": ["Markering"],
    "Bord": ["Bord", "Informatiebord"],
    "Drager": ["Straatmeubilair", "Paal", "Hek", "Muur", "Constructieonderdeel", "Paalconstructie"],
}


def clean_label(value: object) -> str:
    """Veldnaam zonder voetnootnummer of sterretjes, genormaliseerd. / Field name without footnote or asterisks."""
    return norm(SUFFIX.sub("", str(value).strip()))


def clean_title(value: object) -> str:
    return SEM_SPACE.sub("(sem.rel)", norm(str(value)))


@dataclass
class ManualSheet:
    name: str
    title: str = ""
    object_types: list[str] = field(default_factory=list)
    sections: dict[str, list[str]] = field(default_factory=dict)  # genormaliseerde titel -> veldnamen


@dataclass
class SectionDiff:
    title: str
    missing: list[str]
    extra: list[str]
    common: int


@dataclass
class SheetComparison:
    sheet: str
    filters: list[str]
    object_info: SectionDiff
    missing_sections: list[str]
    extra_sections: list[str]
    other_sections: list[SectionDiff]

    @property
    def recall(self) -> float:
        total = self.object_info.common + len(self.object_info.missing)
        return self.object_info.common / total if total else 1.0

    @property
    def precision(self) -> float:
        total = self.object_info.common + len(self.object_info.extra)
        return self.object_info.common / total if total else 1.0


def read_manual(path: str | Path) -> dict[str, ManualSheet]:
    """Lees de tabbladen die een 'Objecttypes: …'-regel hebben (de bijgewerkte paspoorten).
    Read the sheets that have an 'Objecttypes: …' line (the tuned passports)."""
    workbook = load_workbook(path, data_only=True)
    result: dict[str, ManualSheet] = {}
    for sheet in workbook.worksheets:
        second = sheet.cell(row=2, column=1).value
        if not isinstance(second, str) or not second.startswith("Objecttypes:"):
            continue
        manual = ManualSheet(sheet.title, str(sheet.cell(row=1, column=1).value or ""))
        manual.object_types = [t.strip() for t in second.split(":", 1)[1].split(",") if t.strip()]
        current: list[str] | None = None
        for row in sheet.iter_rows(min_row=3):
            first = row[0]
            if first.value and first.fill.fill_type == "solid":
                key = clean_title(first.value)
                if key == "basis" and "basis" in manual.sections:
                    key = "object informatie"  # in Beheerzone staat 'Object informatie' onder een tweede 'Basis'
                current = manual.sections.setdefault(key, [])
                continue
            if current is None:
                continue
            for cell in row[:MARGIN_COLUMN]:
                text = str(cell.value).strip() if cell.value is not None else ""
                if text and not set(text) <= ELLIPSIS_CHARS and not FOOTNOTE_LINE.match(text):
                    current.append(clean_label(text))
        manual.sections = {k: list(dict.fromkeys(v)) for k, v in manual.sections.items()}
        result[sheet.title] = manual
    return result


def generated_sections(tab: PassportTab) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    for section in tab.sections:
        labels = [clean_label(c.label) for row in section.rows for c in row if set(c.label) - ELLIPSIS_CHARS]
        sections[clean_title(section.title)] = list(dict.fromkeys(labels))
    return sections


def diff(title: str, manual: list[str], generated: list[str]) -> SectionDiff:
    m, g = set(manual), set(generated)
    return SectionDiff(title, sorted(m - g), sorted(g - m), len(m & g))


def compare_sheet(manual: ManualSheet, tab: PassportTab) -> SheetComparison:
    generated = generated_sections(tab)
    object_key = "object informatie"
    manual_object = [f for f in manual.sections.get(object_key, []) if f != "volgnummer"]
    skip = {"basis", object_key}
    other = [
        diff(title, manual.sections[title], generated[title])
        for title in manual.sections
        if title in generated and title not in skip
    ]
    return SheetComparison(
        sheet=manual.name,
        filters=tab.merged_from or [tab.name],
        object_info=diff("Object informatie", manual_object, generated.get(object_key, [])),
        missing_sections=[t for t in manual.sections if t not in generated and t not in skip],
        extra_sections=[t for t in generated if t not in manual.sections and t not in skip],
        other_sections=other,
    )


def compare_files(
    spec_files: list[str], manual_file: str, profile_key: str = DEFAULT_PROFILE.key,
    sheets: dict[str, list[str]] | None = None,
) -> list[SheetComparison]:
    spec = read_spec(spec_files[0])
    for extra in spec_files[1:]:
        spec.merge(read_spec(extra))
    engine = LayoutEngine(spec, LayoutOptions(profile=PROFILES[profile_key]))
    manual = read_manual(manual_file)
    mapping = sheets or ROTTERDAM_V3_SHEETS
    results = []
    filters = spec.filters()
    for name, sheet in manual.items():
        members = [f for f in mapping.get(name, [name]) if f in filters]
        if not members:
            continue
        results.append(compare_sheet(sheet, merged_tab(spec, engine, members, name)))
    return results


def format_report(results: list[SheetComparison]) -> str:
    lines = ["# Vergelijking met handmatig bijgewerkt bestand / Comparison with the manually tuned file", ""]
    if not results:
        return "\n".join([*lines, "Geen vergelijkbare tabbladen / No comparable sheets."])
    lines += ["| Sheet | Filters | Recall | Precision | Missing | Extra |", "|---|---|---|---|---|---|"]
    for r in results:
        lines.append(
            f"| {r.sheet} | {', '.join(r.filters)} | {r.recall:.0%} | {r.precision:.0%} | "
            f"{len(r.object_info.missing)} | {len(r.object_info.extra)} |",
        )
    avg_recall = sum(r.recall for r in results) / len(results)
    avg_precision = sum(r.precision for r in results) / len(results)
    lines += ["", f"**Gemiddeld / Average: recall {avg_recall:.0%}, precision {avg_precision:.0%}**", ""]
    for r in results:
        lines.append(f"## {r.sheet}")
        lines.append(f"- Object informatie ontbreekt / missing: {', '.join(r.object_info.missing) or '-'}")
        extra = ", ".join(r.object_info.extra) or "-"
        lines.append(f"- Object informatie extra (handmatig weggelaten) / extra: {extra}")
        lines.append(f"- Secties ontbreken / missing sections: {', '.join(r.missing_sections) or '-'}")
        lines.append(f"- Secties extra / extra sections: {', '.join(r.extra_sections) or '-'}")
        for section in r.other_sections:
            if section.missing or section.extra:
                lines.append(f"- {section.title}: ontbreekt {section.missing or '-'}; extra {section.extra or '-'}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", action="append", required=True, help="specificatiebestand (herhaalbaar)")
    parser.add_argument("--manual", required=True, help="handmatig bijgewerkt paspoortinrichting-bestand")
    parser.add_argument("--profile", default=DEFAULT_PROFILE.key, choices=sorted(PROFILES))
    parser.add_argument("--out", help="schrijf het rapport naar dit bestand (Markdown)")
    args: Any = parser.parse_args(argv)
    report = format_report(compare_files(args.spec, args.manual, args.profile))
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
