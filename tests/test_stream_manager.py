from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.core.models import StreamState
from app.services.stream_manager import StreamManager


def test_build_command() -> None:
    s = Settings(
        octoprint_webcam_url="http://cam",
        youtube_rtmps_url="rtmps://example/live2",
        youtube_stream_key="test",
    )
    c = StreamManager(s).build_command()
    assert c[0] == "ffmpeg"
    assert "http://cam" in c
    assert "rtmps://example/live2/test" in c


def test_requires_stream_key() -> None:
    with pytest.raises(ValueError):
        StreamManager(Settings(youtube_stream_key="")).build_command()


@pytest.mark.asyncio
async def test_start_closes_log_handle_on_success(tmp_path: Path) -> None:
    settings = Settings(youtube_stream_key="test", octoprint_webcam_url="http://cam")
    manager = StreamManager(settings)
    manager.log_dir = tmp_path

    fake_process = MagicMock()
    fake_process.returncode = None
    fake_process.pid = 1234

    with patch(
        "app.services.stream_manager.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=fake_process,
    ) as mock_exec:
        status = await manager.start()

    assert status.state == StreamState.RUNNING
    log_handle = mock_exec.await_args.kwargs["stdout"]
    assert log_handle.closed


@pytest.mark.asyncio
async def test_start_closes_log_handle_on_failure(tmp_path: Path) -> None:
    settings = Settings(youtube_stream_key="test", octoprint_webcam_url="http://cam")
    manager = StreamManager(settings)
    manager.log_dir = tmp_path
    opened: list[object] = []

    real_open = open

    def tracking_open(*args: object, **kwargs: object) -> object:
        handle = real_open(*args, **kwargs)
        opened.append(handle)
        return handle

    with (
        patch("builtins.open", side_effect=tracking_open),
        patch(
            "app.services.stream_manager.asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            side_effect=OSError("ffmpeg missing"),
        ),
    ):
        with pytest.raises(OSError, match="ffmpeg missing"):
            await manager.start()

    assert manager.state == StreamState.ERROR
    assert opened
    assert all(handle.closed for handle in opened)  # type: ignore[attr-defined]
