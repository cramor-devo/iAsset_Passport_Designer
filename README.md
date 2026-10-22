# iAsset Passport Designer

Zet IMBOR-/objecttypespecificaties (xlsx, Wave 1 en Wave 2) om in **paspoortontwerpen**, een **visuele mockup** en
**`POST /passport-tabs`-strings** die je met [iAsset Syncer](https://github.com/cramor-devo/iAsset_Syncer) naar de
iAsset V2 API stuurt. / Turns IMBOR/object type specifications (xlsx, Wave 1 and 2) into **passport designs**, a
**visual mockup** and **`POST /passport-tabs` strings** you send to the iAsset V2 API with iAsset Syncer.

Minimum Python 3.11 · PyQt6 6.11.0 (GPL-3.0) · openpyxl 3.1.5 (MIT, leest/schrijft xlsx / reads and writes xlsx).
Licence: GPL-3.0-or-later (required by PyQt6's GPL terms; same as iAsset Syncer).

## Download (Windows)

Download `iAsset_Passport_Designer.exe` from the latest [release](../../releases): one file, no Python needed.
(The executable is not code-signed, so Windows SmartScreen may warn on first start.) Build it yourself with
`powershell -ExecutionPolicy Bypass -File build.ps1`.

## Setup

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Ontwikkelen / Development: `pip install -r requirements-dev.txt`, then `ruff check .`, `pyright`, `pytest`.
Logbestand / log file: `%LOCALAPPDATA%\iAssetPassportDesigner\passport_designer.log`.

## Gebruik / Usage

1. **File → Open specification(s)…** (meerdere xlsx tegelijk; *Add specification* voegt toe, bijv. Wave 2 bovenop Wave 1).
   Verwacht tabbladen `Objecttypen` (Objecttype, Filter, Groep/Fase) en `Attributen` (Objecttype, Attribuut).
2. Kies links een filter en een voorbeeld-objecttype: de **Mockup** toont het paspoort in iAsset-stijl (donker/licht).
   Velden die niet voor het gekozen objecttype gelden zijn gedimd (tooltip toont voor welke objecttypen/subthema's).
3. **Samenvoegadvies**: stelt filters voor die één paspoort kunnen delen (zelfde beheergroep, Jaccard-gelijkenis van
   attributen). Velden die niet voor alle objecttypen gelden krijgen een voetnoot — dat zijn de velden die je in iAsset
   per subthema aan/uit zet. *Voorbeeld* bekijkt, *Toepassen* voegt samen, *Matrix exporteren* schrijft veld × objecttype.
4. **File → Load field ID file…**: JSON/CSV/xlsx-export van `GET /diverse-fields` (kolommen label/name + id). Zonder
   veld-id's staat `field_id` op `null` en meldt het tabblad *Validatie* een fout.
5. Tabblad **API payload**: kopieer of sla op. Plak de JSON in iAsset Syncer → API Explorer → V2 → `POST /passport-tabs`
   (Syncer verstuurt het als multipart met `fields[0][children][1][label]`; dezelfde velden staan onder *Formuliervelden*).
6. **File → Export Excel design…** schrijft één tabblad per paspoort; *Export mockup as PNG* de mockup.

## Ontwerpprofielen / Design profiles (Settings → Design profile)

- **Rotterdam v3 (standaard)** — volgt het handmatig bijgewerkte eindresultaat (`docs/analyse-handmatig-v3.md`).
- **Original** — het oorspronkelijke script (4 kolommen, Beheer informatie, notities onderaan).

`python -m passport_designer.compare --spec wave1.xlsx --manual handmatig.xlsx` vergelijkt de uitvoer met een handmatig
bijgewerkt bestand (recall/precision per tabblad). `python tools/extract_relations.py handmatig.xlsx` leest de
relatiesecties (Sem.Rel) uit zo'n bestand naar `passport_designer/data/rotterdam_v3_relations.json`.

## Aannames die je op een testomgeving moet controleren / Assumptions to verify on a test system

De OpenAPI-spec van `POST /passport-tabs` noemt alleen `field_type ∈ {0, 1, 2}` zonder betekenis. Standaard: rij
(top-level) = `1`, veld (child) = `0`, `field_id` van een rij = `0`, `order` begint bij `1`, rijen zonder titel krijgen
het onzichtbare label U+FE0F (zoals iAsset zelf doet). Aanpasbaar onder *Settings → Payload settings*.
The spec does not document the `field_type` codes; the defaults above are assumptions.

## Bekende beperkingen / Known limitations

- De inhoudelijke selectie van velden per paspoort is menselijk werk; de designer toont een veilige bovenverzameling.
- Herhaalbare secties (Actoren, Memo) worden als één rij verstuurd; zet ze in iAsset op herhalen.
- Objecttypen zonder attributen in de data worden gemeld (zie Validatie).
