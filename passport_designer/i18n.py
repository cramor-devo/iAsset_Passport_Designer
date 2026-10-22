"""Vertaaltabel (EN/NL): alle zichtbare teksten staan hier, zodat taalwissel geen codewijziging vraagt.
Translation table (EN/NL): all user-visible strings live here, so switching language needs no code change."""

from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "app.title": {"en": "iAsset Passport Designer", "nl": "iAsset Passport Designer"},
    "menu.file": {"en": "&File", "nl": "&Bestand"},
    "menu.view": {"en": "&View", "nl": "&Beeld"},
    "menu.settings": {"en": "&Settings", "nl": "&Instellingen"},
    "menu.help": {"en": "&Help", "nl": "&Help"},
    "menu.language": {"en": "Language", "nl": "Taal"},
    "menu.profile": {"en": "Design profile", "nl": "Ontwerpprofiel"},
    "menu.theme": {"en": "Mockup theme", "nl": "Mockup-thema"},
    "theme.dark": {"en": "Dark", "nl": "Donker"},
    "theme.light": {"en": "Light", "nl": "Licht"},
    "action.open": {"en": "&Open specification(s)…", "nl": "Specificatie(s) &openen…"},
    "action.add": {"en": "&Add specification…", "nl": "Specificatie &toevoegen…"},
    "action.load_ids": {"en": "Load field &ID file…", "nl": "Veld-&ID-bestand laden…"},
    "action.export_excel": {"en": "Export &Excel design…", "nl": "&Excel-ontwerp exporteren…"},
    "action.export_png": {"en": "Export mockup as &PNG…", "nl": "Mockup als &PNG exporteren…"},
    "action.save_payload": {"en": "&Save payload…", "nl": "Payload op&slaan…"},
    "action.save_all_payloads": {"en": "Save &all payloads…", "nl": "&Alle payloads opslaan…"},
    "action.quit": {"en": "&Quit", "nl": "&Afsluiten"},
    "action.payload_settings": {"en": "&Payload settings…", "nl": "&Payload-instellingen…"},
    "action.about": {"en": "&About", "nl": "&Over"},
    "action.copy": {"en": "Copy to clipboard", "nl": "Kopieer naar klembord"},
    "panel.filters": {"en": "Filters (passport tabs)", "nl": "Filters (paspoorttabbladen)"},
    "panel.object_type": {"en": "Preview object type:", "nl": "Voorbeeld-objecttype:"},
    "panel.only_flagged": {
        "en": "Only attributes marked for the passport",
        "nl": "Alleen attributen die in het paspoort getoond worden",
    },
    "panel.only_flagged_tip": {
        "en": "Skips attributes that are 'Nee' in 'In paspoort tonen' / 'Opnemen'.",
        "nl": "Slaat attributen over die op 'Nee' staan bij 'In paspoort tonen' / 'Opnemen'.",
    },
    "tab.mockup": {"en": "Mockup", "nl": "Mockup"},
    "tab.payload": {"en": "API payload", "nl": "API-payload"},
    "tab.validation": {"en": "Validation", "nl": "Validatie"},
    "payload.format": {"en": "Format:", "nl": "Formaat:"},
    "payload.fmt_json": {"en": "JSON (readable)", "nl": "JSON (leesbaar)"},
    "payload.fmt_compact": {"en": "JSON (one line)", "nl": "JSON (één regel)"},
    "payload.fmt_form": {"en": "Form fields (Laravel)", "nl": "Formuliervelden (Laravel)"},
    "payload.hint": {
        "en": "Paste the JSON body into iAsset Syncer → API Explorer → V2 → POST /passport-tabs.",
        "nl": "Plak de JSON-body in iAsset Syncer → API Explorer → V2 → POST /passport-tabs.",
    },
    "payload.summary": {
        "en": "{resolved} of {total} fields have an iAsset field ID.",
        "nl": "{resolved} van {total} velden hebben een iAsset veld-ID.",
    },
    "payload.empty": {"en": "Open a specification to start.", "nl": "Open een specificatie om te beginnen."},
    "mock.archive": {"en": "Archive", "nl": "Archief"},
    "mock.log": {"en": "Log", "nl": "Logboek"},
    "mock.notes": {"en": "Notes / Exceptions", "nl": "Notities / Uitzonderingen"},
    "mock.applies_to": {"en": "Applies to: {types}", "nl": "Geldt voor: {types}"},
    "mock.not_for_type": {
        "en": "Not applicable to {type}. Applies to: {types}",
        "nl": "Niet van toepassing op {type}. Geldt voor: {types}",
    },
    "mock.edit": {"en": "Edit", "nl": "Bewerken"},
    "mock.delete": {"en": "Delete", "nl": "Verwijderen"},
    "mock.print": {"en": "Print", "nl": "Afdrukken"},
    "mock.more": {"en": "More", "nl": "Meer"},
    "mock.fullscreen": {"en": "Full screen", "nl": "Volledig scherm"},
    "mock.close": {"en": "Close", "nl": "Sluiten"},
    "status.ready": {"en": "Ready.", "nl": "Klaar."},
    "status.loading": {"en": "Loading {name}…", "nl": "{name} laden…"},
    "status.loaded": {
        "en": "Loaded {files} file(s): {filters} filters, {types} object types.",
        "nl": "{files} bestand(en) geladen: {filters} filters, {types} objecttypen.",
    },
    "status.ids_loaded": {
        "en": "{count} field IDs loaded from {name}.",
        "nl": "{count} veld-ID's geladen uit {name}.",
    },
    "status.saved": {"en": "Saved: {path}", "nl": "Opgeslagen: {path}"},
    "status.copied": {"en": "Copied to clipboard.", "nl": "Gekopieerd naar klembord."},
    "dialog.open_spec": {"en": "Open specification", "nl": "Specificatie openen"},
    "dialog.add_spec": {"en": "Add specification", "nl": "Specificatie toevoegen"},
    "dialog.load_ids": {"en": "Load field ID file", "nl": "Veld-ID-bestand laden"},
    "dialog.save_excel": {"en": "Save Excel design", "nl": "Excel-ontwerp opslaan"},
    "dialog.save_png": {"en": "Save mockup", "nl": "Mockup opslaan"},
    "dialog.save_payload": {"en": "Save payload", "nl": "Payload opslaan"},
    "dialog.save_folder": {
        "en": "Choose a folder for the payload files",
        "nl": "Kies een map voor de payload-bestanden",
    },
    "dialog.filter_xlsx": {"en": "Excel files (*.xlsx *.xlsm)", "nl": "Excel-bestanden (*.xlsx *.xlsm)"},
    "dialog.filter_ids": {
        "en": "Field ID files (*.json *.csv *.xlsx)",
        "nl": "Veld-ID-bestanden (*.json *.csv *.xlsx)",
    },
    "dialog.filter_png": {"en": "PNG image (*.png)", "nl": "PNG-afbeelding (*.png)"},
    "dialog.filter_json": {"en": "JSON (*.json);;Text (*.txt)", "nl": "JSON (*.json);;Tekst (*.txt)"},
    "error.title": {"en": "Something went wrong", "nl": "Er ging iets mis"},
    "error.read_spec": {
        "en": "The specification could not be read:\n{detail}\n\nDetails are in the log file.",
        "nl": "De specificatie kon niet worden gelezen:\n{detail}\n\nDetails staan in het logbestand.",
    },
    "error.read_ids": {
        "en": "The field ID file could not be read:\n{detail}",
        "nl": "Het veld-ID-bestand kon niet worden gelezen:\n{detail}",
    },
    "error.write": {
        "en": "The file could not be written:\n{detail}",
        "nl": "Het bestand kon niet worden geschreven:\n{detail}",
    },
    "error.nothing": {"en": "Open a specification first.", "nl": "Open eerst een specificatie."},
    "settings.title": {"en": "Payload settings", "nl": "Payload-instellingen"},
    "settings.theme_id": {"en": "Theme ID (-1 = all themes)", "nl": "Thema-ID (-1 = alle thema's)"},
    "settings.group_type": {"en": "field_type of a row", "nl": "field_type van een rij"},
    "settings.field_type": {"en": "field_type of a field", "nl": "field_type van een veld"},
    "settings.group_id": {"en": "field_id of a row", "nl": "field_id van een rij"},
    "settings.order_start": {"en": "First order number", "nl": "Eerste volgnummer"},
    "settings.note": {
        "en": "The API spec does not document these codes (field_type is 0, 1 or 2). Verify them on a test system.",
        "nl": "De API-spec beschrijft deze codes niet (field_type is 0, 1 of 2). Controleer ze op een testomgeving.",
    },
    "about.title": {"en": "About", "nl": "Over"},
    "about.text": {
        "en": "Turns IMBOR/object type specifications (xlsx) into passport designs, mockups and "
        "POST /passport-tabs strings for iAsset Syncer.\nVersion {version} · GPL-3.0-or-later.",
        "nl": "Zet IMBOR-/objecttypespecificaties (xlsx) om in paspoortontwerpen, mockups en "
        "POST /passport-tabs-strings voor iAsset Syncer.\nVersie {version} · GPL-3.0-or-later.",
    },
    "sev.info": {"en": "Info", "nl": "Info"},
    "sev.warning": {"en": "Warning", "nl": "Waarschuwing"},
    "sev.error": {"en": "Error", "nl": "Fout"},
    "validation.ok": {"en": "No issues.", "nl": "Geen meldingen."},
    "tab.merge": {"en": "Merge suggestions", "nl": "Samenvoegadvies"},
    "merge.threshold": {"en": "Minimum similarity:", "nl": "Minimale gelijkenis:"},
    "merge.same_group": {"en": "Same management group only", "nl": "Alleen binnen dezelfde beheergroep"},
    "merge.same_group_tip": {
        "en": "Only suggest merging filters that share the same management group (Groep).",
        "nl": "Stel alleen filters voor samenvoegen voor die dezelfde beheergroep (Groep) delen.",
    },
    "merge.hint": {
        "en": "Filters (search filters) in the same group with similar attributes can share one passport. Fields that "
        "do not apply to all object types get a footnote: enable those per sub-theme in iAsset. "
        "Similarity = shared attributes ÷ all attributes (Jaccard).",
        "nl": "Filters (zoekfilters) in dezelfde groep met vergelijkbare attributen kunnen één paspoort delen. Velden "
        "die niet voor alle objecttypen gelden krijgen een voetnoot: schakel die in iAsset per subthema in. "
        "Gelijkenis = gedeelde attributen ÷ alle attributen (Jaccard).",
    },
    "merge.col.name": {"en": "Merged passport / filter", "nl": "Samengevoegd paspoort / filter"},
    "merge.col.similarity": {"en": "Similarity", "nl": "Gelijkenis"},
    "merge.col.types": {"en": "Object types", "nl": "Objecttypen"},
    "merge.col.fields": {"en": "Fields", "nl": "Velden"},
    "merge.col.fit": {"en": "Fit", "nl": "Pasvorm"},
    "merge.fields_fmt": {
        "en": "{common} common + {partial} per sub-theme",
        "nl": "{common} gemeenschappelijk + {partial} per subthema",
    },
    "merge.low_fit_tip": {
        "en": "At least one filter uses less than half of the merged fields.",
        "nl": "Minstens één filter gebruikt minder dan de helft van de samengevoegde velden.",
    },
    "merge.summary": {
        "en": "{count} suggestion(s); merging them saves {saved} passport(s).",
        "nl": "{count} suggestie(s); samenvoegen bespaart {saved} paspoort(en).",
    },
    "merge.none": {
        "en": "No merge suggestions at this similarity.",
        "nl": "Geen samenvoegsuggesties bij deze gelijkenis.",
    },
    "merge.preview": {"en": "Preview merged passport", "nl": "Voorbeeld samengevoegd paspoort"},
    "merge.apply": {"en": "Apply merge", "nl": "Samenvoegen toepassen"},
    "merge.reset": {"en": "Undo all merges", "nl": "Alle samenvoegingen ongedaan maken"},
    "merge.export": {"en": "Export merge matrix…", "nl": "Samenvoegmatrix exporteren…"},
    "merge.previewing": {"en": "Preview of {name} (not applied).", "nl": "Voorbeeld van {name} (niet toegepast)."},
    "merge.applied": {"en": "Merged into {name}.", "nl": "Samengevoegd tot {name}."},
    "merge.reset_done": {"en": "All merges undone.", "nl": "Alle samenvoegingen ongedaan gemaakt."},
    "dialog.save_merge": {"en": "Save merge matrix", "nl": "Samenvoegmatrix opslaan"},
}

LANGUAGES: dict[str, str] = {"en": "English", "nl": "Nederlands"}


class Translator:
    """Houdt de gekozen taal bij en zoekt teksten op. / Keeps the chosen language and looks up strings."""

    def __init__(self, language: str = "en") -> None:
        self.language = language if language in LANGUAGES else "en"

    def set_language(self, language: str) -> None:
        if language in LANGUAGES:
            self.language = language

    def __call__(self, key: str, **values: object) -> str:
        entry = TRANSLATIONS.get(key)
        text = key if entry is None else entry.get(self.language, entry["en"])
        return text.format(**values) if values else text


translator = Translator()
tr = translator
