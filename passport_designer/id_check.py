"""ID-controle (offline): vergelijkt het ontwerp met een veldencatalogus. Geen netwerk, geen Qt.
ID check (offline): compares the design with a field catalog. No network, no Qt."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .field_catalog import FieldCatalog, FieldInfo
from .field_map import FieldIdMap
from .models import PassportTab, norm

OK = "ok"
MISSING_ID = "missing-id"
UNKNOWN_ID = "unknown-id"
AMBIGUOUS = "ambiguous"
LABEL_MISMATCH = "label-mismatch"
TYPE_MISMATCH = "type-mismatch"
SUBTHEME_DISABLED = "subtheme-disabled"
SUBTHEME_UNKNOWN = "subtheme-unknown"

REPORT_SHEET = "ID-controle"
_HEADERS = ("Tab", "Section", "Label", "Field ID", "Status", "Severity", "Detail", "Object types")
_WIDTHS = (28, 28, 34, 12, 20, 10, 70, 50)


@dataclass
class IdFinding:
    """Eén bevinding. / One finding."""

    tab: str
    section: str
    label: str
    field_id: int | None
    status: str
    severity: str  # 'error' | 'warning' | 'info'
    detail: str = ""
    object_types: list[str] = field(default_factory=list)


def _clean(label: str) -> str:
    return label.rstrip("*").strip()


def _fields(tab: PassportTab) -> dict[str, tuple[str, str]]:
    """Unieke velden van een tab: genormaliseerd label -> (sectietitel, ontwerplabel). / Unique fields of a tab."""
    found: dict[str, tuple[str, str]] = {}
    for section in tab.sections:
        rows = section.rows[:1] if section.repeater else section.rows
        for row in rows:
            for cell in row:
                label = _clean(cell.label)
                if label:
                    found.setdefault(norm(label), (section.title, label))
    return found


def _subtheme_findings(
    tab: PassportTab, section: str, label: str, info: FieldInfo, catalog: FieldCatalog,
) -> list[IdFinding]:
    disabled: list[str] = []
    for obj in tab.object_types:
        if not tab.applicable(label, obj.name):
            continue
        wanted = catalog.subthemes_for_name(obj.name)
        if wanted and not (wanted & info.subthemes):
            disabled.append(obj.name)
    if not disabled:
        return []
    return [
        IdFinding(
            tab.name, section, label, info.id, SUBTHEME_DISABLED, "error",
            "Field is not enabled for the subtheme of these object types.", disabled,
        ),
    ]


def check_ids(tabs: list[PassportTab], catalog: FieldCatalog, id_map: FieldIdMap | None = None) -> list[IdFinding]:
    """Controleer per tab en veld de id's tegen de catalogus. / Check IDs per tab and field against the catalog."""
    findings: list[IdFinding] = []
    other = id_map.catalog if id_map is not None and id_map.catalog is not catalog else None
    if not catalog.has_subtheme_names:
        findings.append(
            IdFinding(
                "", "", "", None, SUBTHEME_UNKNOWN, "info",
                "Subtheme names are unknown in this catalog; load the iAsset field-catalog xlsx to check subthemes.",
            ),
        )
    for tab in tabs:
        for section, label in _fields(tab).values():
            found = _check_field(tab, section, label, catalog, id_map, other)
            if not found:
                ok_id = id_map.lookup(label) if id_map is not None else None
                if ok_id is None:
                    ok_id = catalog.by_label(label)[0].id
                found = [IdFinding(tab.name, section, label, ok_id, OK, "info")]
            findings.extend(found)
        if catalog.has_subtheme_names:
            unmatched = [o.name for o in tab.object_types if not catalog.subthemes_for_name(o.name)]
            if unmatched:
                findings.append(
                    IdFinding(
                        tab.name, "", "", None, SUBTHEME_UNKNOWN, "warning",
                        "No subtheme with this name in the catalog; subtheme check skipped.", unmatched,
                    ),
                )
    return findings


def _check_field(
    tab: PassportTab, section: str, label: str, catalog: FieldCatalog, id_map: FieldIdMap | None,
    other: FieldCatalog | None,
) -> list[IdFinding]:
    matches = catalog.by_label(label)
    field_id = id_map.lookup(label) if id_map is not None else None
    if id_map is not None and field_id is not None:
        # De ID-map beslist; alleen een dubbel label in de map zelf is dubbelzinnig. Het gekozen ID wordt hieronder
        # gecontroleerd (bestaan, type, subthema). / The ID map decides; only a duplicate in the map itself is
        # ambiguous. The chosen ID is validated below (existence, type, subtheme).
        ambiguous = id_map.is_ambiguous(label)
    else:
        ambiguous = len(matches) > 1
        field_id = matches[0].id if len(matches) == 1 else None
    if ambiguous:
        ids = sorted({m.id for m in matches}) or ([field_id] if field_id is not None else [])
        return [
            IdFinding(
                tab.name, section, label, field_id, AMBIGUOUS, "warning",
                f"Label matches several field IDs: {', '.join(map(str, ids))}.",
            ),
        ]
    if field_id is None:
        return [IdFinding(tab.name, section, label, None, MISSING_ID, "error", "No field ID found for this label.")]
    info = catalog.get(field_id)
    if info is None:
        return [
            IdFinding(tab.name, section, label, field_id, UNKNOWN_ID, "error", "Field ID is not in the catalog."),
        ]
    result: list[IdFinding] = []
    if norm(info.label) != norm(label):
        result.append(
            IdFinding(
                tab.name, section, label, field_id, LABEL_MISMATCH, "warning",
                f"Catalog label is '{info.label}'.",
            ),
        )
    counterpart = other.get(field_id) if other is not None else None
    if counterpart and counterpart.kind != "unknown" and info.kind != "unknown" and counterpart.kind != info.kind:
        result.append(
            IdFinding(
                tab.name, section, label, field_id, TYPE_MISMATCH, "warning",
                f"Type differs: {counterpart.type} ({counterpart.kind}) vs {info.type} ({info.kind}).",
            ),
        )
    result.extend(_subtheme_findings(tab, section, label, info, catalog))
    return result


def summarize(findings: list[IdFinding]) -> dict[str, int]:
    """Aantal bevindingen per status. / Number of findings per status."""
    return dict(Counter(f.status for f in findings))


def summary_text(findings: list[IdFinding]) -> str:
    """Korte samenvatting, bijv. '3 ok, 1 missing-id'. / Short summary, e.g. '3 ok, 1 missing-id'."""
    counts = summarize(findings)
    return ", ".join(f"{n} {status}" for status, n in sorted(counts.items())) or "no findings"


def export_id_report(findings: list[IdFinding], path: str | Path) -> None:
    """Schrijf de bevindingen naar een xlsx-bestand. / Write the findings to an xlsx file."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = REPORT_SHEET
    sheet.append(list(_HEADERS))
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for f in findings:
        sheet.append(
            [f.tab, f.section, f.label, f.field_id, f.status, f.severity, f.detail, ", ".join(f.object_types)],
        )
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(_HEADERS))}{max(sheet.max_row, 1)}"
    sheet.freeze_panes = "A2"
    for index, width in enumerate(_WIDTHS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    workbook.save(Path(path))
