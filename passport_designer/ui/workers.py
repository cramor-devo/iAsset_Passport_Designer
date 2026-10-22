"""Achtergrondtaken: lange bewerkingen (Excel lezen) blokkeren de UI niet.
Background jobs: long operations (reading Excel) never block the UI."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

log = logging.getLogger(__name__)


class JobSignals(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(object)
    progress = pyqtSignal(str)


class Job(QRunnable):
    """Voert ``func(progress)`` uit op een werkthread. / Runs ``func(progress)`` on a worker thread."""

    def __init__(self, func: Callable[[Callable[[str], None]], Any]) -> None:
        super().__init__()
        self.signals = JobSignals()
        self._func = func

    def run(self) -> None:
        try:
            result = self._func(self.signals.progress.emit)
        except Exception as exc:  # noqa: BLE001 - elke fout wordt gelogd en gemeld / every error is logged and reported
            log.exception("Background job failed")
            self.signals.failed.emit(exc)
        else:
            self.signals.finished.emit(result)


def run_job(job: Job) -> None:
    pool = QThreadPool.globalInstance()
    if pool is not None:
        pool.start(job)
