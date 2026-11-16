"""Dialoog om verwijderde velden terug te zetten. / Dialog to bring deleted fields back."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ..i18n import tr


class RestoreDialog(QDialog):
    """Afvinklijst met verwijderde velden (sleutel -> weergavenaam). / Checklist of deleted fields (key -> display
    name)."""

    def __init__(self, fields: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("restoreDialog")
        self.setWindowTitle(tr("verify.restore_title"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("verify.restore_text")))
        self.list = QListWidget()
        for key, name in fields.items():
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(item)
        layout.addWidget(self.list)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def chosen(self) -> list[str]:
        """Sleutels van de aangevinkte velden. / Keys of the ticked fields."""
        result: list[str] = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                result.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return result
