"""Genereert de request-body voor POST /passport-tabs (iAsset API V2) uit een PassportTab.
Generates the request body for POST /passport-tabs (iAsset API V2) from a PassportTab.

NL: De body is een JSON-object dat je in de API Explorer van iAsset Syncer plakt; Syncer verstuurt het als
multipart-formulier met Laravel-notatie (fields[0][children][1][label]). Elke rij van het raster wordt één
top-level 'field' (de rij) met de velden als 'children'; dat past bij de API (één niveau children) en bij het
iAsset-paspoort, waar elke rij een tabel met kolomkoppen is.
EN: The body is a JSON object you paste into the API Explorer of iAsset Syncer; Syncer sends it as a multipart form
with Laravel notation (fields[0][children][1][label]). Each grid row becomes one top-level 'field' (the row) with the
fields as 'children'; this fits the API (one level of children) and the iAsset passport, where each row is a table
with column headings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .field_map import FieldIdMap
from .models import Issue, PassportTab, Severity

ENDPOINT = "POST /passport-tabs"
MAX_LABEL = 50  # maxLength in de OpenAPI-spec / maxLength in the OpenAPI spec
# iAsset gebruikt zelf een onzichtbaar teken (U+FE0F) als label van rijen zonder titel (label is verplicht).
# iAsset itself uses an invisible character (U+FE0F) as the label of untitled rows (label is required).
BLANK_LABEL = "\ufe0f"


@dataclass(frozen=True)
class PayloadOptions:
    """Instellingen voor de payload. De type-codes zijn aannames: de OpenAPI-spec noemt alleen de waarden 0, 1, 2.
    Payload settings. The type codes are assumptions: the OpenAPI spec only lists the values 0, 1, 2."""

    theme_id: int = -1  # -1 = alle thema's / all themes
    group_field_type: int = 1
    field_field_type: int = 0
    group_field_id: int = 0
    order_start: int = 1
    active: bool = True


@dataclass
class TabPayload:
    """Resultaat: body, meldingen en tellingen. / Result: body, issues and counts."""

    body: dict[str, Any]
    issues: list[Issue] = field(default_factory=list)
    field_count: int = 0
    resolved_count: int = 0

    @property
    def unresolved_count(self) -> int:
        return self.field_count - self.resolved_count

    def has_errors(self) -> bool:
        return any(i.severity is Severity.ERROR for i in self.issues)


def _fit(label: str, issues: list[Issue], what: str) -> str:
    if len(label) <= MAX_LABEL:
        return label
    message = f"{what} '{label}' is longer than {MAX_LABEL} characters; truncated."
    issues.append(Issue(Severity.WARNING, "label-too-long", message))
    return label[:MAX_LABEL]


def build_tab_payload(
    tab: PassportTab, ids: FieldIdMap | None = None, options: PayloadOptions | None = None,
) -> TabPayload:
    """Bouw de body voor één paspoorttabblad. Onbekende veld-id's worden null (en gemeld).
    Build the body for one passport tab. Unknown field IDs become null (and are reported)."""
    opts = options or PayloadOptions()
    issues: list[Issue] = [
        Issue(
            Severity.INFO,
            "assumed-type-codes",
            f"Assumed codes: row field_type={opts.group_field_type}, field field_type={opts.field_field_type}, "
            f"row field_id={opts.group_field_id}, order starts at {opts.order_start}. "
            "The API spec does not document these; verify on a test environment.",
        ),
    ]
    unresolved: set[str] = set()
    ambiguous: set[str] = set()
    fields: list[dict[str, object]] = []
    total = resolved = 0
    order = opts.order_start
    repeaters: list[str] = []
    questions: set[str] = set()
    for section in tab.sections:
        title_pending = True
        rows = section.rows[:1] if section.repeater else section.rows
        if section.repeater:
            repeaters.append(section.title)
        for row in rows:
            if not row:
                continue
            children: list[dict[str, object]] = []
            for position, cell in enumerate(row, start=opts.order_start):
                # sterretjes zijn open vragen in het ontwerp / asterisks are open questions in the design
                label = cell.label.rstrip("*").strip()
                if label != cell.label:
                    questions.add(label)
                field_id = ids.lookup(label) if ids else None
                total += 1
                if field_id is None:
                    unresolved.add(label)
                else:
                    resolved += 1
                    if ids and ids.is_ambiguous(label):
                        ambiguous.add(label)
                children.append(
                    {
                        "label": _fit(label, issues, "Field label"),
                        "field_type": opts.field_field_type,
                        "field_id": field_id,
                        "order": position,
                        "inherit": False,
                    },
                )
            title = _fit(section.title, issues, "Section title") if title_pending else BLANK_LABEL
            title_pending = False
            fields.append(
                {
                    "label": title,
                    "field_type": opts.group_field_type,
                    "field_id": opts.group_field_id,
                    "order": order,
                    "inherit": False,
                    "children": children,
                },
            )
            order += 1

    if repeaters:
        issues.append(
            Issue(
                Severity.INFO,
                "repeater-sections",
                f"Repeating sections sent as one row each (set them to repeat in iAsset): {', '.join(repeaters)}.",
            ),
        )
    if questions:
        issues.append(
            Issue(
                Severity.WARNING,
                "open-design-questions",
                f"Fields marked with * in the design are open questions (not in the delivered data): "
                f"{', '.join(sorted(questions))}.",
            ),
        )
    if unresolved:
        shown = ", ".join(sorted(unresolved, key=str.casefold)[:12])
        more = f" (+{len(unresolved) - 12} more)" if len(unresolved) > 12 else ""
        issues.append(
            Issue(
                Severity.WARNING if ids else Severity.ERROR,
                "unresolved-field-ids",
                f"{len(unresolved)} field(s) without iAsset field_id: {shown}{more}. "
                "Load a field ID file (GET /diverse-fields) before posting.",
            ),
        )
    if ambiguous:
        names = ", ".join(sorted(ambiguous))
        issues.append(
            Issue(Severity.WARNING, "ambiguous-field-ids", f"Label(s) with several IDs (first used): {names}"),
        )
    if tab.data_gaps:
        issues.append(
            Issue(
                Severity.WARNING,
                "no-attributes",
                f"No attributes in the specification for: {', '.join(tab.data_gaps)}. "
                "They may inherit them from a parent type that is missing in the data.",
            ),
        )
    if tab.merged_from:
        issues.append(
            Issue(
                Severity.INFO,
                "merged-passport",
                f"Merged passport from filters: {', '.join(tab.merged_from)}.",
            ),
        )
    if tab.footnotes:
        issues.append(
            Issue(
                Severity.INFO,
                "partial-fields",
                f"{len(tab.footnotes)} footnoted field(s) apply to only some object types (see Notes); "
                "restrict them with sub-themes in iAsset.",
            ),
        )
    body: dict[str, object] = {
        "name": _fit(tab.name, issues, "Tab name"),
        "theme": opts.theme_id,
        "description": _fit(tab.group, issues, "Description") if tab.group else None,
        "active": opts.active,
        "fields": fields,
    }
    return TabPayload(body, issues, total, resolved)


def to_json(body: dict[str, object]) -> str:
    """Leesbare JSON voor de API Explorer. / Readable JSON for the API Explorer."""
    return json.dumps(body, indent=2, ensure_ascii=False)


def to_compact_json(body: dict[str, object]) -> str:
    """Compacte JSON op één regel (de 'string' om te plakken). / Compact one-line JSON (the string to paste)."""
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False)


def flatten(value: object, prefix: str = "") -> list[tuple[str, object]]:
    """Geneste body -> Laravel-formuliervelden (zoals Syncer). / Nested body -> Laravel form fields (like Syncer)."""
    if isinstance(value, dict):
        items: list[tuple[str, object]] = []
        for key, item in value.items():
            items.extend(flatten(item, f"{prefix}[{key}]" if prefix else str(key)))
        return items
    if isinstance(value, list):
        items = []
        for index, item in enumerate(value):
            items.extend(flatten(item, f"{prefix}[{index}]"))
        return items
    return [(prefix, value)]


def to_form_lines(body: dict[str, object]) -> str:
    """Eén regel per formulierveld: 'fields[0][label]=Basis' (None -> leeg, bool -> 1/0).
    One line per form field: 'fields[0][label]=Basis' (None -> empty, bool -> 1/0)."""
    lines = []
    for name, value in flatten(body):
        if value is None:
            text = ""
        elif isinstance(value, bool):
            text = "1" if value else "0"
        else:
            text = str(value)
        lines.append(f"{name}={text}")
    return "\n".join(lines)
