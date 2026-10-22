# Analyse: handmatig bijgewerkt paspoort vs. iAsset Passport Designer / Analysis: manually tuned passport vs. the designer

Bron / Source: `Paspoort inrichting 20261005 Rotterdam-inrichting-Wave-1-v3 (1).xlsx`
Reproduceren / Reproduce: `python -m passport_designer.compare --spec <wave1.xlsx> --manual <handmatig.xlsx>`

## Wat de handmatige versie anders doet dan het oude script / What the manual version changes

| Onderwerp / Topic | Oud script / Old script | Handmatig eindresultaat / Manual end result | Designer (profiel `rotterdam_v3`) |
|---|---|---|---|
| Kop / Header | – | Titel (18 pt) + `Objecttypes: …` | ✔ |
| Basis | Beheergroep, IMBOR Filter, Objecttype, naam / volgnummer, identificatie, domein | Nummer, Objecttype, IMBOR Filter\*, Thema, Subthema + opmerking | ✔ |
| Raster / Grid | max. 4, witregel na 3 rijen | tot 5 per rij, witregel tussen elke rij | ✔ |
| Object informatie | alle attributen | zonder administratieve velden (geostatus, in onderzoek, status, nummer, …); kwaliteitsniveau → Beleid | ✔ (uitsluitlijst) |
| Locatie | `Locatie (Sem.rel)` met geometrie | `Locatie informatie` (Openbare ruimte, Subbuurtdeelnaam, Buurtnaam, Wijknaam, Gemeentenaam, Ligging) | ✔ |
| Beheer informatie | Beheerder, Eigenaar, … | vervangen door `Actoren en rollen (Sem.Rel)` (herhaalbaar) en `Memo (Sem.Rel)` | ✔ |
| Relatiesecties / Relation sections | – | Wegvakonderdeel, Constructielagen, Wegvak informatie, Drager informatie, Borden aan drager | ✔ (uit het bestand gehaald: `data/rotterdam_v3_relations.json`) |
| Overige / Geometrie | LV-publicatiedatum, … | iAssetID, conversie-id (+ clusternummer/identificatie indien aanwezig); aparte sectie `Geometrie` | ✔ |
| Voetnoten / Footnotes | sectie onderaan | kolom `Opmerkingen` naast de rij | ✔ |
| (Sem.Rel)-kleur / colour | zachtpaars `D9D2E9` | lichtblauw `D9E2F3`; veldnamen niet vet | ✔ |
| Samenvoegen / Merging | 1 tabblad per filter | `Bord` = Bord + Informatiebord; `Drager` = Straatmeubilair + Paal + Hek + Muur + Constructieonderdeel + Paalconstructie | ✔ Bord wordt als eerste voorgesteld (gelijkenis 70 %). Drager: vanaf 40 % (alle groepen) stelt de advisor Paal + Paalconstructie + Constructieonderdeel voor; Meubilair (3 filters) en Dragers (2 filters) per groep vanaf 30–40 %. Het volledige Drager-paspoort (6 filters, 4 groepen) blijft een inhoudelijke keuze. |

## Meetresultaat / Measured result (Object informatie)

Recall = deel van de handmatig gekozen velden dat de designer ook toont. Precision = deel van de designer-velden dat handmatig is behouden.

| Sheet | Filters | Recall | Precision | Ontbreekt / Missing | Extra |
|---|---|---|---|---|---|
| Beheerzone | Beheerzone | 100% | 70% | 0 | 3 |
| Verharding | Verharding | 100% | 39% | 0 | 33 |
| Constructie | Constructie | 92% | 69% | 1 | 5 |
| Blok | Blok | 100% | 70% | 0 | 3 |
| Weginrichtingsobject | Weginrichtingsobject | 100% | 33% | 0 | 10 |
| Verkeerskundige zone | Verkeerskundige zone | 100% | 64% | 0 | 4 |
| Markering | Markering | 100% | 58% | 0 | 8 |
| Bord | Bord, Informatiebord | 96% | 73% | 1 | 8 |
| Drager | 6 filters | 100% | 20% | 0 | 37 |

**Gemiddeld / Average: recall 99 %, precision 55 %** (oud script: recall 86 %, precision 45 %).

## Wat de designer niet (kan) nabootsen / What the designer cannot reproduce

1. **Inhoudelijke selectie.** De mensen hebben veel velden bewust weggelaten (Verharding: 21 van 54; Drager: 9 van 45). Dat is geen regel in de data: de kolom *Minimale dataset* verklaart het maar deels (recall 29–82 %), een minimale dekkingsdrempel ook niet. De designer toont daarom een veilige bovenverzameling; de `compare`-tool laat precies zien welke velden zijn geschrapt.
2. **Open vragen** (`Verkeersbord**`, `Aantal borden aan drager***`, `Dikte constructie**`): afkomstig uit overleg, niet uit de data. Ze staan wel in de relatiesecties/opmerkingen; sterretjes worden in de API-payload weggelaten en als waarschuwing gemeld.
3. **Ontbrekende data.** `Piramideblok`, `Schampblok` en `Verkeersgeleidebol` hebben geen attributen in het bestand (de attributen staan bij het bovenliggende type `Blok`). De designer laat een type zonder attributen erven van het type waarop de naam eindigt (Piramideblok → Blok) en meldt de rest (Verkeersgeleidebol) als waarschuwing.
4. **Overige informatie** wisselt per tabblad (clusternummer, identificatie, Bgt-nummer, lv-publicatiedatum); de designer toont clusternummer/identificatie alleen als het attribuut in de data staat.
5. **Voetnootnummers** zijn handmatig hergebruikt over tabbladen (bijv. (18), (25)); de designer nummert per paspoort opnieuw.
6. Verouderde tabbladen in het handmatige bestand (Straatmeubilair, Hek, Muur, Constructieonderdeel, Paalconstructie in het oude 4-kolommen-formaat) worden genegeerd.
