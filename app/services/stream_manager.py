import asyncio
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional
from app.config import Settings
from app.core.models import StreamState

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
        output_url = f"{self.settings.youtube_rtmps_url.rstrip('/')}/{self.settings.youtube_stream_key}"
        return [
            "ffmpeg", "-hide_banner", "-loglevel", "warning",
            "-thread_queue_size", "512", "-i", self.settings.octoprint_webcam_url,
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-vf", f"scale={self.settings.video_width}:{self.settings.video_height}:force_original_aspect_ratio=decrease,pad={self.settings.video_width}:{self.settings.video_height}:(ow-iw)/2:(oh-ih)/2",
            "-r", str(self.settings.video_fps), "-c:v", "libx264", "-preset", "veryfast",
            "-tune", "zerolatency", "-pix_fmt", "yuv420p", "-b:v", self.settings.video_bitrate,
            "-maxrate", self.settings.video_bitrate, "-bufsize", "6000k",
            "-g", str(self.settings.video_fps * 2), "-c:a", "aac", "-b:a", self.settings.audio_bitrate,
            "-ar", "44100", "-f", "flv", output_url,
        ]

    async def start(self) -> StreamStatus:
        if self.process and self.process.returncode is None:
            return self.status()
        self.state = StreamState.STARTING
        log_handle = open(self.log_dir / "ffmpeg.log", "ab", buffering=0)
        try:
            self.process = await asyncio.create_subprocess_exec(*self.build_command(), stdout=log_handle, stderr=log_handle)
            self.state = StreamState.RUNNING
            self.last_error = None
            return self.status()
        except Exception as exc:
            self.state = StreamState.ERROR
            self.last_error = str(exc)
            log_handle.close()
            raise

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
