# Changelog

## 0.5.1 - 2026-11-17
- Added: **rename a passport.** Select it and press **F2**, double-click it, or use right-click → **Rename passport…** or **Edit → Rename passport…**. The name must be unique (case-insensitive, also against other passports; a duplicate is blocked) and at most 50 characters; a name longer than 31 characters or with `[]:*?/\` is shortened as an Excel sheet name, with a note in the dialog. Marks, deletions and layout move with the passport (and are stored under the generated name, so they are found again on the next start); the Mockup, Design sheet, payload, Excel, PNG and bulk exports use the new name. A renamed passport shows ✎ and its original name in the tooltip; **Reset passport name** (context menu) restores it. Renaming a merged passport changes the name of the merge. Renames are session-only, like merges, and are cleared when new specifications are opened or the filter column changes.
- Added: on the **Merge suggestions** tab, **Rename suggestion…** (button and right-click menu with Preview / Rename / Apply) changes the name before you apply a merge. The chosen name is kept while the suggestions stay the same and is dropped when the threshold or same-group option changes.
- Changed: menus. **Merge selected passports…** (Ctrl+M) moved from File to Edit, next to the new **Rename passport…**; **Check field IDs…** and **Check/fix annotations…** moved from File to the new **Tools** menu (Dutch: **Controle**); **Undo/Redo** are now at the top of Edit. Shortcuts are unchanged.
- Added: a search box above the passport list, and a tooltip with the full name and number of object types.
- Changed: Undo/Redo name the action in the menu (e.g. **Undo rename**, **Undo field change**) and the status bar confirms it. Undo also covers renames.

## 0.5.0
- Added: **Bulk export** tab (the 7th tab) writes many PNGs in one go. Check passports (one image of the whole passport, named after the tab, e.g. `Dragers.png`) and/or object types (named after the type, e.g. `Persleiding.png`), filter the list, and choose the folder for passport images and the folder for object type images (remembered). A name that already exists in the run gets the tab in brackets (`Persleiding (Dragers).png`). Options: dark/light theme, only fields with Opnemen = "Ja", highlight minimal dataset, "verify with customer" marks and extra tabs; they start from the current view but never change it. Every image equals what **Export mockup as PNG** gives for the same selection and includes your layout changes and deletions. A progress bar with **Cancel** keeps the files already written; existing files ask first (**Overwrite all / Skip existing / Cancel**); errors per image are listed in the end report with **Open folder**. Exporting the Design sheet as PNG is not included yet.
- Added: **drag and drop in the Design sheet.** Drag a field to another place in its row, another row or another section (dropping on a section heading appends it; dropping on an empty row fills it). Right-click: **Insert empty row above/below**, **New section below…** (with a title and style), **Rename section…**, **Delete empty row** and **Reset order of this passport**. A row holds at most 5 fields; repeatable sections and Notes can only be moved as a whole. The Design sheet is leading: the mockup, the PNG, the Excel exports and the API payload all follow it (an empty row is skipped in the payload, a new section becomes a group with its title; footnotes are renumbered). **Edit → Redo field change** (Ctrl+Y) and Undo work for moves. The layout is saved automatically per passport and specification, and **File → Save layout… / Load layout…** share it as JSON; fields that are no longer in the specification are reported on the Validation tab. Dragging is off while a single object type is selected. The `_designer` sheet records the layout (`layout`), which a refined import reads back.
- Added: **View → Highlight minimal dataset** (Ctrl+Shift+M, also a checkbox above the views, off by default). Minimal-dataset
  fields get a green shade (all object types of the passport), the colour of their object type, or stripes (several
  types), in the mockup, the design sheet, the PNG and the Excel exports, with a legend of the object-type colours. The
  `_designer` sheet records `minimal_dataset_shown`. Excel stripes use a gradient fill; their rendering in Excel is unverified.
- Added: **Fields to verify with the customer.** In the Design sheet tab, select fields and use **Edit → Mark: verify with customer** (Ctrl+Shift+V, or the context menu): they turn red (also in the PNG and the Excel exports, with a tooltip). **Edit → Delete field** (Del), **Delete all fields marked for verification** (asks first) and **Restore deleted fields…** change the passport; **Undo field change** (Ctrl+Z) steps back. Marked fields stay in the payload until deleted; deleted fields are removed from the payload, the views and the exports and are listed on the Validation tab. Fields in repeatable sections cannot be deleted. **View → Show "verify with customer" marks** hides the red colour. A refined Excel import recognises red text and the green fill `92D050` as marks; the `_designer` sheet records `verify` and `deleted`. Marks, deletions and the layout are saved per passport and per specification (next to the settings) and restored on the next start.
- Changed: the **Rotterdam v3** profile follows the refined Wave 2 workbook: new sections *Gekoppelde objecten (Sem.Rel)* and *Inwinningsinformatie (Sem.Rel)*, a *Datum* column in Memo, *Distributiegebied* and *Stroomgebied* in Locatie informatie, *Beheerobjectomschrijving* in Overige informatie (no *clusternummer*), and *Borden aan drager* for Waterinrichtingsobject. Rows never hold more than 5 fields. Every new export therefore differs from earlier ones.
- Fixed: importing a refined Excel no longer reads remark text beside the grid as a field, normalises section titles that differ only in brackets or suffix (with a warning), skips placeholder rows (`..., etc.`, `.....`), links `**` to its remark and warns for rows with more than 5 fields. Object types with attributes but no row in Objecttypen are reported on the Validation tab.
- Changed: the Opnemen toggle ("Only fields with Opnemen = Ja") is now in **View** (shortcut Ctrl+Alt+O) and as a
  checkbox above the views, instead of in the left panel. With the toggle off, fields with Opnemen = Nee are shown in
  grey italic in the mockup, the design sheet and the Excel export. The `_designer` sheet records `only_included`.
- Changed: the Opnemen and MinimaleDataset flags are read per attribute from the specification (not only for the
  first object type); when two specification files disagree, the later file wins and a warning is logged.
- Changed: clearer File-menu labels: *Open Unafact specification(s)…*, *Add Unafact specification…* and *Load passport
  field ID file…* (Dutch: *Unafact-specificatie(s) openen…*, *Unafact-specificatie toevoegen…*, *Paspoort-veld-ID-bestand
  laden…*). The shortcuts are unchanged.
- Fixed: with Windows in dark mode, the light theme showed black tab headers. The chosen theme now sets the colours of
  the whole window (palette, Fusion style, tab headers, table headers, menu bar, status bar and scrollbars), so the
  dark and light themes look the same whatever Windows uses. Controls such as checkboxes and combo boxes now use the
  Fusion style and may look slightly different from before.
- Changed: the exe is named `iAsset_Passport_Designer_vX.Y.Z.exe` (underscores instead of spaces, plus the version), and so are its SHA256
  file and the release assets. The window title shows the version too. Old download links to
  `iAsset_Passport_Designer.exe` and `releases/latest/download/...` no longer work. The app name, saved settings and log
  folder are unchanged.

## 0.4.0
- The `POST /passport-tabs` payload now matches what iAsset really stores (verified against a real `GET /templates/tabs`):
  layout elements (`field_type` 2: row 10, line 1, *Actoren en rollen* 11, *Memo* 19, relations 17–27 incl.
  *Constructielagen* 23, *Geometrie* 4, *iASSET-id* 16), system fields (`field_type` 0) and diverse fields
  (`field_type` 1), a horizontal line between sections (switchable), *iASSET-id* as its own last element, no footnote
  numbers in labels. New settings are stored under new keys, so old saved defaults no longer apply.
- The mockup shows every relation element (not only *Memo*) as an iAsset linked-object table: link buttons, search
  boxes and *Alle* dropdowns (Thema, Subthema, Objecttype), three sample rows with checkboxes, and a pager; *Memo*
  keeps the empty state.
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
