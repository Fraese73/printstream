import asyncio
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.core.models import StreamState
from app.services.overlay import OverlayWriter

logger = logging.getLogger(__name__)


def parse_bitrate_k(bitrate: str) -> int:
    match = re.fullmatch(r"(\d+)([kKmM]?)", bitrate.strip())
    if not match:
        raise ValueError(f"Ungültige Bitrate: {bitrate}")
    value = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "m":
        return value * 1000
    return value


def bufsize_from_bitrate(video_bitrate: str) -> str:
    return f"{parse_bitrate_k(video_bitrate) * 2}k"


@dataclass
class StreamStatus:
    state: StreamState
    pid: Optional[int] = None
    return_code: Optional[int] = None
    last_error: Optional[str] = None
    desired_running: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class StreamManager:
    def __init__(
        self,
        settings: Settings,
        overlay: Optional[OverlayWriter] = None,
    ) -> None:
        self.settings = settings
        self.overlay = overlay
        self.process: Optional[asyncio.subprocess.Process] = None
        self.state = StreamState.STOPPED
        self.last_error: Optional[str] = None
        self.log_dir = Path("logs").resolve()
        self.log_dir.mkdir(exist_ok=True)
        self.desired_state_path = self.log_dir / "desired_stream"
        self.overlay_path = self.log_dir / "overlay.txt"

    def is_desired_running(self) -> bool:
        try:
            return self.desired_state_path.read_text(encoding="utf-8").strip() == "running"
        except OSError:
            return False

    def set_desired_running(self, running: bool) -> None:
        self.desired_state_path.write_text(
            "running" if running else "stopped",
            encoding="utf-8",
        )

    def build_video_filter(self, fps: int) -> str:
        width = self.settings.video_width
        height = self.settings.video_height
        filters = [
            f"fps={fps}",
            f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "format=yuv420p",
        ]
        if self.settings.overlay_enabled:
            fontfile = self.settings.overlay_font_path.replace(":", "\\:")
            textfile = str(self.overlay_path.resolve()).replace(":", "\\:")
            filters.append(
                "drawtext="
                f"fontfile={fontfile}:"
                f"textfile={textfile}:"
                "reload=1:"
                "expansion=none:"
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

        fps = self.settings.video_fps
        if fps < 15:
            logger.warning(
                "VIDEO_FPS=%s ist zu niedrig für YouTube Live – verwende 15 FPS.",
                fps,
            )
            fps = 15

        bitrate = self.settings.video_bitrate
        gop = str(fps * 2)
        output_url = (
            f"{self.settings.youtube_rtmps_url.rstrip('/')}/"
            f"{self.settings.youtube_stream_key}"
        )

        # Wallclock + CFR: OctoPrint-MJPEG ist oft VFR; YouTube braucht stabile Zeitstempel.
        return [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-reconnect",
            "1",
            "-reconnect_streamed",
            "1",
            "-reconnect_delay_max",
            "5",
            "-rw_timeout",
            "15000000",
            "-fflags",
            "+genpts+discardcorrupt",
            "-use_wallclock_as_timestamps",
            "1",
            "-thread_queue_size",
            "512",
            "-i",
            self.settings.octoprint_webcam_url,
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-vf",
            self.build_video_filter(fps),
            "-r",
            str(fps),
            "-fps_mode",
            "cfr",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            bitrate,
            "-minrate",
            bitrate,
            "-maxrate",
            bitrate,
            "-bufsize",
            bufsize_from_bitrate(bitrate),
            "-g",
            gop,
            "-keyint_min",
            gop,
            "-sc_threshold",
            "0",
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

    async def start(self, *, user_requested: bool = True) -> StreamStatus:
        if user_requested:
            self.set_desired_running(True)
        if self.process and self.process.returncode is None:
            return self.status()

        if self.settings.overlay_enabled:
            if self.overlay:
                await self.overlay.start()
            else:
                self.overlay_path.parent.mkdir(parents=True, exist_ok=True)
                if not self.overlay_path.exists():
                    self.overlay_path.write_text(
                        "PrintStream\nWarte auf Druckdaten …\n",
                        encoding="utf-8",
                    )

        self.state = StreamState.STARTING
        log_handle = open(self.log_dir / "ffmpeg.log", "ab", buffering=0)
        try:
            self.process = await asyncio.create_subprocess_exec(
                *self.build_command(),
                stdout=log_handle,
                stderr=log_handle,
            )
            self.state = StreamState.RUNNING
            self.last_error = None
            return self.status()
        except Exception as exc:
            self.state = StreamState.ERROR
            self.last_error = str(exc)
            if self.overlay:
                await self.overlay.stop()
            raise
        finally:
            # Child already inherited the FDs; always close the parent's handle.
            log_handle.close()

    async def stop(self, *, user_requested: bool = True) -> StreamStatus:
        if user_requested:
            self.set_desired_running(False)
        if self.overlay:
            await self.overlay.stop()
        if not self.process or self.process.returncode is not None:
            self.state = StreamState.STOPPED
            return self.status()
        self.state = StreamState.STOPPING
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=10)
        except asyncio.TimeoutError:
            self.process.kill()
            await self.process.wait()
        self.state = StreamState.STOPPED
        return self.status()

    async def resume_if_desired(self) -> None:
        if not self.settings.stream_auto_resume:
            logger.info("Auto-Resume ist deaktiviert (STREAM_AUTO_RESUME=false).")
            return
        if not self.is_desired_running():
            logger.info(
                "Kein Auto-Resume: %s ist nicht 'running' (vorher einmal Start klicken).",
                self.desired_state_path,
            )
            return

        delay = max(0.0, self.settings.stream_resume_delay_seconds)
        logger.info(
            "Auto-Resume: Stream war aktiv – warte %.0fs, dann bis zu 5 Startversuche.",
            delay,
        )
        if delay:
            await asyncio.sleep(delay)

        last_error: Optional[Exception] = None
        for attempt in range(1, 6):
            if not self.is_desired_running():
                logger.info("Auto-Resume abgebrochen: gewünschter Zustand nicht mehr 'running'.")
                return
            if self.process and self.process.returncode is None:
                logger.info("Auto-Resume: Stream läuft bereits.")
                return
            try:
                await self.start(user_requested=False)
                logger.info("Auto-Resume erfolgreich (Versuch %s/5).", attempt)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                self.last_error = str(exc)
                logger.warning(
                    "Auto-Resume Versuch %s/5 fehlgeschlagen: %s",
                    attempt,
                    exc,
                )
                await asyncio.sleep(30)

        logger.error("Auto-Resume endgültig fehlgeschlagen: %s", last_error)
        self.state = StreamState.ERROR

    def status(self) -> StreamStatus:
        return StreamStatus(
            state=self.state,
            pid=self.process.pid if self.process else None,
            return_code=self.process.returncode if self.process else None,
            last_error=self.last_error,
            desired_running=self.is_desired_running(),
        )
