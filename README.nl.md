# iAsset Passport Designer

[English](README.md) · **Nederlands**

iAsset Passport Designer zet IMBOR-objecttypespecificaties (xlsx, Wave 1 en Wave 2) om in drie dingen:

- een **paspoortontwerp** per filter,
- een **visuele mockup** van het paspoort in iAsset-stijl,
- **`POST /passport-tabs`-payloads** die je met [iAsset Syncer](https://github.com/cramor-devo/iAsset_Syncer) naar de
  iAsset V2 API stuurt.

De interface is beschikbaar in het Nederlands en het Engels (**Beeld → Taal**).

## Vereisten

- Python 3.11 of nieuwer
- PyQt6 6.11.0 (GPL-3.0)
- openpyxl 3.1.5 (MIT), om xlsx-bestanden te lezen en te schrijven

## Downloaden (Windows)

Download `iAsset_Passport_Designer.exe` bij de nieuwste [release](../../releases). Het is één bestand en je hebt er
geen Python voor nodig. Het programma is niet digitaal ondertekend, dus Windows SmartScreen kan bij de eerste keer
starten een waarschuwing geven.

Wil je het programma zelf bouwen? Gebruik dan:

```text
powershell -ExecutionPolicy Bypass -File build.ps1
```

Het resultaat komt in `dist\iAsset_Passport_Designer.exe`.

### Een release maken

Lokaal bouwen is niet nodig voor een release. Zet `__version__` in `passport_designer/__init__.py` en werk
`CHANGELOG.md` bij. Samenvoegen naar `main` is genoeg: de workflow **CI and release** bouwt de exe en publiceert
release `v<versie>` (zie [Ontwikkelen](#ontwikkelen)).

Je kunt ook zelf een GitHub-release publiceren met tag `vX.Y.Z` (gelijk aan de versie). De workflow **Release** draait
dan de tests op `windows-latest`, bouwt de exe met `build.ps1` en hangt `iAsset_Passport_Designer.exe` en
`iAsset_Passport_Designer.exe.sha256` aan die release. Wil je een bestaande release opnieuw bouwen of het
SHA256-bestand toevoegen, start de workflow dan handmatig (**Actions → Release → Run workflow**) met de tag.

## Installeren vanuit de broncode

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Het logbestand staat in `%LOCALAPPDATA%\iAssetPassportDesigner\passport_designer.log`.

## Gebruik

1. Kies **Bestand → Specificatie(s) openen…** en selecteer een of meer xlsx-bestanden. Met **Specificatie
   toevoegen…** voeg je een bestand toe aan wat al geladen is, bijvoorbeeld Wave 2 bovenop Wave 1. Elk bestand heeft
   een tabblad `Objecttypen` nodig (kolom Objecttype plus Filter, Zoekfilter of Fase; eventueel Groep) en een tabblad
   `Attributen` (kolommen Objecttype, Attribuut).
2. Kies linksboven bij **Filterkolom (Objecttypen)** op welke kolom van het tabblad `Objecttypen` de objecttypen in
   paspoorten worden gegroepeerd, bijvoorbeeld `Filter`/`Zoekfilter` in Wave 1 of `Fase` in Wave 2. Standaard gebruikt
   de designer Filter, dan Zoekfilter, dan Fase; je keuze wordt onthouden. Wijzigen maakt toegepaste samenvoegingen
   ongedaan.
3. Kies links een filter en een voorbeeld-objecttype. **Alle objecttypen** toont het hele paspoort; kies je één
   objecttype, dan worden velden die daar niet voor gelden **verborgen**. Het tabblad **Mockup** laat zien hoe het
   paspoort er in iAsset uitziet. Via **Beeld → Mockup-thema** kies je een donker of licht thema. Het tabblad
   **Ontwerpblad** toont precies wat de Excel-export schrijft, ingedeeld zoals het paspoortinrichting-bestand: de
   titel, de objecttypen eronder, grijze (en lichtblauwe voor Sem.Rel) sectiekoppen, een lege kolom en de
   verwijzingslijst `Opmerkingen` voor velden die niet voor alle objecttypen gelden.
4. Het tabblad **Samenvoegadvies** stelt filters voor die samen één paspoort kunnen gebruiken. Het advies is gebaseerd
   op dezelfde beheergroep en vergelijkbare attributen (Jaccard-gelijkenis). Velden die niet voor alle objecttypen
   gelden, krijgen een voetnoot: dit zijn de velden die je in iAsset per subthema aan- of uitzet. Met **Voorbeeld
   samengevoegd paspoort** bekijk je een voorstel, met **Samenvoegen toepassen** voeg je de filters samen en met
   **Samenvoegmatrix exporteren…** sla je een matrix van velden × objecttypen op.
   Je kunt ook handmatig samenvoegen: selecteer twee of meer paspoorten in de lijst (Ctrl/Shift+klik) en kies
   **Bestand → Geselecteerde paspoorten samenvoegen…** (**Ctrl+M**, ook in het contextmenu en als **Selectie
   samenvoegen…** op het tabblad Samenvoegadvies). Dat werkt ongeacht filter, groep of drempel van het advies. Geef het
   nieuwe paspoort een naam (verplicht, maximaal 50 tekens, uniek). Verschillen de paspoorten in beheergroep of
   filter, dan toont het venster die verschillen en moet je het uitdrukkelijk bevestigen (Annuleren is de standaard).
   Een handmatige samenvoeging maak je net als andere samenvoegingen ongedaan; bij een ingelezen ontwerp is ze niet
   beschikbaar.
5. Kies **Bestand → Veld-ID-bestand laden…** om een export van `GET /diverse-fields` te laden: de V2-paspoort-diverse-veldenlijst (bijv. `passport field list.csv`,
   CSV met puntkomma `id;label;name;type;values;…`; JSON en xlsx met label/name en id werken ook). Elk paspoortveld
   krijgt de `id` van het diverse veld met dezelfde label. Het iAsset-veldencatalogus-xlsx uit de GUI (met de tabbladen
   `Paspoort velden` en `Thema Subthema`) werkt ook. Zonder veld-ID's krijgt `field_id` de waarde `null` en meldt het
   tabblad **Validatie** een fout.
6. Op het tabblad **API-payload** kopieer je de payload of sla je hem op. Plak de JSON in iAsset Syncer → API Explorer
   → V2 → `POST /passport-tabs`. Syncer verstuurt de gegevens als multipart-formulier
   (`fields[0][children][1][label]`); het formaat **Formuliervelden (Laravel)** toont dezelfde velden in die vorm.
7. **Bestand → Excel-ontwerp exporteren…** maakt één tabblad per paspoort. **Bestand → Excel-ontwerp per objecttype
   exporteren…** maakt één tabblad per objecttype, zonder de velden die daar niet voor gelden. **Bestand → Mockup als
   PNG exporteren…** slaat de mockup (zoals in het voorbeeld) op als afbeelding. Elke Excel-export bevat ook de
   naslagbladen `Bron Objecttypen` en `Bron Attributen` (de specificatieregels van de geëxporteerde objecttypen, met
   bronbestand en datum) en een verborgen blad `_designer` met metagegevens (versie, profiel, specificatiebestanden,
   filterkolom, tabblad → objecttypen).
8. **Bestand → Veld-ID's controleren…** controleert de paspoortvelden **offline** tegen de geladen veld-ID's: het
   programma roept iAsset nooit aan. Laad eerst een opgeslagen V2 `GET /diverse-fields`-JSON of het
   veldencatalogus-xlsx uit de iAsset-GUI. Het venster toont per veld of het ID gevonden of ontbreekt, of label of
   veldtype afwijkt en of het veld is ingeschakeld voor het subthema van elk objecttype (op naam gekoppeld; dat vraagt
   het catalogus-xlsx, een JSON bevat alleen subthema-ID's). Is er al een catalogus geladen, kies dan **Geladen
   catalogus gebruiken** of **Vergelijkingscatalogus kiezen…** (een apart bestand, bijv. het xlsx naast een geladen
   JSON, zodat veldtypeverschillen en subthemanamen worden gecontroleerd). Met **Exporteren…** sla je het rapport op als xlsx.
9. **Bestand → Bijgewerkt Excel-ontwerp importeren…** leest een handmatig verfijnd ontwerp in (bij voorkeur een
   export van dit programma) en toont het als huidig ontwerp. De tabbladen verschijnen in iAsset-stijl, met
   kolombreedtes uit Excel. Het tabblad **Vergelijking** zet de import naast een vers uit de geladen specificatie
   gegenereerd ontwerp: toegevoegde, verwijderde, verplaatste en hernoemde velden per sectie, plus labels die niet in
   de specificatie staan. **Beeld → Wijzigingen markeren** omlijnt die velden in de mockup; dit staat standaard uit,
   zodat screenshots schoon blijven. **Bestand → Terug naar gegenereerd ontwerp** brengt je terug naar het
   gegenereerde ontwerp. Bij een ingelezen ontwerp kun je geen geselecteerde paspoorten samenvoegen en niet per
   objecttype exporteren.
10. **Bestand → Annotaties controleren/repareren…** controleert een verfijnd Excel-bestand tegen de specificatie:
    `(n)`-markeringen die niet kloppen, dubbele nummers, gaten en `Opmerkingen`-regels die niet kloppen. Alleen de
    markeringen bij Object informatie worden gecontroleerd. **Repareren → _fixed.xlsx** schrijft
    `<naam>_fixed.xlsx` met een eigen nummer per veld in leesvolgorde en de `Opmerkingen`-tekst naast de juiste
    regels. Opmaak en layout blijven ongewijzigd en het originele bestand verandert niet. Bevat het blad tekeningen,
    dan waarschuwt het programma.

### Aanbevolen werkwijze

1. Exporteer het Excel-ontwerp (**Bestand → Excel-ontwerp exporteren…**) en werk het uit in Excel.
2. Draai **Bestand → Annotaties controleren/repareren…** en gebruik de `_fixed.xlsx`-kopie.
3. Importeer het met **Bestand → Bijgewerkt Excel-ontwerp importeren…** en bekijk het tabblad **Vergelijking**.
4. Maak een screenshot met **Bestand → Mockup als PNG exporteren…** (markeren uit voor een schoon resultaat).

### Sneltoetsen

| Actie | Sneltoets |
|---|---|
| Veld-ID-bestand laden… | Ctrl+I |
| Veld-ID's controleren… | Ctrl+Shift+D |
| Bijgewerkt Excel-ontwerp importeren… | Ctrl+Shift+I |
| Annotaties controleren/repareren… | Ctrl+Shift+A |
| Geselecteerde paspoorten samenvoegen… | Ctrl+M |
| Excel-ontwerp exporteren… | Ctrl+E |
| Excel-ontwerp per objecttype exporteren… | Ctrl+Shift+E |
| Mockup als PNG exporteren… | Ctrl+P |

## Ontwerpprofielen

Kies een profiel via **Instellingen → Ontwerpprofiel**:

- **Rotterdam v3 (manually tuned)**, de standaard. Dit profiel volgt het handmatig verfijnde eindresultaat dat is
  beschreven in [`docs/analyse-handmatig-v3.md`](docs/analyse-handmatig-v3.md).
- **Original (Paspoortinrichting_obv_Filter)**. Dit is de indeling van het oorspronkelijke script: vier kolommen, een
  sectie "Beheer informatie" en notities onderaan.

### Hulpprogramma's voor de opdrachtregel

Vergelijk het gegenereerde ontwerp met een handmatig bewerkt Excel-bestand (recall en precisie per tabblad):

```text
python -m passport_designer.compare --spec wave1.xlsx --manual handmatig.xlsx
```

Haal de relatiesecties (Sem.Rel) uit zo'n bestand en schrijf ze naar
`passport_designer/data/rotterdam_v3_relations.json`:

```text
python tools/extract_relations.py handmatig.xlsx
```

## Aannames om te controleren op een testomgeving

De OpenAPI-specificatie van `POST /passport-tabs` noemt `field_type ∈ {0, 1, 2}`, maar legt niet uit wat de waarden
betekenen. Het programma gebruikt daarom deze standaardwaarden:

- een rij (bovenste niveau) krijgt `field_type` `1` en een veld (onderliggend niveau) krijgt `field_type` `0`;
- de `field_id` van een rij is `0`;
- `order` begint bij `1`;
- rijen zonder titel krijgen het onzichtbare label U+FE0F, net zoals iAsset dat zelf doet.

Je kunt deze waarden aanpassen via **Instellingen → Payload-instellingen…**. Controleer ze op een testomgeving
voordat je de payloads in productie gebruikt.

## Bekende beperkingen

- Bepalen welke velden in welk paspoort horen, blijft mensenwerk. Het programma toont liever te veel velden dan te
  weinig; jij haalt weg wat niet nodig is.
- Herhaalbare secties (Actoren, Memo) worden als één rij verstuurd. Zet ze daarna in iAsset op herhalen.
- Objecttypen zonder attributen in de brongegevens worden gemeld op het tabblad **Validatie**.

## Ontwikkelen

```text
pip install -r requirements-dev.txt
ruff check .
pyright
pytest
```

Elke push en pull request draait deze controles op GitHub Actions. Zodra een nieuwe versie (`__version__` in
`passport_designer/__init__.py`) op `main` staat, bouwt de workflow het Windows-programma en publiceert het automatisch
als release `v<versie>`.

Zie [CHANGELOG.md](CHANGELOG.md) voor de versiegeschiedenis.

## Licentie

GPL-3.0-or-later, zoals vereist door de GPL-voorwaarden van PyQt6 (dezelfde licentie als iAsset Syncer). Zie
[LICENSE](LICENSE).
