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

Download `iAsset_Passport_Designer.exe` from the latest [release](../../releases). It is a single file and does not
need Python. The executable is not code-signed, so Windows SmartScreen may show a warning the first time you start it.

To build the executable yourself, run:

```text
powershell -ExecutionPolicy Bypass -File build.ps1
```

The result is written to `dist\iAsset_Passport_Designer.exe`.

### Releasing

You do not need to build locally to release. Set `__version__` in `passport_designer/__init__.py` and update
`CHANGELOG.md`. Merging that to `main` is enough: the **CI and release** workflow builds the exe and publishes release
`v<version>` (see [Development](#development)).

You can also publish a GitHub release yourself with tag `vX.Y.Z` (matching the version). The **Release** workflow then
runs the tests on `windows-latest`, builds the exe with `build.ps1` and attaches `iAsset_Passport_Designer.exe` and
`iAsset_Passport_Designer.exe.sha256` to that release. To rebuild or add the SHA256 file to an existing release, run
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

1. Choose **File → Open specification(s)…** and select one or more xlsx files. Use **Add specification…** to add
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
4. The **Merge suggestions** tab proposes filters that could share a single passport, based on the same management
   group and similar attributes (Jaccard similarity). Fields that do not apply to every object type get a footnote:
   these are the fields you switch on or off per sub-theme in iAsset. Use **Preview merged passport** to inspect a
   suggestion, **Apply merge** to merge the filters, and **Export merge matrix…** to save a field × object type matrix.
5. Choose **File → Load field ID file…** to load an export of `GET /diverse-fields` (JSON, CSV or xlsx with the columns
   label/name and id). Without field IDs, `field_id` is set to `null` and the **Validation** tab reports an error.
6. On the **API payload** tab, copy the payload or save it to a file. Paste the JSON into iAsset Syncer → API Explorer
   → V2 → `POST /passport-tabs`. Syncer sends it as multipart form data (`fields[0][children][1][label]`); the
   **Form fields (Laravel)** format shows the same fields in that form.
7. **File → Export Excel design…** writes one sheet per passport. **File → Export Excel design per object type…**
   writes one sheet per object type without the fields that do not apply to it. **File → Export mockup as PNG…**
   saves the mockup (as shown in the preview) as an image.

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

## Assumptions to check on a test environment

The OpenAPI specification of `POST /passport-tabs` lists `field_type ∈ {0, 1, 2}` but does not say what the values
mean. The designer therefore uses these defaults:

- a row (top level) has `field_type` `1`, and a field (child) has `field_type` `0`;
- the `field_id` of a row is `0`;
- `order` starts at `1`;
- rows without a title get the invisible label U+FE0F, as iAsset itself does.

You can change these defaults under **Settings → Payload settings…**. Check them on a test environment before you
use the payloads in production.

## Known limitations

- Deciding which fields belong in each passport is still a human task. The designer errs on the side of showing too
  many fields rather than too few, so you only need to remove what is not needed.
- Repeating sections (Actoren, Memo) are sent as a single row. Set them to repeat in iAsset afterwards.
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
