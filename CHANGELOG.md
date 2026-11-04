# Changelog

## 0.4.0
- Import a manually refined Excel design (*File → Import refined Excel…*) and show it as an iAsset-style mockup with
  Excel-relative column widths. The *Cross-reference* panel compares it with a freshly generated design from the loaded
  specification (added, removed, moved and renamed fields per section, plus labels not in the spec); *View → Highlight
  changes* outlines them in the mockup (off by default, so screenshots stay clean). *Back to generated design* returns
  to the generated design (#10).
- The mockup is restyled after iAsset for all designs: view dropdown, tab bar, section titles, dark header band with
  centred labels and rounded value boxes (#10). Fields are centred: labels in the band and each value box under its
  label; repeatable sections (e.g. *Actoren en rollen*) show one header band with three sample rows, and *Memo* shows
  as a linked-object table with search boxes and pager.
- *Check/fix annotations…*: checks the `(n)` markers and `Opmerkingen` rows of a refined Excel file against the spec and
  writes a repaired `<name>_fixed.xlsx` (own number per field in reading order, layout and styling untouched, original
  file unchanged). Only Object informatie markers are checked; a warning appears when the sheet contains drawings (#11).
- Every Excel export contains the reference sheets `Bron Objecttypen` and `Bron Attributen` (raw spec rows for the
  exported object types, with source file and date) and a hidden `_designer` metadata sheet (version, profile, spec
  files, filter column, tab → object types) that the import uses when present (#12).
- *Check field IDs…*: offline check of the passport fields against a saved V2 `GET /diverse-fields` JSON or the iAsset
  GUI field catalog xlsx: ID found or missing, label and field-type mismatch, and enabled per subthema. Shown in a
  dialog and exportable to xlsx. With a catalog loaded you can pick a separate comparison catalog. The app never calls
  iAsset (#13).
- *Load field ID file…* also accepts the iAsset GUI field catalog xlsx (`Paspoort velden` plus `Thema Subthema`) (#14).
- *Merge selected passports…* (Ctrl+M): merge the selected passports regardless of filter, group or advisor threshold,
  with a name dialog and a confirmation when group or filter differ. Joins Undo/Reset, export and payload; disabled while
  an imported design is shown (#15).

## 0.3.1
- Field ID import now reads the V2 passport diverse-fields list (`passport field list.csv`): fixed CSV parsing of the
  large JSON `values` column (quoted newlines, `;` inside cells), so passport fields get their IDs from it.

## 0.3.0
- Release workflow: publishing a GitHub release builds the exe on `windows-latest` (after ruff and pytest) and attaches
  the exe and its SHA256 file to the release; can be re-run manually for a tag.
- Copilot cloud agent environment (`copilot-setup-steps.yml`): Ubuntu with Python, Qt system libraries and the dev
  dependencies in `.venv`.
- Application icon (iAsset Syncer style with a passport), used for windows, the taskbar and the exe
  (`passport_designer/assets`, regenerate ICO/PNG with `python tools/generate_app_icon.py`).
- Filter column selector: group/merge passports by any column of the `Objecttypen` sheet (e.g. `Fase` in Wave 2,
  `Filter`/`Zoekfilter` before). Default: Filter → Zoekfilter → Fase; the choice is remembered. A sheet only needs
  `Objecttype` plus one of these columns.
- Preview per object type hides the fields that do not apply to it (instead of dimming them); *All object types* shows
  the whole passport. The PNG export follows the preview.
- New *Design sheet* tab: shows exactly what the Excel export writes (title, object types below, grey/blue headings,
  empty column, `Opmerkingen` reference list for fields that do not apply to all object types).
- *Export Excel design per object type…*: one sheet per object type without the fields that do not apply to it.
- GitHub Actions: tests on every push/PR; on `main` a new version is built as Windows exe and released automatically.

## 0.2.0
- Single-file Windows executable (`iAsset_Passport_Designer.exe`, PyInstaller) and `build.ps1`.
- Design profile `rotterdam_v3` (default), modelled on the manually tuned Wave-1-v3 workbook: title/`Objecttypes` header,
  iAsset base fields, up to 5 fields per row, remarks column, Locatie/Beleid/Actoren/Memo/Overige/Geometrie sections and
  relation sections (`data/rotterdam_v3_relations.json`). The original layout remains available as profile `legacy`.
- Merge advisor: suggests filters that can share one passport (same management group, attribute similarity), with
  footnotes for fields that apply to only some object types (sub-theme settings in iAsset), preview/apply/undo and a
  field × object type matrix export.
- Comparison tool (`python -m passport_designer.compare`) against a manually tuned workbook; `tools/extract_relations.py`.
- Object types without attributes inherit from the type their name ends with (Piramideblok → Blok); remaining gaps are reported.
- Payload: repeating sections sent once, `*` marks removed from labels and reported.

## 0.1.0
- First version: xlsx specification reader (Wave 1/2), passport design, mockup, Excel export, `POST /passport-tabs` strings.
