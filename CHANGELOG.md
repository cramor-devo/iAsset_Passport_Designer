# Changelog

## Unreleased
- Release workflow: publishing a GitHub release builds the exe on `windows-latest` (after ruff and pytest) and attaches
  the exe and its SHA256 file to the release; can be re-run manually for a tag.
- Copilot cloud agent environment (`copilot-setup-steps.yml`): Ubuntu with Python, Qt system libraries and the dev
  dependencies in `.venv`.

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
