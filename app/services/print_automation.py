from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from app.adapters.octoprint import OctoPrintAdapter
from app.config import Settings
from app.services.stream_manager import StreamManager

logger = logging.getLogger(__name__)


def is_printing(status: dict[str, Any]) -> bool:
    if not status.get("connected"):
        return False
    state = status.get("state") or {}
    if not isinstance(state, dict):
        return False
    flags = state.get("flags") or {}
    if not isinstance(flags, dict):
        return False
    return bool(flags.get("printing"))


class PrintAutomation:
    """Pollt OctoPrint und startet den Stream bei Druckbeginn (Rising Edge)."""

    def __init__(
        self,
        settings: Settings,
        octoprint: OctoPrintAdapter,
        stream_manager: StreamManager,
    ) -> None:
        self.settings = settings
        self.octoprint = octoprint
        self.stream_manager = stream_manager
        self._task: Optional[asyncio.Task[None]] = None
        self._was_printing: Optional[bool] = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if not self.settings.auto_start_on_print:
            logger.info("Auto-Start bei Druckbeginn ist deaktiviert.")
            return
        if self.running:
            return
        self._was_printing = None
        self._task = asyncio.create_task(self._run(), name="print-automation")
        logger.info(
            "Print-Automation gestartet (Poll alle %.0fs).",
            self.settings.auto_print_poll_seconds,
        )

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Print-Automation gestoppt.")

    async def _run(self) -> None:
        try:
            while True:
                await self.tick()
                await asyncio.sleep(max(1.0, self.settings.auto_print_poll_seconds))
        except asyncio.CancelledError:
            raise

    async def tick(self) -> None:
        status = await self.octoprint.get_status()
        printing = is_printing(status)

        if self._was_printing is None:
            # Erste Messung nur als Baseline – kein Start mitten im laufenden Druck.
            self._was_printing = printing
            logger.info(
                "Print-Automation Baseline: printing=%s",
                printing,
            )
            return

        if printing and not self._was_printing:
            await self._on_print_started()

        self._was_printing = printing

    async def _on_print_started(self) -> None:
        logger.info("Druckbeginn erkannt – starte Stream.")
        try:
            await self.stream_manager.start(user_requested=True)
        except Exception as exc:
            logger.warning("Auto-Start bei Druckbeginn fehlgeschlagen: %s", exc)
