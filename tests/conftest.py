"""Gedeelde testgegevens: kleine xlsx-bestanden in Wave 1- en Wave 2-indeling. Alles offline.
Shared test data: small xlsx files in Wave 1 and Wave 2 layouts. Everything offline."""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from passport_designer.models import ObjectType, SpecModel
from passport_designer.spec_reader import read_spec


def make_wave1(path: Path) -> Path:
    workbook = Workbook()
    types = workbook.active
    assert types is not None
    types.title = "Objecttypen"
    types.append(["Objecttypen implementatie"])
    types.append(["2026-09-25"])
    types.append(["Objecttype", "GUID", "URI", "Informatiemodel", "Filter", "Groep", "Fase", "Geometrietype"])
    types.append(["APV-bord", "g", "u", "IMBOR", "Bord", "Borden", "Wave 1", "Point"])
    types.append(["Verkeersbord", "g", "u", "IMBOR", "Bord", "Borden", "Wave 1", "Point"])
    types.append(["Asfaltverharding", "g", "u", "IMBOR", "Verharding", "Wegen", "Wave 1", "Surface"])
    attrs = workbook.create_sheet("Attributen")
    attrs.append(["Paspoortgegevens"])
    attrs.append([])
    attrs.append(["Objecttype", "GUID", "Attribuut", "GUID", "In paspoort tonen"])
    rows = [
        ("APV-bord", "domein", "Ja"),
        ("APV-bord", "identificatie", "Ja"),
        ("APV-bord", "bordcode", "Ja"),
        ("APV-bord", "APV-verordening", "Ja"),
        ("APV-bord", "breedte", "Ja"),
        ("APV-bord", "hoogte", "Ja"),
        ("APV-bord", "primaire kleur", "Ja"),
        ("APV-bord", "aanlegjaar", "Ja"),
        ("APV-bord", "geheim", "Nee"),
        ("Verkeersbord", "bordcode", "Ja"),
        ("Verkeersbord", "breedte", "Ja"),
        ("Verkeersbord", "hoogte", "Ja"),
        ("Verkeersbord", "primaire kleur", "Ja"),
        ("Verkeersbord", "aanlegjaar", "Ja"),
        ("Asfaltverharding", "breedte", "Ja"),
        ("Asfaltverharding", "dikte", "Ja"),
    ]
    for type_name, attribute, flag in rows:
        attrs.append([type_name, "g", attribute, "g", flag])
    workbook.save(path)
    return path


def make_wave2(path: Path) -> Path:
    workbook = Workbook()
    types = workbook.active
    assert types is not None
    types.title = "Objecttypen"
    types.append(["RD-Objecttypen-Wave-2"])
    types.append(["Organisatie", "Objecttype", "Filter", "Systeem", "Fase", "Geometrietype"])
    types.append(["Gemeente Rotterdam", "Aansluitput", "RD-Obsurv", "Wave 2", "Put", "Point"])
    types.append(["Gemeente Rotterdam", "Aflaatstuw", "RD-Ultimo", "Wave 2", "Stuw", "Surface"])
    attrs = workbook.create_sheet("Attributen")
    attrs.append(["RD_Objecttypen-Attributen"])
    attrs.append(["Organisatie", "Objecttype", "Fase", "Klasse", "Volgorde", "Attribuut", "Opnemen"])
    attrs.append(["Gemeente Rotterdam", "Aansluitput", "Wave 2", "Constructie", 5, "aanleghoogte", "Ja"])
    attrs.append(["Gemeente Rotterdam", "Aansluitput", "Wave 2", "Constructie", 6, "diameter", "Nee"])
    attrs.append(["Gemeente Rotterdam", "Aflaatstuw", "Wave 2", "Constructie", 5, "aanleghoogte", "Ja"])
    workbook.save(path)
    return path


COMMON = ["breedte", "hoogte", "dikte", "kleur", "aanlegjaar", "productiejaar"]


def make_spec() -> SpecModel:
    spec = SpecModel()
    spec.object_types = [
        ObjectType("Verkeersbord", "Bord", "Borden"),
        ObjectType("APV-bord", "Bord", "Borden"),
        ObjectType("Informatiebord", "Informatiebord", "Borden"),
        ObjectType("Paal", "Paal", "Meubilair"),
        ObjectType("Asfalt", "Verharding", "Wegen"),
    ]
    spec.attributes = {
        "Verkeersbord": [*COMMON, "bordcode"],
        "APV-bord": [*COMMON, "bordcode", "APV-verordening"],
        "Informatiebord": [*COMMON, "tekst"],
        "Paal": [*COMMON, "bordcode", "tekst"],  # zelfde attributen, andere groep / same attributes, other group
        "Asfalt": ["laagdikte", "bindmiddel", "korrel"],
    }
    return spec


@pytest.fixture
def wave1_file(tmp_path: Path) -> Path:
    return make_wave1(tmp_path / "wave1.xlsx")


@pytest.fixture
def wave2_file(tmp_path: Path) -> Path:
    return make_wave2(tmp_path / "wave2.xlsx")


@pytest.fixture
def wave1_spec(wave1_file: Path) -> SpecModel:
    return read_spec(wave1_file)
