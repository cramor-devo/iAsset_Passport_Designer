"""Instellingen voor de API-payload. / Settings for the API payload."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from ..i18n import tr
from ..payload import PayloadOptions


class PayloadSettingsDialog(QDialog):
    """Dialoog om thema-id en type-codes aan te passen. / Dialog to edit the theme ID and type codes."""

    def __init__(self, options: PayloadOptions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._base = options
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.theme_id = self._spin(options.theme_id, -1)
        self.group_type = self._spin(options.group_field_type, 0)
        self.field_type = self._spin(options.field_field_type, 0)
        self.group_id = self._spin(options.group_field_id, 0)
        self.order_start = self._spin(options.order_start, 0)
        for key, spin in (
            ("settings.theme_id", self.theme_id),
            ("settings.group_type", self.group_type),
            ("settings.field_type", self.field_type),
            ("settings.group_id", self.group_id),
            ("settings.order_start", self.order_start),
        ):
            label = QLabel(tr(key))
            label.setBuddy(spin)
            form.addRow(label, spin)
        layout.addLayout(form)
        note = QLabel(tr("settings.note"))
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _spin(value: int, minimum: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, 1_000_000)
        spin.setValue(value)
        return spin

    def options(self) -> PayloadOptions:
        return PayloadOptions(
            theme_id=self.theme_id.value(),
            group_field_type=self.group_type.value(),
            field_field_type=self.field_type.value(),
            group_field_id=self.group_id.value(),
            order_start=self.order_start.value(),
            active=self._base.active,
        )
