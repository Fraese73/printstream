from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Optional

from app.config import Settings


def parse_bitrate_k(bitrate: str) -> int:
    """Parse a bitrate like '3000k' or '128k' into kilobits."""
    match = re.fullmatch(r"(\d+)([kKmM]?)", bitrate.strip())
    if not match:
        raise ValueError(f"Ungültige Bitrate: {bitrate}")
    value = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "m":
        return value * 1000
    return value


def bufsize_from_bitrate(video_bitrate: str) -> str:
    """Derive FFmpeg bufsize as roughly 2x video bitrate."""
    return f"{parse_bitrate_k(video_bitrate) * 2}k"


@dataclass
class StreamStatus:
    running: bool
    pid: Optional[int] = None
    return_code: Optional[int] = None
    last_error: Optional[str] = None
    log_tail: list[str] = field(default_factory=list)


class StreamManager:
    LOG_TAIL_LINES = 30

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.process: Optional[asyncio.subprocess.Process] = None
        self.last_error: Optional[str] = None
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        self.log_path = self.log_dir / "ffmpeg.log"
        self.overlay_path = self.log_dir / "overlay.txt"
        self._log_file: Optional[IO[bytes]] = None
        self._watch_task: Optional[asyncio.Task[None]] = None
        self._stopping: bool = False

    def redact(self, text: str) -> str:
        """Remove the YouTube stream key from any text that may be logged or returned."""
        key = self.settings.youtube_stream_key
        if not key:
            return text
        return text.replace(key, "***REDACTED***")

    def _close_log_file(self) -> None:
        if self._log_file is not None and not self._log_file.closed:
            self._log_file.close()
        self._log_file = None

    def read_log_tail(self, max_lines: int | None = None) -> list[str]:
        limit = max_lines if max_lines is not None else self.LOG_TAIL_LINES
        if not self.log_path.exists():
            return []
        try:
            content = self.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        lines = [self.redact(line.rstrip("\n")) for line in content.splitlines() if line.strip()]
        return lines[-limit:]

    def build_video_filter(self) -> str:
        width = self.settings.video_width
        height = self.settings.video_height
        filters = [
            f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        ]
        if self.settings.overlay_enabled:
            fontfile = self.settings.overlay_font_path.replace(":", "\\:")
            textfile = str(self.overlay_path.resolve()).replace(":", "\\:")
            filters.append(
                "drawtext="
                f"fontfile={fontfile}:"
                f"textfile={textfile}:"
                "reload=1:"
                f"fontsize={self.settings.overlay_font_size}:"
                f"fontcolor={self.settings.overlay_font_color}:"
                f"x={self.settings.overlay_x}:"
                f"y={self.settings.overlay_y}:"
                "box=1:boxcolor=black@0.45:boxborderw=8"
            )
        return ",".join(filters)

    def build_command(self) -> list[str]:
        if not self.settings.youtube_stream_key:
            raise ValueError("Kein YouTube-Streamschlüssel konfiguriert.")
        if not self.settings.octoprint_webcam_url:
            raise ValueError("Keine OctoPrint-Webcam-URL konfiguriert.")

        output_url = (
            f"{self.settings.youtube_rtmps_url.rstrip('/')}/"
            f"{self.settings.youtube_stream_key}"
        )
        bufsize = bufsize_from_bitrate(self.settings.video_bitrate)
        gop = str(self.settings.video_fps * 2)

        return [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-thread_queue_size",
            "512",
            "-reconnect",
            "1",
            "-reconnect_streamed",
            "1",
            "-reconnect_delay_max",
            "5",
            "-fflags",
            "+genpts",
            "-analyzeduration",
            "1000000",
            "-probesize",
            "1000000",
            "-i",
            self.settings.octoprint_webcam_url,
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-vf",
            self.build_video_filter(),
            "-r",
            str(self.settings.video_fps),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            self.settings.video_bitrate,
            "-maxrate",
            self.settings.video_bitrate,
            "-bufsize",
            bufsize,
            "-g",
            gop,
            "-c:a",
            "aac",
            "-b:a",
            self.settings.audio_bitrate,
            "-ar",
            "44100",
            "-f",
            "flv",
            output_url,
        ]

    def _ensure_overlay_file(self) -> None:
        if not self.overlay_path.exists():
            self.overlay_path.write_text("PrintStream\nWarte auf Druckdaten …\n", encoding="utf-8")

    async def _watch_process(self, process: asyncio.subprocess.Process) -> None:
        return_code = await process.wait()
        self._close_log_file()
        if not self._stopping and return_code not in (0, None):
            tail = self.read_log_tail(10)
            detail = " | ".join(tail) if tail else f"FFmpeg beendet mit Code {return_code}"
            self.last_error = self.redact(detail)
        self._watch_task = None

    async def start(self) -> StreamStatus:
        if self.process and self.process.returncode is None:
            return self.status()

        command = self.build_command()
        if self.settings.overlay_enabled:
            self._ensure_overlay_file()

        self._stopping = False
        self._close_log_file()
        self._log_file = open(self.log_path, "ab", buffering=0)
        try:
            self.process = await asyncio.create_subprocess_exec(
                *command,
                stdout=self._log_file,
                stderr=self._log_file,
            )
            self.last_error = None
            if self._watch_task and not self._watch_task.done():
                self._watch_task.cancel()
            self._watch_task = asyncio.create_task(self._watch_process(self.process))
            return self.status()
        except Exception as exc:
            self.last_error = self.redact(str(exc))
            self._close_log_file()
            raise

    async def stop(self) -> StreamStatus:
        if not self.process or self.process.returncode is not None:
            self._close_log_file()
            return self.status()

        self._stopping = True
        process = self.process
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

        if self._watch_task and not self._watch_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self._watch_task), timeout=2)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._watch_task.cancel()

        self._close_log_file()
        self.last_error = None
        return self.status()

    def status(self) -> StreamStatus:
        log_tail = self.read_log_tail()
        if not self.process:
            return StreamStatus(
                running=False,
                last_error=self.last_error,
                log_tail=log_tail,
            )

        running = self.process.returncode is None
        if (
            not running
            and not self._stopping
            and self.last_error is None
            and self.process.returncode not in (0, None)
        ):
            tail = self.read_log_tail(10)
            detail = (
                " | ".join(tail)
                if tail
                else f"FFmpeg beendet mit Code {self.process.returncode}"
            )
            self.last_error = self.redact(detail)

        return StreamStatus(
            running=running,
            pid=self.process.pid,
            return_code=self.process.returncode,
            last_error=self.last_error,
            log_tail=log_tail,
        )
