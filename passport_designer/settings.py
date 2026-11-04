"""Logbestand en instellingen-opslag. / Log file and settings storage."""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

from PyQt6.QtCore import QSettings

from .payload import PayloadOptions

ORGANISATION = "iAssetPassportDesigner"
APPLICATION = "PassportDesigner"


def data_dir() -> Path:
    """Map voor logbestanden (%LOCALAPPDATA% op Windows). / Folder for log files (%LOCALAPPDATA% on Windows)."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    folder = Path(base) / ORGANISATION
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def setup_logging() -> Path:
    """Schrijf details naar een roterend logbestand; de gebruiker ziet nooit een stacktrace.
    Write details to a rotating log file; the user never sees a stack trace."""
    path = data_dir() / "passport_designer.log"
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=500_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return path


class AppSettings:
    """Dunne laag om QSettings met getypeerde waarden. / Thin typed layer over QSettings."""

    def __init__(self, backend: QSettings | None = None) -> None:
        self._qs = backend or QSettings(ORGANISATION, APPLICATION)

    def string(self, key: str, default: str) -> str:
        return str(self._qs.value(key, default))

    def integer(self, key: str, default: int) -> int:
        try:
            return int(str(self._qs.value(key, default)))
        except ValueError:
            return default

    def boolean(self, key: str, default: bool) -> bool:
        return str(self._qs.value(key, default)).lower() in ("true", "1")

    def set(self, key: str, value: object) -> None:
        self._qs.setValue(key, value)

    def payload_options(self) -> PayloadOptions:
        # NL: nieuwe sleutels (payload/v2/...) zodat oude opgeslagen standaardwaarden (1/0/0) niet overschrijven.
        # EN: new keys (payload/v2/...) so old saved defaults (1/0/0) do not override the new ones.
        d = PayloadOptions()
        k = "payload/v2/"
        return PayloadOptions(
            theme_id=self.integer("payload/theme_id", d.theme_id),
            group_field_type=self.integer(k + "group_field_type", d.group_field_type),
            field_field_type=self.integer(k + "field_field_type", d.field_field_type),
            system_field_type=self.integer(k + "system_field_type", d.system_field_type),
            group_field_id=self.integer(k + "group_field_id", d.group_field_id),
            line_field_id=self.integer(k + "line_field_id", d.line_field_id),
            separators=self.boolean(k + "separators", d.separators),
            order_start=self.integer("payload/order_start", d.order_start),
        )

    def save_payload_options(self, options: PayloadOptions) -> None:
        k = "payload/v2/"
        self.set("payload/theme_id", options.theme_id)
        self.set(k + "group_field_type", options.group_field_type)
        self.set(k + "field_field_type", options.field_field_type)
        self.set(k + "system_field_type", options.system_field_type)
        self.set(k + "group_field_id", options.group_field_id)
        self.set(k + "line_field_id", options.line_field_id)
        self.set(k + "separators", options.separators)
        self.set("payload/order_start", options.order_start)
