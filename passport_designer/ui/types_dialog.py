"""Dialoog om objecttypen te verplaatsen of te verwijderen. / Dialog to move or delete object types."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr


class TypesDialog(QDialog):
    """Kies objecttypen van één paspoort en verplaats ze naar een ander paspoort of verwijder ze. Na sluiten geeft
    ``action`` de keuze: "move", "delete", "restore" of "" (geannuleerd).
    Pick object types of one passport and move them to another passport or delete them. After closing, ``action``
    holds the choice: "move", "delete", "restore" or "" (cancelled)."""

    def __init__(self, tab_name: str, types: list[str], targets: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("typesDialog")
        self.setWindowTitle(tr("types.title", tab=tab_name))
        self.action = ""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("types.text")))
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.addItems(types)
        layout.addWidget(self.list)
        move_row = QHBoxLayout()
        self.target_combo = QComboBox()
        self.target_combo.addItems(targets)
        self.move_button = QPushButton(tr("types.move"))
        self.move_button.setEnabled(bool(targets))
        self.move_button.clicked.connect(lambda: self._finish("move"))
        move_row.addWidget(self.target_combo, 1)
        move_row.addWidget(self.move_button)
        layout.addLayout(move_row)
        self.delete_button = QPushButton(tr("types.delete"))
        self.delete_button.clicked.connect(lambda: self._finish("delete"))
        self.restore_button = QPushButton(tr("types.restore"))
        self.restore_button.clicked.connect(lambda: self._finish("restore"))
        layout.addWidget(self.delete_button)
        layout.addWidget(self.restore_button)

    def _finish(self, action: str) -> None:
        self.action = action
        self.accept()

    def chosen(self) -> list[str]:
        """Namen van de geselecteerde objecttypen. / Names of the selected object types."""
        return [item.text() for item in self.list.selectedItems()]

    def target(self) -> str:
        """Naam van het gekozen doelpaspoort. / Name of the chosen target passport."""
        return self.target_combo.currentText()
