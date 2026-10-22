"""Ontwerpprofielen: de vaste onderdelen van een paspoort (secties, raster, opmaak) los van de objecttypegegevens.
Design profiles: the fixed parts of a passport (sections, grid, formatting) separate from the object type data.

NL: 'legacy' volgt het oorspronkelijke script (Paspoortinrichting_obv_Filter.xlsx). 'rotterdam_v3' volgt het
handmatig bijgewerkte eindresultaat (Paspoort inrichting ... Wave-1-v3): iAsset-basisvelden, Locatie informatie,
Actoren en rollen, Memo, Geometrie, opmerkingen naast de rijen en een kopregel met de objecttypen.
EN: 'legacy' follows the original script. 'rotterdam_v3' follows the manually tuned end result.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .design_rules import (
    BASIS_FIRST_ROW,
    BASIS_SECOND_ROW,
    FIXED_SECTIONS_AFTER_OBJECT,
)

ELLIPSIS = "…"
RELATIONS_FILE = Path(__file__).with_name("data") / "rotterdam_v3_relations.json"


@dataclass(frozen=True)
class FixedSection:
    """Vaste sectie. ``optional`` = velden die alleen verschijnen als het attribuut in de data voorkomt;
    ``repeater`` = voorbeeldrijen die in iAsset herhaald kunnen worden (``repeat`` rijen + een '…'-rij).
    Fixed section. ``optional`` = fields shown only when the attribute exists in the data;
    ``repeater`` = sample rows that can repeat in iAsset (``repeat`` rows + a '…' row)."""

    title: str
    rows: tuple[tuple[str, ...], ...]
    repeater: bool = False
    repeat: int = 1
    optional: frozenset[str] = frozenset()
    grey: bool = False  # forceer grijs i.p.v. de (Sem.)-kleur / force grey instead of the (Sem.) colour


@dataclass(frozen=True)
class RelationSection:
    """Sectie voor een semantische relatie (bijv. 'Wegvakonderdeel (Sem.Rel)') die bij bepaalde filters hoort.
    Section for a semantic relation (e.g. 'Wegvakonderdeel (Sem.Rel)') that belongs to certain filters."""

    title: str
    rows: tuple[tuple[str, ...], ...]
    filters: frozenset[str]
    repeat: int = 1
    repeater: bool = False
    remarks: tuple[tuple[int, str], ...] = ()


@dataclass(frozen=True)
class DesignProfile:
    key: str
    label: str
    grid_columns: int
    basis_rows: tuple[tuple[str, ...], ...]
    after_object: tuple[FixedSection, ...]
    excluded: frozenset[str]
    blank_between_rows: bool  # witregel na elke rij (v3) / blank row after every row (v3)
    rows_before_blank: int  # legacy: na elke N rijen / legacy: after every N rows
    header_lines: bool  # titel + 'Objecttypes: …' bovenaan / title + 'Objecttypes: …' on top
    margin_notes: bool  # opmerkingen naast de rij i.p.v. onderaan / remarks beside the row instead of at the bottom
    bold_fields: bool
    semantic_fill: str
    basis_remark: str = ""
    basis_group_annotation: bool = True  # 'Beheergroep (Borden)' / 'Beheergroep (Borden)'
    relations: tuple[RelationSection, ...] = field(default=())

    @property
    def fixed_names(self) -> frozenset[str]:
        """Veldnamen met een vaste plek (niet in 'Object informatie'). / Field names with a fixed place."""
        names = {n.casefold() for row in self.basis_rows for n in row}
        for section in self.after_object:
            names.update(n.casefold() for row in section.rows for n in row)
        return frozenset(names | self.excluded)

    def relations_for(self, filters: list[str]) -> list[RelationSection]:
        wanted = set(filters)
        return [r for r in self.relations if r.filters & wanted]


LEGACY = DesignProfile(
    key="legacy",
    label="Original (Paspoortinrichting_obv_Filter)",
    grid_columns=4,
    basis_rows=(BASIS_FIRST_ROW, BASIS_SECOND_ROW),
    after_object=tuple(FixedSection(title, rows) for title, rows in FIXED_SECTIONS_AFTER_OBJECT),
    excluded=frozenset(),
    blank_between_rows=False,
    rows_before_blank=3,
    header_lines=False,
    margin_notes=False,
    bold_fields=True,
    semantic_fill="D9D2E9",
)

# Administratieve velden die in de handmatig bijgewerkte versie nergens als 'Object informatie' voorkomen.
# Administrative fields that never appear as 'Object informatie' in the manually tuned version.
V3_EXCLUDED = frozenset(
    {
        "geostatus", "in onderzoek", "locatieaanduiding", "nummer", "relatieve hoogteligging", "status", "naam",
        "alternatieve naam", "ambitieniveau", "beheerafspraak", "beheerder", "beheerder gedetailleerd", "eigenaar",
        "eigenaar gedetailleerd", "onderhoudsplichtige", "imbor type", "beheerobjectomschrijving", "volgnummer",
        "lv-publicatiedatum", "domein", "identificatie geovoorziening", "plaatsingsjaar",
    },
)

V3_BASIS_REMARK = (
    "*IMBOR filter zit niet in de aangeleverde data. Dit is het veld Filter waarop de legenda van iasset nu is "
    "gebaseerd. Zie ook colom E in het tabblad Objecttype."
)


def load_relations(path: Path = RELATIONS_FILE) -> tuple[RelationSection, ...]:
    """Lees de relatiesecties uit het JSON-bestand (leeg als het bestand ontbreekt).
    Read the relation sections from the JSON file (empty when the file is missing)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    result = []
    for item in data.get("sections", []):
        result.append(
            RelationSection(
                title=item["title"],
                rows=tuple(tuple(row) for row in item["rows"]),
                filters=frozenset(item["filters"]),
                repeat=int(item.get("repeat", 1)),
                repeater=bool(item.get("repeater", False)),
                remarks=tuple((int(k), v) for k, v in item.get("remarks", {}).items()),
            ),
        )
    return tuple(result)


