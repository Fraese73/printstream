from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from app.adapters.octoprint import OctoPrintAdapter
from app.config import Settings
from app.services.stream_manager import StreamManager

logger = logging.getLogger(__name__)


def is_print_active(status: dict[str, Any]) -> bool:
    """True während Druck oder Pause (nicht bei reinem Idle / Abbruch-Ende)."""
    if not status.get("connected"):
        return False
    state = status.get("state") or {}
    if not isinstance(state, dict):
        return False
    flags = state.get("flags") or {}
    if not isinstance(flags, dict):
        return False
    return bool(
        flags.get("printing")
        or flags.get("paused")
        or flags.get("pausing")
    )


# Alias für bestehende Imports/Tests
def is_printing(status: dict[str, Any]) -> bool:
    return is_print_active(status)


class PrintAutomation:
    """Pollt OctoPrint und startet/stoppt den Stream bei Druckbeginn/-ende."""

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

    @property
    def enabled(self) -> bool:
        return self.settings.auto_start_on_print or self.settings.auto_stop_on_print_end

    async def start(self) -> None:
        if not self.enabled:
            logger.info("Print-Automation ist deaktiviert (Start/Stop aus).")
            return
        if self.running:
            return
        self._was_printing = None
        self._task = asyncio.create_task(self._run(), name="print-automation")
        logger.info(
            "Print-Automation gestartet (Poll alle %.0fs, start=%s, stop=%s).",
            self.settings.auto_print_poll_seconds,
            self.settings.auto_start_on_print,
            self.settings.auto_stop_on_print_end,
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
        # Kurze Disconnects nicht als Druckende werten.
        if not status.get("connected"):
            logger.debug("Print-Automation: OctoPrint nicht erreichbar, überspringe Tick.")
            return

        printing = is_print_active(status)

        if self._was_printing is None:
            # Erste Messung nur als Baseline – kein Start/Stop mitten im laufenden Druck.
            self._was_printing = printing
            logger.info(
                "Print-Automation Baseline: print_active=%s",
                printing,
            )
            return

        if printing and not self._was_printing:
            if self.settings.auto_start_on_print:
                await self._on_print_started()
        elif not printing and self._was_printing:
            if self.settings.auto_stop_on_print_end:
                await self._on_print_ended()

        self._was_printing = printing

    async def _on_print_started(self) -> None:
        logger.info("Druckbeginn erkannt – starte Stream.")
        try:
            await self.stream_manager.start(user_requested=True)
        except Exception as exc:
            logger.warning("Auto-Start bei Druckbeginn fehlgeschlagen: %s", exc)

    async def _on_print_ended(self) -> None:
        logger.info("Druckende erkannt – stoppe Stream.")
        try:
            await self.stream_manager.stop(user_requested=True)
        except Exception as exc:
            logger.warning("Auto-Stop bei Druckende fehlgeschlagen: %s", exc)
