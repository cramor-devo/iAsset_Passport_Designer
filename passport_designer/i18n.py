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
    "action.export_excel_types": {
        "en": "Export Excel design per object &type…",
        "nl": "Excel-ontwerp per object&type exporteren…",
    },
    "action.export_png": {"en": "Export mockup as &PNG…", "nl": "Mockup als &PNG exporteren…"},
    "action.save_payload": {"en": "&Save payload…", "nl": "Payload op&slaan…"},
    "action.save_all_payloads": {"en": "Save &all payloads…", "nl": "&Alle payloads opslaan…"},
    "action.quit": {"en": "&Quit", "nl": "&Afsluiten"},
    "action.payload_settings": {"en": "&Payload settings…", "nl": "&Payload-instellingen…"},
    "action.about": {"en": "&About", "nl": "&Over"},
    "action.copy": {"en": "Copy to clipboard", "nl": "Kopieer naar klembord"},
    "panel.filters": {"en": "Filters (passport tabs)", "nl": "Filters (paspoorttabbladen)"},
    "panel.object_type": {"en": "Preview object type:", "nl": "Voorbeeld-objecttype:"},
    "panel.all_types": {"en": "All object types", "nl": "Alle objecttypen"},
    "panel.filter_column": {"en": "Filter column (Objecttypen):", "nl": "Filterkolom (Objecttypen):"},
    "panel.filter_column_tip": {
        "en": "Column of the 'Objecttypen' sheet that groups object types into passports (e.g. Filter, Zoekfilter, "
        "Fase). Changing it undoes applied merges.",
        "nl": "Kolom van het tabblad 'Objecttypen' die objecttypen in paspoorten groepeert (bijv. Filter, Zoekfilter, "
        "Fase). Wijzigen maakt toegepaste samenvoegingen ongedaan.",
    },
    "panel.only_flagged": {
        "en": "Only attributes marked for the passport",
        "nl": "Alleen attributen die in het paspoort getoond worden",
    },
    "panel.only_flagged_tip": {
        "en": "Skips attributes that are 'Nee' in 'In paspoort tonen' / 'Opnemen'.",
        "nl": "Slaat attributen over die op 'Nee' staan bij 'In paspoort tonen' / 'Opnemen'.",
    },
    "tab.mockup": {"en": "Mockup", "nl": "Mockup"},
    "tab.sheet": {"en": "Design sheet", "nl": "Ontwerpblad"},
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
    "mock.edit": {"en": "Edit", "nl": "Bewerken"},
    "mock.delete": {"en": "Delete", "nl": "Verwijderen"},
    "mock.print": {"en": "Print", "nl": "Afdrukken"},
    "mock.more": {"en": "More", "nl": "Meer"},
    "mock.fullscreen": {"en": "Full screen", "nl": "Volledig scherm"},
    "mock.close": {"en": "Close", "nl": "Sluiten"},
    "status.ready": {"en": "Ready.", "nl": "Klaar."},
    "status.checking_ids": {"en": "Checking field IDs…", "nl": "Veld-ID's controleren…"},
    "status.fixing": {"en": "Repairing annotations…", "nl": "Annotaties herstellen…"},
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
    "action.merge_selected": {"en": "&Merge selected passports…", "nl": "Geselecteerde paspoorten &samenvoegen…"},
    "merge.selected": {"en": "Merge selected…", "nl": "Selectie samenvoegen…"},
    "merge.selected_tip": {
        "en": "Select two or more passports in the list (Ctrl/Shift+click) and merge them, whatever their filter.",
        "nl": "Selecteer twee of meer paspoorten in de lijst (Ctrl/Shift+klik) en voeg ze samen, ongeacht het filter.",
    },
    "merge.imported_disabled": {
        "en": "Merging is not available for an imported design. Choose 'Back to generated design' first.",
        "nl": "Samenvoegen kan niet bij een ingelezen ontwerp. Kies eerst 'Terug naar gegenereerd ontwerp'.",
    },
    "merge.not_applied": {
        "en": "Merge '{name}' was not applied: its members are not all available as separate passports.",
        "nl": "Samenvoeging '{name}' is niet toegepast: niet alle leden zijn als apart paspoort beschikbaar.",
    },
    "merge.need_two": {
        "en": "Select at least two passports in the list first.",
        "nl": "Selecteer eerst minstens twee paspoorten in de lijst.",
    },
    "merge.dialog.title": {"en": "Merge passports", "nl": "Paspoorten samenvoegen"},
    "merge.dialog.name": {"en": "Name of the combined passport:", "nl": "Naam van het gecombineerde paspoort:"},
    "merge.dialog.members": {"en": "Passports to merge", "nl": "Samen te voegen paspoorten"},
    "merge.dialog.col.filter": {"en": "Filter", "nl": "Filter"},
    "merge.dialog.col.group": {"en": "Management group", "nl": "Beheergroep"},
    "merge.dialog.col.fit": {"en": "Fit", "nl": "Pasvorm"},
    "merge.dialog.info": {
        "en": "Similarity {similarity}%; {common} common fields + {partial} per sub-theme.",
        "nl": "Gelijkenis {similarity}%; {common} gemeenschappelijke velden + {partial} per subthema.",
    },
    "merge.dialog.warn_filters": {
        "en": "These passports use different filters. Fields that do not apply to every filter get a footnote.",
        "nl": "Deze paspoorten gebruiken verschillende filters. Velden die niet voor elk filter gelden krijgen een "
        "voetnoot.",
    },
    "merge.dialog.warn_groups": {
        "en": "WARNING: the passports belong to different management groups ({groups}).",
        "nl": "LET OP: de paspoorten horen bij verschillende beheergroepen ({groups}).",
    },
    "merge.dialog.confirm": {"en": "Merge anyway / Toch samenvoegen", "nl": "Toch samenvoegen / Merge anyway"},
    "merge.name_empty": {"en": "Enter a name.", "nl": "Vul een naam in."},
    "merge.name_too_long": {
        "en": "The name may be at most 50 characters.",
        "nl": "De naam mag maximaal 50 tekens zijn.",
    },
    "merge.name_duplicate": {
        "en": "A passport with this name already exists.", "nl": "Er bestaat al een paspoort met deze naam.",
    },
    "merge.none_group": {"en": "(none)", "nl": "(geen)"},
    "dialog.save_merge": {"en": "Save merge matrix", "nl": "Samenvoegmatrix opslaan"},
    # --- 0.4.0: veld-ID's, import, vergelijking, annotaties / field IDs, import, cross-reference, annotations ---
    "action.check_ids": {"en": "Check field I&Ds…", "nl": "Veld-I&D's controleren…"},
    "action.import_refined": {"en": "&Import refined Excel…", "nl": "Bijgewerkt Excel-ontwerp &importeren…"},
    "action.back_generated": {"en": "&Back to generated design", "nl": "&Terug naar gegenereerd ontwerp"},
    "action.check_annotations": {"en": "Check/fix &annotations…", "nl": "&Annotaties controleren/repareren…"},
    "action.highlight": {"en": "Highlight &changes", "nl": "&Wijzigingen markeren"},
    "action.highlight_tip": {
        "en": "Outline fields that differ from the specification in the mockup (off for clean screenshots).",
        "nl": "Omlijn velden die afwijken van de specificatie in de mockup (uit voor schone screenshots).",
    },
    "action.extra_tabs": {"en": "Show extra &mockup tabs", "nl": "Extra &mockup-tabbladen tonen"},
    "mock.activities": {"en": "Activities", "nl": "Activiteiten"},
    "dialog.load_ids_catalog": {
        "en": "Choose a field catalog or diverse-fields file",
        "nl": "Kies een veldencatalogus of diverse-fields-bestand",
    },
    "dialog.filter_catalog": {
        "en": "Field catalog (*.xlsx *.json)", "nl": "Veldencatalogus (*.xlsx *.json)",
    },
    "dialog.import_refined": {"en": "Import refined Excel design", "nl": "Bijgewerkt Excel-ontwerp importeren"},
    "dialog.check_annotations": {
        "en": "Choose the Excel design to check",
        "nl": "Kies het te controleren Excel-ontwerp",
    },
    "dialog.save_id_report": {"en": "Save ID report", "nl": "ID-rapport opslaan"},
    "status.loading_ids": {"en": "Reading field IDs from {name}…", "nl": "Veld-ID's lezen uit {name}…"},
    "status.ids_detail": {
        "en": "{count} field IDs loaded from {name}; subtheme data: {subthemes}.",
        "nl": "{count} veld-ID's geladen uit {name}; subthemagegevens: {subthemes}.",
    },
    "ids.sub_names": {"en": "yes (with names)", "nl": "ja (met namen)"},
    "ids.sub_ids": {"en": "IDs only, no names", "nl": "alleen ID's, geen namen"},
    "ids.sub_none": {"en": "none", "nl": "geen"},
    "idcheck.title": {"en": "Field ID check", "nl": "Veld-ID-controle"},
    "idcheck.summary": {"en": "{total} fields checked: {text}", "nl": "{total} velden gecontroleerd: {text}"},
    "idcheck.severity": {"en": "Severity:", "nl": "Ernst:"},
    "idcheck.status": {"en": "Status:", "nl": "Status:"},
    "idcheck.all": {"en": "All", "nl": "Alle"},
    "idcheck.shown": {"en": "{shown} of {total} shown", "nl": "{shown} van {total} getoond"},
    "idcheck.col.tab": {"en": "Passport", "nl": "Paspoort"},
    "idcheck.col.section": {"en": "Section", "nl": "Sectie"},
    "idcheck.col.label": {"en": "Label", "nl": "Label"},
    "idcheck.col.id": {"en": "ID", "nl": "ID"},
    "idcheck.col.status": {"en": "Status", "nl": "Status"},
    "idcheck.col.detail": {"en": "Detail", "nl": "Toelichting"},
    "idcheck.col.types": {"en": "Object types", "nl": "Objecttypen"},
    "idcheck.export": {"en": "Export…", "nl": "Exporteren…"},
    "idcheck.offline": {
        "en": "Offline check: the app never contacts iAsset.",
        "nl": "Offline controle: de app maakt nooit verbinding met iAsset.",
    },
    "error.read_catalog": {
        "en": "The field catalog could not be read:\n{detail}",
        "nl": "De veldencatalogus kon niet worden gelezen:\n{detail}",
    },
    "error.read_refined": {
        "en": "The Excel design could not be read:\n{detail}\n\nDetails are in the log file.",
        "nl": "Het Excel-ontwerp kon niet worden gelezen:\n{detail}\n\nDetails staan in het logbestand.",
    },
    "error.no_sheets": {
        "en": "No passport design sheets were found in this file.",
        "nl": "In dit bestand zijn geen paspoortontwerp-bladen gevonden.",
    },
    "error.id_check": {
        "en": "The field IDs could not be checked:\n{detail}",
        "nl": "De veld-ID's konden niet worden gecontroleerd:\n{detail}",
    },
    "annot.warnings": {"en": "Warnings:", "nl": "Waarschuwingen:"},
    "error.annotations": {
        "en": "The annotations could not be checked:\n{detail}",
        "nl": "De annotaties konden niet worden gecontroleerd:\n{detail}",
    },
    "error.export_imported_types": {
        "en": "Export per object type is not available for an imported design. Go back to the generated design first.",
        "nl": "Exporteren per objecttype is niet beschikbaar voor een geïmporteerd ontwerp. Ga eerst terug naar het "
        "gegenereerde ontwerp.",
    },
    "import.window": {"en": "Imported design: {name}", "nl": "Geïmporteerd ontwerp: {name}"},
    "import.loading": {"en": "Reading {name}…", "nl": "{name} lezen…"},
    "import.done": {
        "en": "Imported {sheets} sheet(s) from {name}; {changes} difference(s) with the specification.",
        "nl": "{sheets} blad(en) geïmporteerd uit {name}; {changes} verschil(len) met de specificatie.",
    },
    "import.done_nospec": {
        "en": "Imported {sheets} sheet(s) from {name}. Load the specification to cross-reference.",
        "nl": "{sheets} blad(en) geïmporteerd uit {name}. Laad de specificatie om te vergelijken.",
    },
    "import.back_done": {"en": "Back to the generated design.", "nl": "Terug naar het gegenereerde ontwerp."},
    "tab.crossref": {"en": "Cross-reference", "nl": "Vergelijking"},
    "xref.not_imported": {
        "en": "Import a refined Excel design (File → Import refined Excel…) to compare it with the specification.",
        "nl": "Importeer een bijgewerkt Excel-ontwerp (Bestand → Bijgewerkt Excel-ontwerp importeren…) om het met de "
        "specificatie te vergelijken.",
    },
    "xref.need_spec": {
        "en": "Load the specification to cross-reference the imported design.",
        "nl": "Laad de specificatie om het geïmporteerde ontwerp te vergelijken.",
    },
    "xref.imported": {"en": "Imported: {name}", "nl": "Geïmporteerd: {name}"},
    "xref.no_diff": {"en": "No differences", "nl": "Geen verschillen"},
    "xref.warnings": {"en": "Import warnings", "nl": "Importwaarschuwingen"},
    "xref.sheet_counts": {"en": "{name} ({counts})", "nl": "{name} ({counts})"},
    "xref.col.kind": {"en": "Kind", "nl": "Soort"},
    "xref.col.label": {"en": "Field", "nl": "Veld"},
    "xref.col.move": {"en": "From → to section", "nl": "Van → naar sectie"},
    "xref.col.detail": {"en": "Detail", "nl": "Toelichting"},
    "xref.sections_added": {"en": "New section: {name}", "nl": "Nieuwe sectie: {name}"},
    "xref.sections_removed": {"en": "Missing section: {name}", "nl": "Ontbrekende sectie: {name}"},
    "kind.added": {"en": "Added", "nl": "Toegevoegd"},
    "kind.removed": {"en": "Removed", "nl": "Verwijderd"},
    "kind.moved": {"en": "Moved", "nl": "Verplaatst"},
    "kind.renamed": {"en": "Renamed", "nl": "Hernoemd"},
    "kind.not-in-spec": {"en": "Not in spec", "nl": "Niet in spec"},
    "annot.title": {"en": "Check annotations", "nl": "Annotaties controleren"},
    "annot.file": {"en": "File: {path}", "nl": "Bestand: {path}"},
    "annot.no_spec": {
        "en": "No specification loaded: only the internal consistency is checked.",
        "nl": "Geen specificatie geladen: alleen de interne consistentie wordt gecontroleerd.",
    },
    "annot.summary": {
        "en": "{sheets} sheet(s) checked, {issues} issue(s).",
        "nl": "{sheets} blad(en) gecontroleerd, {issues} probleem/problemen.",
    },
    "annot.ok": {"en": "No annotation issues found.", "nl": "Geen annotatieproblemen gevonden."},
    "annot.col.sheet": {"en": "Sheet", "nl": "Blad"},
    "annot.col.cell": {"en": "Cell", "nl": "Cel"},
    "annot.col.kind": {"en": "Kind", "nl": "Soort"},
    "annot.col.severity": {"en": "Severity", "nl": "Ernst"},
    "annot.col.detail": {"en": "Detail", "nl": "Toelichting"},
    "annot.fix": {"en": "Fix → _fixed.xlsx", "nl": "Repareren → _fixed.xlsx"},
    "annot.fix_tip": {
        "en": "Renumbers footnotes and rewrites the remarks into a copy; the original is left untouched.",
        "nl": "Nummert voetnoten opnieuw en schrijft de opmerkingen in een kopie; het origineel blijft ongemoeid.",
    },
    "annot.fixed": {"en": "Fixed copy written to: {path}", "nl": "Gerepareerde kopie opgeslagen als: {path}"},
    "annot.changes": {"en": "{count} change(s):", "nl": "{count} wijziging(en):"},
    "annot.after": {
        "en": "After the fix: {issues} issue(s) left.",
        "nl": "Na de reparatie: nog {issues} probleem/problemen.",
    },
    "annot.fix_failed": {"en": "The fix failed:\n{detail}", "nl": "De reparatie is mislukt:\n{detail}"},
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
