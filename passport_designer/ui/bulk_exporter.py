"""Voert de bulk-export uit op de GUI-thread, één afbeelding per timer-tik, zodat het venster reageert en annuleren
kan. Widgets mogen niet op een werkthread getekend worden, dus ``workers.Job`` is hier niet bruikbaar.
Runs the bulk export on the GUI thread, one image per timer tick, so the window stays responsive and can cancel.
Widgets must not be drawn on a worker thread, so ``workers.Job`` cannot be used here."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap

from ..bulk_export import ExportJob

log = logging.getLogger(__name__)


@dataclass
class ExportReport:
    """Uitkomst van een run. / Outcome of a run."""

    total: int
    exported: int = 0
    skipped: int = 0
    cancelled: bool = False
    failed: list[tuple[ExportJob, str]] = field(default_factory=list)


class BulkExporter(QObject):
    """Schrijft de taken één voor één; ``render`` levert de afbeelding voor een taak.
    Writes the jobs one by one; ``render`` returns the image for a job."""

    progress = pyqtSignal(int, int, str)  # (nummer, totaal, naam) / (number, total, name)
    item_failed = pyqtSignal(object, str)  # (taak, melding) / (job, message)
    finished = pyqtSignal(object)  # ExportReport

    def __init__(
        self, jobs: list[ExportJob], render: Callable[[ExportJob], QPixmap], *, skipped: int = 0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._jobs = jobs
        self._render = render
        self._index = 0
        self._cancelled = False
        self._done = False
        self.report = ExportReport(total=len(jobs), skipped=skipped)

    def start(self) -> None:
        """Meld de eerste taak en begin. / Announce the first job and begin."""
        if not self._jobs:
            self._finish()
            return
        self.progress.emit(1, len(self._jobs), self._jobs[0].label)
        QTimer.singleShot(0, self._step)

    def cancel(self) -> None:
        """Stop na de afbeelding die nu bezig is; geschreven bestanden blijven. / Stop after the current image;
        written files stay."""
        self._cancelled = True

    def _step(self) -> None:
        if self._done:
            return
        if self._cancelled:
            self.report.cancelled = True
            self._finish()
            return
        job = self._jobs[self._index]
        try:
            pixmap = self._render(job)
            if pixmap.isNull():
                raise ValueError("empty image")
            job.path.parent.mkdir(parents=True, exist_ok=True)
            if not pixmap.save(str(job.path), "PNG"):
                raise OSError(f"cannot write {job.path}")
            self.report.exported += 1
        except Exception as exc:  # noqa: BLE001 - één fout stopt de run niet / one error does not stop the run
            log.error("Bulk export failed for %s: %s", job.path, exc)
            self.report.failed.append((job, str(exc)))
            self.item_failed.emit(job, str(exc))
        self._index += 1
        if self._index >= len(self._jobs):
            self._finish()
            return
        self.progress.emit(self._index + 1, len(self._jobs), self._jobs[self._index].label)
        QTimer.singleShot(0, self._step)

    def _finish(self) -> None:
        self._done = True
        self.finished.emit(self.report)
