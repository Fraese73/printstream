import asyncio
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.core.models import StreamState

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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class StreamManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.process: Optional[asyncio.subprocess.Process] = None
        self.state = StreamState.STOPPED
        self.last_error: Optional[str] = None
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

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

        width = self.settings.video_width
        height = self.settings.video_height
        bitrate = self.settings.video_bitrate
        gop = str(fps * 2)
        output_url = (
            f"{self.settings.youtube_rtmps_url.rstrip('/')}/"
            f"{self.settings.youtube_stream_key}"
        )
        video_filter = (
            f"fps={fps},"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            "format=yuv420p"
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
            video_filter,
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

    async def start(self) -> StreamStatus:
        if self.process and self.process.returncode is None:
            return self.status()
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
            raise
        finally:
            # Child already inherited the FDs; always close the parent's handle.
            log_handle.close()

    async def stop(self) -> StreamStatus:
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

    def status(self) -> StreamStatus:
        return StreamStatus(self.state, self.process.pid if self.process else None, self.process.returncode if self.process else None, self.last_error)
