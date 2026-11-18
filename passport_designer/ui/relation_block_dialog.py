"""Dialogen voor relatieblokken en hernoemde standaardblokken. / Dialogs for relation blocks and renamed standard
blocks.

NL: ``BlockManagerDialog`` toont de blokken van het getoonde paspoort; het hoofdvenster voert de wijzigingen uit
(met ongedaan maken) via het ``BlockHost``-protocol. ``BlockEditor`` bewerkt één blok.
EN: ``BlockManagerDialog`` shows the blocks of the shown passport; the main window carries out the changes (with undo)
through the ``BlockHost`` protocol. ``BlockEditor`` edits one block.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..merge_advisor import MAX_NAME
from ..relation_blocks import (
    DEFAULT_REPEAT,
    EXTRA_RELATION_TYPES,
    MAX_COLUMNS,
    MAX_REPEAT,
    RELATION_TYPES,
    TEMPLATE_RELATION_TYPES,
    BlockEdit,
    RelationBlock,
    block_title_error,
)


@dataclass(frozen=True)
class BlockEntry:
    """Eén regel in de blokkenlijst. ``index`` is de plek onder de relatieblokken (-1 = standaardblok).
    One line of the block list. ``index`` is the place among the relation blocks (-1 = standard block)."""

    title: str  # getoonde titel / shown title
    original_title: str  # gegenereerde titel van een standaardblok / generated title of a standard block
    element: int
    labels: tuple[str, ...]  # getoonde kolomnamen / shown column labels
    samples: tuple[str, ...]
    standard_labels: tuple[str, ...] = ()
    repeat: int = DEFAULT_REPEAT
    index: int = -1
    renamed: bool = False

    @property
    def is_standard(self) -> bool:
        return self.index < 0


class BlockHost(Protocol):
    """Wat het hoofdvenster voor de dialoog uitvoert. / What the main window carries out for the dialog."""

    def block_entries(self) -> list[BlockEntry]: ...

    def shown_titles(self) -> set[str]: ...

    def add_block(self, block: RelationBlock, *, all_passports: bool) -> bool: ...

    def update_block(self, entry: BlockEntry, block: RelationBlock, *, all_passports: bool) -> bool: ...

    def delete_block(self, entry: BlockEntry, *, all_passports: bool) -> bool: ...

    def move_block(self, entry: BlockEntry, delta: int) -> bool: ...

    def set_standard_edit(self, entry: BlockEntry, edit: BlockEdit, *, all_passports: bool) -> bool: ...

    def reset_standard(self, entry: BlockEntry, *, all_passports: bool) -> bool: ...


def type_text(element: int) -> str:
    return f"{element} - {RELATION_TYPES.get(element, '?')}"


class BlockEditor(QDialog):
    """Bewerkt één blok: naam, relatietype (alleen bij een nieuw/relatieblok), kolomnamen met voorbeeldgegevens en het
    aantal voorbeeldrijen. Edits one block: name, relation type (new/relation blocks only), column labels with sample
    data and the number of sample rows."""

    def __init__(
        self, parent: QWidget | None = None, *, entry: BlockEntry | None, existing: set[str],
    ) -> None:
        super().__init__(parent)
        self.entry = entry
        self.existing = existing
        self.current = entry.title if entry else ""
        self.standard = entry is not None and entry.is_standard
        self.setWindowTitle(tr("blocks.editor_edit" if entry else "blocks.editor_add"))
        self.setMinimumWidth(520)
        form = QFormLayout()
        self.name_edit = QLineEdit(self.current)
        self.name_edit.setMaxLength(MAX_NAME + 20)
        form.addRow(tr("blocks.name"), self.name_edit)
        self.type_combo = QComboBox()
        self.extra_check = QCheckBox(tr("blocks.show_extra"))
        if self.standard and entry is not None:
            form.addRow(tr("blocks.type_fixed"), QLabel(type_text(entry.element)))
        else:
            wanted = entry.element if entry else min(TEMPLATE_RELATION_TYPES)
            self.extra_check.setChecked(wanted in EXTRA_RELATION_TYPES)
            self._fill_types(wanted)
            self.extra_check.toggled.connect(lambda _on: self._fill_types(self.type_combo.currentData()))
            form.addRow(tr("blocks.type"), self.type_combo)
            form.addRow("", self.extra_check)
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(1, MAX_REPEAT)
        self.repeat_spin.setValue(entry.repeat if entry else DEFAULT_REPEAT)
        if not self.standard:
            form.addRow(tr("blocks.repeat"), self.repeat_spin)
        rows = len(entry.standard_labels) if self.standard and entry else MAX_COLUMNS
        self.table = QTableWidget(rows, 2)
        self.table.setHorizontalHeaderLabels([tr("blocks.col_label"), tr("blocks.col_sample")])
        self.table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.table.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        labels = entry.labels if entry else ("Nummer", "Objecttype")
        for row in range(rows):
            label = labels[row] if row < len(labels) else ""
            sample = entry.samples[row] if entry and row < len(entry.samples) else ""
            self.table.setItem(row, 0, QTableWidgetItem(label))
            self.table.setItem(row, 1, QTableWidgetItem(sample))
        self.table.setColumnWidth(0, 220)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #c0392b;")
        note = QLabel(tr("blocks.sample_note"))
        note.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.table)
        layout.addWidget(note)
        layout.addWidget(self.error_label)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert self.ok_button is not None
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.name_edit.textChanged.connect(self._validate)
        self.table.itemChanged.connect(self._validate)
        self._validate()

    def _fill_types(self, selected: object) -> None:
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        types = dict(TEMPLATE_RELATION_TYPES)
        if self.extra_check.isChecked():
            types.update(EXTRA_RELATION_TYPES)
        for element in types:
            self.type_combo.addItem(type_text(element), element)
        index = self.type_combo.findData(selected)
        self.type_combo.setCurrentIndex(max(index, 0))
        self.type_combo.blockSignals(False)

    def _column(self, column: int) -> list[str]:
        values: list[str] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, column)
            values.append(" ".join(item.text().split()) if item else "")
        return values

    def labels(self) -> tuple[str, ...]:
        return tuple(self._column(0))

    def samples(self) -> tuple[str, ...]:
        return tuple(self._column(1))

    def new_name(self) -> str:
        return " ".join(self.name_edit.text().split())

    def element(self) -> int:
        if self.standard and self.entry is not None:
            return self.entry.element
        return int(self.type_combo.currentData())

    def block(self) -> RelationBlock:
        """Het ingevulde relatieblok (kolommen zonder naam vallen weg). / The filled-in relation block (columns
        without a name are dropped)."""
        pairs = [(label, sample) for label, sample in zip(self.labels(), self.samples(), strict=True) if label]
        return RelationBlock(
            self.new_name(), self.element(), tuple(p[0] for p in pairs),
            tuple(p[1] for p in pairs) if any(p[1] for p in pairs) else (), self.repeat_spin.value(),
        )

    def standard_edit(self) -> BlockEdit:
        """Alleen wat afwijkt van de standaard (voor een standaardblok). / Only what differs from the standard (for a
        standard block)."""
        assert self.entry is not None
        title = self.new_name() if self.new_name() != self.entry.original_title else ""
        labels = tuple(
            label if label != std else "" for label, std in zip(self.labels(), self.entry.standard_labels, strict=False)
        )
        return BlockEdit(title, labels, self.samples())

    def _validate(self, *_args: object) -> None:
        key = block_title_error(self.new_name(), self.existing, self.current)
        if key is None and not self.standard and not self.block().columns:
            message = tr("blocks.columns_needed")
        else:
            message = tr(key) if key else ""
        self.error_label.setText(message)
        self.ok_button.setEnabled(not message)  # type: ignore[union-attr]


class BlockManagerDialog(QDialog):
    """Lijst met de blokken van het paspoort en de acties Toevoegen, Bewerken, Verwijderen, Standaard herstellen en
    verplaatsen. List of the passport's blocks and the actions Add, Edit, Delete, Reset to standard and move."""

    def __init__(self, host: BlockHost, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.host = host
        self.setWindowTitle(tr("blocks.title"))
        self.setMinimumSize(560, 420)
        layout = QVBoxLayout(self)
        intro = QLabel(tr("blocks.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel(tr("blocks.scope")))
        self.scope_combo = QComboBox()
        self.scope_combo.addItem(tr("blocks.scope_this"), False)
        self.scope_combo.addItem(tr("blocks.scope_all"), True)
        scope_row.addWidget(self.scope_combo, 1)
        layout.addLayout(scope_row)
        self.list = QListWidget()
        self.list.itemSelectionChanged.connect(self._update_buttons)
        self.list.itemDoubleClicked.connect(lambda _item: self.edit_selected())
        layout.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        self.add_button = self._button("blocks.add", self.add_new, buttons)
        self.edit_button = self._button("blocks.edit", self.edit_selected, buttons)
        self.delete_button = self._button("blocks.delete", self.delete_selected, buttons)
        self.reset_button = self._button("blocks.reset", self.reset_selected, buttons)
        self.up_button = self._button("blocks.up", lambda: self.move_selected(-1), buttons)
        self.down_button = self._button("blocks.down", lambda: self.move_selected(1), buttons)
        layout.addLayout(buttons)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        close.button(QDialogButtonBox.StandardButton.Close).setText(tr("blocks.close"))  # type: ignore[union-attr]
        layout.addWidget(close)
        self.refresh()

    def _button(self, key: str, slot: object, row: QHBoxLayout) -> QPushButton:
        button = QPushButton(tr(key))
        button.clicked.connect(lambda _checked=False: slot())  # type: ignore[operator]
        row.addWidget(button)
        return button

    @property
    def all_passports(self) -> bool:
        return bool(self.scope_combo.currentData())

    def _editor(self, entry: BlockEntry | None) -> BlockEditor:
        return BlockEditor(self, entry=entry, existing=self.host.shown_titles())

    def _run_editor(self, editor: BlockEditor) -> bool:
        return editor.exec() == QDialog.DialogCode.Accepted

    def refresh(self, keep: int = -1) -> None:
        """Vul de lijst opnieuw; ``keep`` = rij om weer te selecteren. / Refill the list; ``keep`` = row to reselect."""
        self.entries = self.host.block_entries()
        self.list.clear()
        for entry in self.entries:
            if entry.is_standard:
                kind = tr("blocks.kind_renamed" if entry.renamed else "blocks.kind_standard")
            else:
                kind = tr("blocks.kind_relation", type=type_text(entry.element))
            item = QListWidgetItem(f"{entry.title}  [{kind}]")
            item.setData(Qt.ItemDataRole.UserRole, entry.title)
            self.list.addItem(item)
        if 0 <= keep < self.list.count():
            self.list.setCurrentRow(keep)
        self._update_buttons()

    def selected_entry(self) -> BlockEntry | None:
        row = self.list.currentRow()
        return self.entries[row] if 0 <= row < len(self.entries) else None

    def _update_buttons(self) -> None:
        entry = self.selected_entry()
        relation_count = sum(1 for e in self.entries if not e.is_standard)
        self.edit_button.setEnabled(entry is not None)
        self.delete_button.setEnabled(entry is not None and not entry.is_standard)
        self.reset_button.setEnabled(entry is not None and entry.is_standard and entry.renamed)
        self.up_button.setEnabled(entry is not None and not entry.is_standard and entry.index > 0)
        self.down_button.setEnabled(entry is not None and not entry.is_standard and entry.index < relation_count - 1)

    def add_new(self) -> None:
        editor = self._editor(None)
        if self._run_editor(editor) and self.host.add_block(editor.block(), all_passports=self.all_passports):
            self.refresh(keep=len(self.entries))

    def edit_selected(self) -> None:
        entry = self.selected_entry()
        if entry is None:
            return
        editor = self._editor(entry)
        if not self._run_editor(editor):
            return
        row = self.list.currentRow()
        if entry.is_standard:
            self.host.set_standard_edit(entry, editor.standard_edit(), all_passports=self.all_passports)
        else:
            self.host.update_block(entry, editor.block(), all_passports=self.all_passports)
        self.refresh(keep=row)

    def delete_selected(self) -> None:
        entry = self.selected_entry()
        if entry is not None and not entry.is_standard:
            self.host.delete_block(entry, all_passports=self.all_passports)
            self.refresh()

    def reset_selected(self) -> None:
        entry = self.selected_entry()
        if entry is not None and entry.is_standard:
            self.host.reset_standard(entry, all_passports=self.all_passports)
            self.refresh(keep=self.list.currentRow())

    def move_selected(self, delta: int) -> None:
        entry = self.selected_entry()
        if entry is not None and not entry.is_standard and self.host.move_block(entry, delta):
            self.refresh(keep=self.list.currentRow() + delta)
