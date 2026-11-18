"""Voert de wijzigingen van relatie- en standaardblokken uit voor het hoofdvenster (met ongedaan maken).
Carries out the relation and standard block changes for the main window (with undo)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..i18n import tr
from ..layout_overrides import (
    LayoutRefused,
    TabOverride,
    add_block,
    apply_override,
    block_edit_of,
    delete_block,
    move_block,
    reset_block_edit,
    set_block_edit,
    update_block,
)
from ..models import PassportTab, SectionStyle, norm
from ..payload import section_element
from ..relation_blocks import BlockEdit, RelationBlock, apply_blocks, standard_columns
from .relation_block_dialog import BlockEntry

if TYPE_CHECKING:
    from .main_window import MainWindow

Change = Callable[[PassportTab, TabOverride, set[str]], TabOverride]


class BlockController:
    """Implementeert ``BlockHost``: leest de blokken van het getoonde paspoort en past ze toe op dit of alle
    paspoorten. Implements ``BlockHost``: reads the blocks of the shown passport and applies changes to this or
    all passports."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window

    def _override(self, tab: PassportTab) -> TabOverride:
        return self.window.overrides.get(tab.name, TabOverride())

    def shown_titles(self) -> set[str]:
        tab = self.window.current_tab()
        if tab is None:
            return set()
        return self._titles(tab, self._override(tab))

    @staticmethod
    def _titles(tab: PassportTab, override: TabOverride) -> set[str]:
        return {s.title for s in apply_override(tab, override, keep_empty=True)[0].sections}

    def block_entries(self) -> list[BlockEntry]:
        """Standaardblokken (herhaalbare secties van het ontwerp) gevolgd door de relatieblokken van dit paspoort.
        Standard blocks (repeatable sections of the design) followed by this passport's relation blocks."""
        tab = self.window.current_tab()
        if tab is None:
            return []
        override = self._override(tab)
        edited = apply_blocks(tab, (), override.block_edits).sections
        entries: list[BlockEntry] = []
        for original, shown in zip(tab.sections, edited, strict=True):
            if not original.repeater or original.style is SectionStyle.NOTES:
                continue
            edit = block_edit_of(override, original.title)
            columns = [c.label for c in standard_columns(shown)]
            samples = [c.sample for c in standard_columns(shown)]
            entries.append(BlockEntry(
                title=shown.title, original_title=original.title,
                element=shown.element or section_element(original, tab.profile),
                labels=tuple(columns), samples=tuple(samples),
                standard_labels=tuple(c.label for c in standard_columns(original)),
                renamed=edit is not None,
            ))
        for index, block in enumerate(override.blocks):
            entries.append(BlockEntry(
                title=block.title, original_title="", element=block.element, labels=block.columns,
                samples=block.samples, repeat=block.repeat, index=index,
            ))
        return entries

    # --- wijzigingen / changes ---------------------------------------------------------------------------------

    def _apply(self, change: Change, *, all_passports: bool, message: str) -> bool:
        """Pas ``change`` toe op dit (of alle) paspoort(en) met één ongedaan-maken-stap. Weigeringen per paspoort
        worden overgeslagen. Apply ``change`` to this (or all) passport(s) as one undo step. Refusals per passport
        are skipped."""
        window = self.window
        current = window.current_tab()
        if current is None:
            return False
        targets = window.tabs if all_passports else [current]
        updated: dict[str, TabOverride] = {}
        for tab in targets:
            override = self._override(tab)
            try:
                new = change(tab, override, self._titles(tab, override))
            except LayoutRefused:
                continue
            if new != override:
                updated[tab.name] = new
        if not updated:
            window.statusBar().showMessage(tr("blocks.refused"))
            return False
        window._push_undo("undo.blocks")  # noqa: SLF001 - hoofdvenster-intern / main-window internal
        for name, override in updated.items():
            if override.is_empty:
                window.overrides.pop(name, None)
            else:
                window.overrides[name] = override
        window._schedule_save()  # noqa: SLF001
        window._refresh_views()  # noqa: SLF001
        window.statusBar().showMessage(tr(message, count=len(updated)))
        return True

    def add_block(self, block: RelationBlock, *, all_passports: bool) -> bool:
        return self._apply(
            lambda _t, o, titles: add_block(o, block=block, existing_titles=titles),
            all_passports=all_passports, message="blocks.added",
        )

    def update_block(self, entry: BlockEntry, block: RelationBlock, *, all_passports: bool) -> bool:
        def change(_tab: PassportTab, override: TabOverride, titles: set[str]) -> TabOverride:
            index = next((i for i, b in enumerate(override.blocks) if b.title == entry.title), -1)
            return update_block(override, index=index, block=block, existing_titles=titles)

        return self._apply(change, all_passports=all_passports, message="blocks.updated")

    def delete_block(self, entry: BlockEntry, *, all_passports: bool) -> bool:
        def change(_tab: PassportTab, override: TabOverride, _titles: set[str]) -> TabOverride:
            index = next((i for i, b in enumerate(override.blocks) if b.title == entry.title), -1)
            return delete_block(override, index=index)

        return self._apply(change, all_passports=all_passports, message="blocks.deleted")

    def move_block(self, entry: BlockEntry, delta: int) -> bool:
        return self._apply(
            lambda _t, o, _titles: move_block(o, index=entry.index, delta=delta),
            all_passports=False, message="blocks.updated",
        )

    def set_standard_edit(self, entry: BlockEntry, edit: BlockEdit, *, all_passports: bool) -> bool:
        def change(tab: PassportTab, override: TabOverride, titles: set[str]) -> TabOverride:
            if not any(s.repeater and norm(s.title) == norm(entry.original_title) for s in tab.sections):
                raise LayoutRefused("invalid")  # dit paspoort heeft dat blok niet / this passport lacks that block
            return set_block_edit(override, original_title=entry.original_title, edit=edit, existing_titles=titles)

        return self._apply(change, all_passports=all_passports, message="blocks.updated")

    def reset_standard(self, entry: BlockEntry, *, all_passports: bool) -> bool:
        return self._apply(
            lambda _t, o, _titles: reset_block_edit(o, original_title=entry.original_title),
            all_passports=all_passports, message="blocks.reset_done",
        )

