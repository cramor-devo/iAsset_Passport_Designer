# iAsset Passport Designer

**English** · [Nederlands](README.nl.md)

iAsset Passport Designer turns IMBOR object type specifications (xlsx, Wave 1 and Wave 2) into three things:

- a **passport design** for each filter,
- a **visual mockup** of the passport in iAsset style,
- **`POST /passport-tabs` payloads** that you can send to the iAsset V2 API with
  [iAsset Syncer](https://github.com/cramor-devo/iAsset_Syncer).

The interface is available in English and Dutch (**View → Language**).

## Requirements

- Python 3.11 or newer
- PyQt6 6.11.0 (GPL-3.0)
- openpyxl 3.1.5 (MIT), used to read and write xlsx files

## Download (Windows)

Download `iAsset Passport Designer vX.Y.Z.exe` (for example `iAsset Passport Designer v0.5.0.exe`) from the latest [release](../../releases). It is a single file and does not
need Python. The executable is not code-signed, so Windows SmartScreen may show a warning the first time you start it.

To build the executable yourself, run:

```text
powershell -ExecutionPolicy Bypass -File build.ps1
```

The result is written to `dist\iAsset Passport Designer vX.Y.Z.exe`, where the version is read from `__version__`. The
window title shows the same version.

### Releasing

You do not need to build locally to release. Set `__version__` in `passport_designer/__init__.py` and update
`CHANGELOG.md`. Merging that to `main` is enough: the **CI and release** workflow builds the exe and publishes release
`v<version>` (see [Development](#development)).

You can also publish a GitHub release yourself with tag `vX.Y.Z` (matching the version). The **Release** workflow then
runs the tests on `windows-latest`, builds the exe with `build.ps1` and attaches `iAsset Passport Designer vX.Y.Z.exe` and
`iAsset Passport Designer vX.Y.Z.exe.sha256` to that release. To rebuild or add the SHA256 file to an existing release, run
it manually (**Actions → Release → Run workflow**) with its tag.

## Installation from source

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The log file is stored at `%LOCALAPPDATA%\iAssetPassportDesigner\passport_designer.log`.

## Usage

1. Choose **File → Open Unafact specification(s)…** and select one or more xlsx files. Use **Add Unafact specification…** to add
   another file to what is already loaded, for example Wave 2 on top of Wave 1. Each file needs an `Objecttypen` sheet
   (column Objecttype plus Filter, Zoekfilter or Fase; optionally Groep) and an `Attributen` sheet (columns
   Objecttype, Attribuut).
2. Under **Filter column (Objecttypen)** at the top left, choose which column of the `Objecttypen` sheet groups the
   object types into passports, for example `Filter`/`Zoekfilter` in Wave 1 or `Fase` in Wave 2. By default the
   designer uses Filter, then Zoekfilter, then Fase; your choice is remembered. Changing it undoes applied merges.
3. Pick a filter and a preview object type on the left. **All object types** shows the whole passport; when you pick
   a single object type, fields that do not apply to it are **hidden**. The **Mockup** tab shows the passport as it
   will look in iAsset; switch between a dark and a light theme under **View → Mockup theme**. The **Design sheet** tab
   shows exactly what the Excel export writes, laid out like the passport design workbook: the title, the object
   types below it, grey (and light blue for Sem.Rel) section headings, an empty column and the `Opmerkingen`
   reference list for fields that do not apply to every object type.
   **View → Only fields with Opnemen = "Ja"** (**Ctrl+Alt+O**, also the checkbox above the views) is on by default and
   leaves out the fields that are `Opnemen = "Nee"` in the specification. Turn it off to see all fields; those with
   `Opnemen = "Nee"` are then shown in grey italic in the mockup, the design sheet and the Excel exports (with `only_included`
   set to `false` in the `_designer` sheet). The setting is remembered.
   **View → Highlight minimal dataset** (**Ctrl+Shift+M**, also a checkbox above the views; off by default, remembered;
   disabled when the specification has no `MinimaleDataset` column) shades the minimal-dataset fields: **green** when
   the field is in the minimal dataset of all object types of the passport, **the colour of that object type** when
   it is for one type only, and **stripes** of those types' colours for several types. A legend (the object-type names in
   their colours plus *All types* in green) appears under the header, and the tooltip names the types. The shades and
   legend are also written to the PNG and the Excel exports while the toggle is on.
   **Fields to verify with the customer:** in the Design sheet tab, select fields and choose **Edit → Mark: verify with
   customer** (**Ctrl+Shift+V**, also in the right-click menu). They turn red in the views, the PNG and the Excel exports
   (tooltip *Verify with customer*) and stay in the payload. **Edit → Delete field** (**Del**), **Delete all fields
   marked for verification** (asks first) and **Restore deleted fields…** remove or bring back fields; **Ctrl+Z**
   undoes the last change. Deleted fields leave the payload, the views and the exports and are listed on the Validation
   tab; fields in repeatable sections cannot be deleted. **View → Show "verify with customer" marks** hides the red
   colour. Importing a refined Excel recognises red text and the green fill `92D050` as marks. Marks and deletions are
   not remembered between sessions yet.
   **Design profiles:** *Rotterdam v3* has at most 5 fields per row and includes *Gekoppelde objecten (Sem.Rel)*,
   *Inwinningsinformatie (Sem.Rel)*, a *Datum* column in Memo, *Distributiegebied*/*Stroomgebied* in Locatie informatie
   and *Beheerobjectomschrijving* in Overige informatie. When importing a refined Excel, text beside the grid is read as
   a remark, section titles are normalised (with a warning), placeholder rows (`..., etc.`, `.....`) are skipped, `**`
   is linked to its remark and rows with more than 5 fields give a warning. Object types that have attributes but no
   row in Objecttypen are listed on the Validation tab.
4. The **Merge suggestions** tab proposes filters that could share a single passport, based on the same management
   group and similar attributes (Jaccard similarity). Fields that do not apply to every object type get a footnote:
   these are the fields you switch on or off per sub-theme in iAsset. Use **Preview merged passport** to inspect a
   suggestion, **Apply merge** to merge the filters, and **Export merge matrix…** to save a field × object type matrix.
   You can also merge by hand: select two or more passports in the list (Ctrl/Shift+click) and choose **File → Merge
   selected passports…** (**Ctrl+M**, also in the context menu and as **Merge selected…** on the Merge tab). This works
   whatever the filter, group or advisor threshold. Enter a name for the new passport (required, at most 50
   characters, unique). If the passports differ in management group or filter, the dialog lists the differences and you
   must confirm explicitly (Cancel is the default). A manual merge can be undone like any other merge and is not
   available while an imported design is shown.
5. Choose **File → Load passport field ID file…** to load the V2 passport diverse-fields list (e.g. `passport field list.csv`, semicolon CSV with
   `id;label;name;type;values;…`; JSON and xlsx with label/name and id also work). Each passport field gets the `id`
   of the diverse field with the same label. The iAsset GUI field catalog (xlsx with the sheets `Paspoort velden` and
   `Thema Subthema`) is accepted as well. Without field IDs, `field_id` is set to `null` and the **Validation** tab
   reports an error.
6. On the **API payload** tab, copy the payload or save it to a file. Paste the JSON into iAsset Syncer → API Explorer
   → V2 → `POST /passport-tabs`. Syncer sends it as multipart form data (`fields[0][children][1][label]`); the
   **Form fields (Laravel)** format shows the same fields in that form.
7. **File → Export Excel design…** writes one sheet per passport. **File → Export Excel design per object type…**
   writes one sheet per object type without the fields that do not apply to it. **File → Export mockup as PNG…**
   saves the mockup (as shown in the preview) as an image. Every Excel export also contains the reference sheets
   `Bron Objecttypen` and `Bron Attributen` (the spec rows of the exported object types, with source file and date) and
   a hidden `_designer` sheet with metadata (version, profile, spec files, filter column, tab → object types).
8. **File → Check field IDs…** checks the passport fields against the field IDs you loaded, **offline**: the app
   never calls iAsset. Load a saved V2 `GET /diverse-fields` JSON or the iAsset GUI field catalog xlsx first. The
   dialog shows per field whether the ID is found or missing, whether label or field type differ, and whether the
   field is enabled for the sub-theme of each object type (matched by name; this needs the catalog xlsx, a JSON only
   has sub-theme IDs). With a catalog already loaded you can choose **Use loaded catalog** or **Choose comparison
   catalog…** (a separate file, e.g. the xlsx next to a loaded JSON, so field-type differences and sub-theme names are
   checked). **Export…** saves the report as xlsx.
9. **File → Import refined Excel…** reads a manually refined design (preferably one exported by this tool) and shows
   it as the current design. The sheets are shown in iAsset style, with column widths taken from Excel. The
   **Cross-reference** tab compares the import with a design freshly generated from the loaded specification: added,
   removed, moved and renamed fields per section, plus labels that are not in the specification. **View → Highlight
   changes** outlines these fields in the mockup; it is off by default, so screenshots stay clean. **File → Back to
   generated design** returns to the generated design. While an imported design is shown, merging selected passports
   and exporting per object type are unavailable.
10. **File → Check/fix annotations…** checks a refined Excel file against the specification: `(n)` markers that do not
    match, duplicates, gaps and `Opmerkingen` rows that do not match. Only the Object informatie markers are checked.
    **Fix → _fixed.xlsx** writes `<name>_fixed.xlsx` with its own number for each field in reading order and the
    `Opmerkingen` text beside the right rows. Layout and styling stay untouched and the original file is not changed.
    The tool warns if the sheet contains drawings.

### Recommended workflow

1. Export the Excel design (**File → Export Excel design…**) and refine it in Excel.
2. Run **File → Check/fix annotations…** and use the `_fixed.xlsx` copy.
3. Import it with **File → Import refined Excel…** and review the **Cross-reference** tab.
4. Take a screenshot with **File → Export mockup as PNG…** (highlighting off for a clean result).

### Keyboard shortcuts

| Action | Shortcut |
|---|---|
| Load passport field ID file… | Ctrl+I |
| Check field IDs… | Ctrl+Shift+D |
| Import refined Excel… | Ctrl+Shift+I |
| Check/fix annotations… | Ctrl+Shift+A |
| Merge selected passports… | Ctrl+M |
| Export Excel design… | Ctrl+E |
| Export Excel design per object type… | Ctrl+Shift+E |
| Export mockup as PNG… | Ctrl+P |
| Only fields with Opnemen = "Ja" (View menu) | Ctrl+Alt+O |
| Highlight minimal dataset (View menu) | Ctrl+Shift+M |
| Mark: verify with customer (Edit menu) | Ctrl+Shift+V |
| Delete field / Undo field change (Edit menu) | Del / Ctrl+Z |

## Design profiles

Choose a profile under **Settings → Design profile**:

- **Rotterdam v3 (manually tuned)**, the default. It follows the manually refined end result described in
  [`docs/analyse-handmatig-v3.md`](docs/analyse-handmatig-v3.md).
- **Original (Paspoortinrichting_obv_Filter)**. This is the layout of the original script: four columns, a
  "Beheer informatie" section and notes at the bottom.

### Command-line tools

Compare the generated design with a manually edited workbook (recall and precision per sheet):

```text
python -m passport_designer.compare --spec wave1.xlsx --manual handmatig.xlsx
```

Extract the relation sections (Sem.Rel) from such a workbook into
`passport_designer/data/rotterdam_v3_relations.json`:

```text
python tools/extract_relations.py handmatig.xlsx
```

## Payload codes (verified)

The payload structure matches what iAsset really stores, verified against a real `GET /templates/tabs` response:

- sections are layout elements (`field_type` `2`): row/section `10` (continuation rows get the invisible label
  U+FE0F), horizontal line `1`, *Actoren en rollen* `11`, *Memo* / *Is beschreven door* `19`, relations `17`–`27`
  (default `18` *Is verbonden met*; *Constructielagen* is `23` *Bestaat uit*), *Geometrie* `4`, *iASSET-id* `16`;
- fields are system fields (`field_type` `0`: Nummer 1, Naam 2, Thema 3, Subthema 4, Rds coordinaten 23) or diverse
  fields (`field_type` `1`, ID from the field ID file);
- a horizontal line is placed between consecutive sections; *iASSET-id* is its own element at the very end;
- `order` starts at `1` and counts top-level items (lines included) and children separately;
- relation sections that cannot be recognised are sent as *Is verbonden met* with an INFO message.

All codes (and the lines) are configurable under **Settings → Payload settings…**. Per-template visibility is set
with `POST/PATCH /templates`, not in this payload.

## Known limitations

- Deciding which fields belong in each passport is still a human task. The designer errs on the side of showing too
  many fields rather than too few, so you only need to remove what is not needed.
- Relation, Memo and Actoren sections are sent as iAsset elements; the sample rows of the design are not sent.
- Object types without attributes in the source data are reported on the **Validation** tab.

## Development

```text
pip install -r requirements-dev.txt
ruff check .
pyright
pytest
```

Every push and pull request runs these checks on GitHub Actions. When a new version (`__version__` in
`passport_designer/__init__.py`) reaches `main`, the workflow builds the Windows executable and publishes it as release
`v<version>` automatically.

See [CHANGELOG.md](CHANGELOG.md) for the version history.

## Licence

GPL-3.0-or-later, as required by the GPL terms of PyQt6 (the same licence as iAsset Syncer). See [LICENSE](LICENSE).
