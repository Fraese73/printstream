from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.adapters.octoprint import OctoPrintAdapter
from app.config import Settings

logger = logging.getLogger(__name__)


def format_remaining(seconds: Any) -> str:
    if seconds is None:
        return "--:--"
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return "--:--"
    if total < 0:
        return "--:--"
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


def format_temp(block: Any) -> str:
    if not isinstance(block, dict):
        return "--"
    actual = block.get("actual")
    target = block.get("target")
    try:
        actual_s = f"{float(actual):.0f}" if actual is not None else "--"
    except (TypeError, ValueError):
        actual_s = "--"
    try:
        target_s = f"{float(target):.0f}" if target is not None else "--"
    except (TypeError, ValueError):
        target_s = "--"
    return f"{actual_s}/{target_s}°C"


def format_layer(progress: Any) -> str:
    """Layer aus DisplayLayerProgress o. ä., sonst Platzhalter."""
    if not isinstance(progress, dict):
        return "—"
    current = progress.get("currentLayer") or progress.get("layer")
    total = progress.get("totalLayer") or progress.get("layerCount")
    if current is None and total is None:
        return "—"
    try:
        cur_s = str(int(float(current))) if current is not None else "—"
    except (TypeError, ValueError):
        cur_s = "—"
    try:
        tot_s = str(int(float(total))) if total is not None else "—"
    except (TypeError, ValueError):
        tot_s = "—"
    return f"{cur_s}/{tot_s}"


def build_overlay_text(status: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc).astimezone().strftime("%H:%M")
    if not status.get("connected"):
        error = status.get("error") or "OctoPrint nicht erreichbar"
        return f"PrintStream  {now}\n{error}\n"

    job = status.get("job") or {}
    progress = status.get("progress") or {}
    temperature = status.get("temperature") or {}
    state = status.get("state") or {}

    file_info = job.get("file") if isinstance(job, dict) else {}
    filename = (file_info or {}).get("display") or (file_info or {}).get("name") or "—"
    completion = progress.get("completion") if isinstance(progress, dict) else None
    try:
        pct = f"{float(completion):.1f}%" if completion is not None else "—%"
    except (TypeError, ValueError):
        pct = "—%"

    print_time_left = progress.get("printTimeLeft") if isinstance(progress, dict) else None
    remaining = format_remaining(print_time_left)
    layer = format_layer(progress)
    tool = format_temp(temperature.get("tool0") if isinstance(temperature, dict) else None)
    bed = format_temp(temperature.get("bed") if isinstance(temperature, dict) else None)
    flags = state.get("flags") if isinstance(state, dict) else {}
    printing = bool(flags.get("printing")) if isinstance(flags, dict) else False
    state_text = state.get("text") if isinstance(state, dict) else None
    mode = state_text or ("Druck" if printing else "Bereit")

    return (
        f"PrintStream  {now}  |  {mode}\n"
        f"{filename}\n"
        f"Fortschritt {pct}  |  Layer {layer}  |  Rest {remaining}\n"
        f"Düse {tool}  |  Bett {bed}\n"
    )


class OverlayWriter:
    def __init__(
        self,
        settings: Settings,
        octoprint: OctoPrintAdapter,
        overlay_path: Path,
    ) -> None:
        self.settings = settings
        self.octoprint = octoprint
        self.overlay_path = overlay_path
        self._task: Optional[asyncio.Task[None]] = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def ensure_file(self) -> None:
        self.overlay_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.overlay_path.exists():
            self.overlay_path.write_text(
                "PrintStream\nWarte auf Druckdaten …\n",
                encoding="utf-8",
            )

    async def start(self) -> None:
        if not self.settings.overlay_enabled:
            return
        if self.running:
            return
        self.ensure_file()
        await self.refresh()
        self._task = asyncio.create_task(self._run(), name="overlay-writer")
        logger.info("Overlay-Writer gestartet (%s).", self.overlay_path)

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Overlay-Writer gestoppt.")

    async def _run(self) -> None:
        try:
            while True:
                await self.refresh()
                await asyncio.sleep(self.settings.overlay_interval_seconds)
        except asyncio.CancelledError:
            raise

    async def refresh(self) -> None:
        status = await self.octoprint.get_status()
        text = build_overlay_text(status)
        self.overlay_path.write_text(text, encoding="utf-8")
