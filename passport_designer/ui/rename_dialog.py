"""Dialoog om een paspoort te hernoemen. / Dialog to rename a passport."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ..i18n import tr
from ..merge_advisor import MAX_NAME
from ..renaming import sheet_name_adjusted, validate_rename


class RenameDialog(QDialog):
    """Vraagt een nieuwe naam; OK pas actief bij een geldige, andere naam. 'Naam herstellen' geeft de gegenereerde
    naam terug (alleen als die afwijkt). Asks a new name; OK is only enabled for a valid, different name. 'Reset
    name' returns the generated name (only offered when it differs)."""

    def __init__(
        self, current: str, existing: set[str], parent: QWidget | None = None, *,
        title_key: str = "rename.title", original: str = "",
    ) -> None:
        super().__init__(parent)
        self.current = current
        self.existing = existing
        self.original = original if original and original != current else ""
        self.reset_requested = False
        self.setWindowTitle(tr(title_key))
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        self.name_label = QLabel(tr("rename.prompt"))
        self.name_edit = QLineEdit(current)
        self.name_edit.setMaxLength(MAX_NAME + 20)  # te lang = foutmelding / too long = error
        self.name_label.setBuddy(self.name_edit)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #c0392b;")
        self.sheet_label = QLabel(tr("rename.sheet_note"))
        self.sheet_label.setWordWrap(True)
        layout.addWidget(self.name_label)
        layout.addWidget(self.name_edit)
        layout.addWidget(self.error_label)
        layout.addWidget(self.sheet_label)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert self.ok_button is not None
        self.reset_button: QPushButton | None = None
        if self.original:
            self.reset_button = self.buttons.addButton(
                tr("rename.reset", name=self.original), QDialogButtonBox.ButtonRole.ResetRole,
            )
            assert self.reset_button is not None
            self.reset_button.clicked.connect(self._reset)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.name_edit.textChanged.connect(self._validate)
        self._validate()

    def new_name(self) -> str:
        return self.name_edit.text().strip()

    def _reset(self) -> None:
        self.name_edit.setText(self.original)
        self.reset_requested = True
        self.accept()

    def _validate(self, *_args: object) -> None:
        key = validate_rename(self.name_edit.text(), self.current, self.existing)
        self.error_label.setText(tr(key) if key else "")
        self.sheet_label.setVisible(key is None and sheet_name_adjusted(self.name_edit.text()))
        assert self.ok_button is not None
        self.ok_button.setEnabled(key is None and self.new_name() != self.current)
