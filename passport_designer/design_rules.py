"""Ontwerpregels voor het paspoort (vaste secties, vaste velden en blokindeling van 'Object informatie').
Design rules for the passport (fixed sections, fixed fields and block classification of 'Object informatie')."""

from __future__ import annotations

GRID_COLUMNS = 4
ROWS_BEFORE_BLANK = 3  # na elke 3 rijen (12 velden) een witregel / a blank line after every 3 rows (12 fields)

# Sectietitels (exacte volgorde). / Section titles (exact order).
SECTION_BASIS = "Basis"
SECTION_OBJECT = "Object informatie"
SECTION_NOTES = "Notities / Uitzonderingen"

# Vaste secties NA 'Object informatie': titel -> rijen met velden. / Fixed sections AFTER 'Object informatie'.
FIXED_SECTIONS_AFTER_OBJECT: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = (
    (
        "Locatie (Sem.rel)",
        (
            ("Gemeente", "Wijk", "Buurt", "Subbuurtdeel"),
            ("Straatnaam", "Openbare ruimte", "Ligging", "geometrie"),
            ("identificatie geovoorziening",),
        ),
    ),
    (
        "Beleidsinformatie",
        (
            ("structuurniveau", "structuurgebied", "ambitieniveau", "bestemming"),
            ("wegcategorie duurzaam veilig",),
        ),
    ),
    (
        "Beheer informatie (Sem.Rel)",
        (
            ("Beheerder", "Beheerder gedetailleerd", "Eigenaar", "Eigenaar gedetailleerd"),
            ("Onderhoudsplichtige", "beheerafspraak"),
        ),
    ),
    (
        "Drager informatie (Sem.)",
        (("IMBOR type", "Modelnaam", "Plaatsingsjaar"),),
    ),
    (
        "Overige informatie",
        (("Beheerobjectomschrijving", "clusternummer", "LV-publicatiedatum", "conversie-id"),),
    ),
)

# Velden in Basis; 'Beheergroep' krijgt de waarde van de groep. / Fields in Basis; 'Beheergroep' gets the group value.
BASIS_FIRST_ROW = ("Beheergroep", "IMBOR Filter", "Objecttype", "naam")
BASIS_SECOND_ROW = ("volgnummer", "identificatie", "domein")

# Attributen die al een vaste plek hebben horen niet in 'Object informatie'.
# Attributes that already have a fixed place do not belong in 'Object informatie'.
FIXED_FIELD_NAMES: frozenset[str] = frozenset(
    {n.casefold() for n in (*BASIS_FIRST_ROW, *BASIS_SECOND_ROW)}
    | {n.casefold() for _, rows in FIXED_SECTIONS_AFTER_OBJECT for row in rows for n in row},
)

# Logische blokken in 'Object informatie': (blokkaam, trefwoorden). Eerste treffer wint, dus de volgorde telt
# (bijv. 'type conservering' hoort bij Materiaal/Specs, niet bij Vorm/Type). Aanpasbaar zonder andere code te wijzigen.
# Logical blocks in 'Object informatie': (block name, keywords). First match wins, so order matters
# (e.g. 'type conservering' belongs to Materiaal/Specs, not Vorm/Type). Editable without touching other code.
BLOCK_ORDER: tuple[str, ...] = (
    "Identificatie",
    "Vorm/Type",
    "Dimensies",
    "Materiaal/Specs",
    "Ligging",
    "Tijd/Plaatsing",
    "Overig",
)

BLOCK_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Ligging", ("ligging", "locatie", "orient", "richting", "aanlegh", "maaiveld")),
    ("Tijd/Plaatsing", ("jaar", "datum", "periode", "plaatsing", "aanleg", "levensduur", "leeftijd", "tijdelijk")),
    ("Dimensies", ("breedte", "hoogte", "diameter", "dikte", "lengte", "afmeting", "oppervlakte", "inhoud",
                   "diepte", "afstand", "gewicht", "helling", "straal", "maat")),
    ("Materiaal/Specs", ("materiaal", "kleur", "conserv", "reflectie", "kwaliteit", "markering", "coating",
                         "afwerking", "eigenschap", "specificatie")),
    ("Identificatie", ("nummer", "code", "identif", "barcode", "kenmerk", "sleutel", "verordening",
                       "status", "onderzoek")),
    ("Vorm/Type", ("vorm", "type", "soort", "toepassing", "functie", "uitvoering", "bevestiging", "symbool",
                   "tekst", "waarde", "opbouw", "categorie")),
)


def classify_block(attribute: str) -> str:
    """Bepaal het logische blok van een attribuut via trefwoorden. / Determine the logical block of an attribute."""
    name = attribute.casefold()
    for block, keywords in BLOCK_KEYWORDS:
        if any(keyword in name for keyword in keywords):
            return block
    return "Overig"
