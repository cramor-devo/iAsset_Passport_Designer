"""Genereert de request-body voor POST /passport-tabs (iAsset API V2) uit een PassportTab.
Generates the request body for POST /passport-tabs (iAsset API V2) from a PassportTab.

NL: De body is een JSON-object dat je in de API Explorer van iAsset Syncer plakt. De structuur is gelijk aan wat
iAsset echt opslaat (gecontroleerd met een echte GET /templates/tabs): secties worden layout-elementen (field_type 2:
rij 10, lijn 1, Actoren en rollen 11, relaties 17-27, Memo 19, Geometrie 4, iASSET-id 16), velden zijn systeemvelden
(field_type 0) of diverse velden (field_type 1). Zichtbaarheid per paspoortsjabloon (visibilities) hoort bij
POST/PATCH /templates, niet bij /passport-tabs en zit dus niet in deze body.
EN: The body is a JSON object you paste into the API Explorer of iAsset Syncer. Its structure matches what iAsset
really stores (verified against a real GET /templates/tabs): sections become layout elements (field_type 2: row 10,
line 1, Actoren en rollen 11, relations 17-27, Memo 19, Geometrie 4, iASSET-id 16), fields are system fields
(field_type 0) or diverse fields (field_type 1). Per-template visibility (visibilities) belongs to POST/PATCH
/templates, not /passport-tabs, so it is not part of this body.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .field_map import FieldIdMap
from .models import Issue, PassportTab, Section, Severity
from .profiles import ELLIPSIS, DesignProfile

ENDPOINT = "POST /passport-tabs"
MAX_LABEL = 50  # maxLength in de OpenAPI-spec / maxLength in the OpenAPI spec
# iAsset gebruikt zelf een onzichtbaar teken (U+FE0F) als label van rijen zonder titel (label is verplicht).
# iAsset itself uses an invisible character (U+FE0F) as the label of untitled rows (label is required).
BLANK_LABEL = "\ufe0f"

# NL: Gecontroleerde layout-element-codes (field_type 2) uit een echte GET /templates/tabs.
# EN: Verified layout element codes (field_type 2) from a real GET /templates/tabs.
ELEMENT_LINE = 1
ELEMENT_ROW = 10
ELEMENT_ACTORS = 11
ELEMENT_GEOMETRY = 4
ELEMENT_IASSET_ID = 16
ELEMENT_MEMO = 19
ELEMENT_CONNECTED = 18
ELEMENT_CODES: dict[int, str] = {
    0: "Text heading", 1: "Horizontale lijn", 2: "Foto", 3: "Extra foto's", 4: "Geometrie", 7: "Archief",
    10: "Row / section", 11: "Actoren en rollen", 12: "Logboek", 15: "Activiteiten", 16: "iASSET-id",
    17: "Heeft deel", 18: "Is verbonden met", 19: "Is beschreven door", 20: "Bevat", 21: "Heeft begrenzing",
    22: "Voert uit", 23: "Bestaat uit", 24: "Speelt", 25: "Heeft betrekking op", 26: "Beginpunt", 27: "Eindpunt",
}
RELATION_NAMES: dict[str, int] = {
    "heeft deel": 17, "is verbonden met": 18, "is beschreven door": 19, "bevat": 20, "heeft begrenzing": 21,
    "voert uit": 22, "bestaat uit": 23, "speelt": 24, "heeft betrekking op": 25, "beginpunt": 26, "eindpunt": 27,
}
# Systeemvelden (field_type 0), op genormaliseerd label. / System fields (field_type 0), by normalised label.
SYSTEM_FIELDS: dict[str, int] = {"nummer": 1, "naam": 2, "thema": 3, "subthema": 4, "rds coordinaten": 23}

_SEM_SUFFIX = re.compile(r"\s*\((?:sem\.?\s*rel\.?|sem\.?)\)\s*$", re.IGNORECASE)
_FOOTNOTE_SUFFIX = re.compile(r"\s*\(\d+\)\s*$")


def _norm_title(title: str) -> str:
    return _SEM_SUFFIX.sub("", title.strip()).casefold().strip()


def _is_iasset_id(label: str) -> bool:
    return re.sub(r"[^a-z0-9]", "", label.casefold()) == "iassetid"


def _classify(section: Section, profile: DesignProfile | None) -> tuple[int, bool]:
    """(element-code, aangenomen?) / (element code, assumed?)."""
    title = _norm_title(section.title)
    if title.startswith("memo") or title == "is beschreven door":
        return ELEMENT_MEMO, False
    if title.startswith("actoren en rollen"):
        return ELEMENT_ACTORS, False
    if title == "geometrie":
        return ELEMENT_GEOMETRY, False
    if profile:
        for relation in profile.relations:
            if _norm_title(relation.title) == title:
                return relation.element_id, False
    if title in RELATION_NAMES:
        return RELATION_NAMES[title], False
    if section.repeater and "(sem" in section.title.casefold():
        return ELEMENT_CONNECTED, True
    return ELEMENT_ROW, False


def section_element(section: Section, profile: DesignProfile | None = None) -> int:
    """Layout-element-code (field_type 2) van een sectie. / Layout element code (field_type 2) of a section."""
    return _classify(section, profile)[0]


@dataclass(frozen=True)
class PayloadOptions:
    """Instellingen voor de payload. De standaardcodes zijn gecontroleerd met een echte GET /templates/tabs.
    Payload settings. The default codes are verified against a real GET /templates/tabs."""

    theme_id: int = -1  # -1 = alle thema's / all themes
    group_field_type: int = 2  # layout-element / layout element
    field_field_type: int = 1  # diverse veld / diverse field
    system_field_type: int = 0  # systeemveld (Nummer, Naam, ...) / system field
    group_field_id: int = ELEMENT_ROW
    line_field_id: int = ELEMENT_LINE
    separators: bool = True  # horizontale lijn tussen secties / horizontal line between sections
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
            f"Codes verified against a real GET /templates/tabs: layout element field_type="
            f"{opts.group_field_type} (row id {opts.group_field_id}, line id {opts.line_field_id}), diverse field "
            f"field_type={opts.field_field_type}, system field field_type={opts.system_field_type}, order starts at "
            f"{opts.order_start}. All are configurable in the payload settings.",
        ),
    ]
    unresolved: set[str] = set()
    ambiguous: set[str] = set()
    questions: set[str] = set()
    counts = {"total": 0, "resolved": 0}
    assumed_relations: list[str] = []
    has_iasset_id = False

    def child(cell_label: str, position: int) -> dict[str, object]:
        label = _FOOTNOTE_SUFFIX.sub("", cell_label.rstrip("*").strip())
        if cell_label.rstrip().endswith("*"):
            questions.add(label)
        counts["total"] += 1
        system_id = SYSTEM_FIELDS.get(label.casefold().strip())
        if system_id is not None:
            counts["resolved"] += 1
            field_type, field_id = opts.system_field_type, system_id
        else:
            field_type = opts.field_field_type
            field_id = ids.lookup(label) if ids else None
            if field_id is None:
                unresolved.add(label)
            else:
                counts["resolved"] += 1
                if ids and ids.is_ambiguous(label):
                    ambiguous.add(label)
        return {
            "label": _fit(label, issues, "Field label"),
            "field_type": field_type,
            "field_id": field_id,
            "order": position,
            "inherit": False,
        }

    def element(label: str, element_id: int, children: list[dict[str, object]]) -> dict[str, object]:
        return {
            "label": label,
            "field_type": opts.group_field_type,
            "field_id": element_id,
            "inherit": False,
            "children": children,
        }

    elements: list[list[dict[str, object]]] = []  # per sectie / per section
    for section in tab.sections:
        code, assumed = _classify(section, tab.profile)
        title = _fit(section.title, issues, "Section title")
        if code == ELEMENT_ROW:
            rows: list[list[str]] = []
            for row in section.rows:
                labels = [c.label for c in row if c.label.strip() and not set(c.label) <= {ELLIPSIS}]
                kept = [x for x in labels if not _is_iasset_id(x)]
                has_iasset_id = has_iasset_id or len(kept) != len(labels)
                if kept:
                    rows.append(kept)
            group: list[dict[str, object]] = []
            for index, labels in enumerate(rows):
                row_id = opts.group_field_id
                item = element(title if index == 0 else BLANK_LABEL, row_id, [])
                item["children"] = [child(x, n) for n, x in enumerate(labels, start=opts.order_start)]
                group.append(item)
            if group:
                elements.append(group)
            continue
        children: list[dict[str, object]] = []
        if code == ELEMENT_ACTORS:
            usable = [[c.label for c in r if c.label.strip() and set(c.label) != {ELLIPSIS}] for r in section.rows]
            labels = next((r for r in usable if r), [])
            children = [child(x, n) for n, x in enumerate(labels, start=opts.order_start)]
        if assumed:
            assumed_relations.append(section.title)
        elements.append([element(title, code, children)])
    if has_iasset_id:
        elements.append([element("iASSET-id", ELEMENT_IASSET_ID, [])])

    fields: list[dict[str, object]] = []
    for group in elements:
        if opts.separators and fields:
            fields.append(element("Horizontale lijn", opts.line_field_id, []))
        fields.extend(group)
    for position, item in enumerate(fields, start=opts.order_start):
        item["order"] = position
    total, resolved = counts["total"], counts["resolved"]

    if assumed_relations:
        issues.append(
            Issue(
                Severity.INFO,
                "assumed-relation-type",
                f"Assumed relation type 'Is verbonden met' (18) for: {', '.join(assumed_relations)}.",
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
