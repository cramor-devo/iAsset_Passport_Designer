"""Dialoog om geselecteerde paspoorten handmatig samen te voegen, ook bij verschillende filters of groepen.
Dialog to manually merge selected passports, even when their filters or groups differ."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..merge_advisor import MAX_NAME, ManualMergeInfo, validate_merge_name


class MergeDialog(QDialog):
    """Vraagt om een nieuwe naam en bevestiging; OK pas actief als beide in orde zijn.
    Asks for a new name and confirmation; OK only becomes active when both are in order."""

    def __init__(self, info: ManualMergeInfo, existing: set[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.info = info
        self.existing = existing
        self.setWindowTitle(tr("merge.dialog.title"))
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("merge.dialog.members")))
        self.member_tree = QTreeWidget()
        self.member_tree.setRootIsDecorated(False)
        self.member_tree.setHeaderLabels(
            [tr("merge.dialog.col.filter"), tr("merge.dialog.col.group"), tr("merge.dialog.col.fit")],
        )
        for fit in info.fits:
            group = info.groups.get(fit.filter) or tr("merge.none_group")
            self.member_tree.addTopLevelItem(QTreeWidgetItem([fit.filter, group, f"{round(fit.fit * 100)}%"]))
        self.member_tree.setMaximumHeight(160)
        layout.addWidget(self.member_tree)
        layout.addWidget(QLabel(tr(
            "merge.dialog.info", similarity=round(info.similarity * 100),
            common=info.total_fields - info.partial_fields, partial=info.partial_fields,
        )))

        self.name_label = QLabel(tr("merge.dialog.name"))
        self.name_edit = QLineEdit(info.name)
        self.name_edit.setMaxLength(MAX_NAME + 20)  # te lang = foutmelding / too long = error
        self.name_label.setBuddy(self.name_edit)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #c0392b;")
        layout.addWidget(self.name_label)
        layout.addWidget(self.name_edit)
        layout.addWidget(self.error_label)

        self.group_warning = QLabel()
        self.group_warning.setWordWrap(True)
        self.group_warning.setStyleSheet("color: #c0392b; font-weight: bold;")
        self.filter_warning = QLabel(tr("merge.dialog.warn_filters"))
        self.filter_warning.setWordWrap(True)
        self.group_warning.setVisible(info.groups_differ)
        if info.groups_differ:
            groups = ", ".join(sorted({g for g in info.groups.values() if g}))
            self.group_warning.setText(tr("merge.dialog.warn_groups", groups=groups))
        self.filter_warning.setVisible(info.filters_differ)
        layout.addWidget(self.group_warning)
        layout.addWidget(self.filter_warning)
        self.confirm_check = QCheckBox(tr("merge.dialog.confirm"))
        layout.addWidget(self.confirm_check)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        assert self.ok_button is not None and self.cancel_button is not None
        self.ok_button.setAutoDefault(False)
        self.cancel_button.setAutoDefault(True)
        self.cancel_button.setDefault(True)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.name_edit.textChanged.connect(self._validate)
        self.confirm_check.toggled.connect(self._validate)
        self._validate()

    def merge_name(self) -> str:
        return self.name_edit.text().strip()

    def _validate(self, *_args: object) -> None:
        key = validate_merge_name(self.name_edit.text(), self.existing)
        self.error_label.setText(tr(key) if key else "")
        confirmed = self.confirm_check.isChecked() or not self.info.needs_confirmation
        assert self.ok_button is not None
        self.ok_button.setEnabled(key is None and confirmed)