ROTTERDAM_V3 = DesignProfile(
    key="rotterdam_v3",
    label="Rotterdam v3 (manually tuned)",
    grid_columns=5,
    basis_rows=(("Nummer", "Objecttype", "IMBOR Filter*", "Thema", "Subthema"),),
    after_object=(
        FixedSection(
            "Locatie informatie",
            (("Openbare ruimte", "Subbuurtdeelnaam", "Buurtnaam", "Wijknaam"), ("Gemeentenaam", "Ligging")),
        ),
        FixedSection(
            "Beleidsinformatie",
            (("structuurniveau", "structuurgebied", "kwaliteitsniveau", "bestemming", "wegcategorie duurzaam veilig"),),
            optional=frozenset({"wegcategorie duurzaam veilig"}),
        ),
        FixedSection(
            "Actoren en rollen (Sem.Rel)",
            (("Rol", "Rol gedetailleerd", "Actor", "Actor Gedetailleerd"),),
            repeater=True,
            repeat=2,
        ),
        FixedSection("Memo (Sem.Rel)", (("Nummer", "Memo veld"),), repeater=True, repeat=3),
        FixedSection(
            "Overige informatie",
            (("iAssetID", "clusternummer", "conversie-id", "identificatie"),),
            optional=frozenset({"clusternummer", "identificatie"}),
        ),
        FixedSection("Geometrie", (("geometrie",),), grey=True),
    ),
    excluded=V3_EXCLUDED,
    blank_between_rows=True,
    rows_before_blank=0,
    header_lines=True,
    margin_notes=True,
    bold_fields=False,
    semantic_fill="D9E2F3",
    basis_remark=V3_BASIS_REMARK,
    basis_group_annotation=False,
    relations=load_relations(),
)

PROFILES: dict[str, DesignProfile] = {p.key: p for p in (ROTTERDAM_V3, LEGACY)}
DEFAULT_PROFILE = ROTTERDAM_V3
