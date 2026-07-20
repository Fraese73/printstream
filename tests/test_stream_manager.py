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
        video_fps=15,
        video_bitrate="2500k",
    )
    c = StreamManager(s).build_command()
    assert c[0] == "ffmpeg"
    assert "http://cam" in c
    assert "rtmps://example/live2/test" in c
    assert "-use_wallclock_as_timestamps" in c
    assert "-fps_mode" in c
    assert "cfr" in c
    assert any(part.startswith("fps=15,") for part in c)
    assert "5000k" in c  # bufsize = 2x bitrate
    assert c[c.index("-g") + 1] == "30"


def test_requires_stream_key() -> None:
    with pytest.raises(ValueError):
        StreamManager(Settings(youtube_stream_key="")).build_command()


def test_requires_webcam_url() -> None:
    with pytest.raises(ValueError, match="Webcam"):
        StreamManager(
            Settings(youtube_stream_key="test", octoprint_webcam_url="")
        ).build_command()


def test_clamps_fps_below_youtube_minimum() -> None:
    command = StreamManager(
        Settings(
            youtube_stream_key="test",
            octoprint_webcam_url="http://cam",
            video_fps=5,
        )
    ).build_command()
    assert any(part.startswith("fps=15,") for part in command)
    assert command[command.index("-r") + 1] == "15"
    assert command[command.index("-g") + 1] == "30"


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

    @pytest.mark.asyncio
async def test_start_persists_desired_running(tmp_path: Path) -> None:
    settings = Settings(youtube_stream_key="test", octoprint_webcam_url="http://cam")
    manager = StreamManager(settings)
    manager.log_dir = tmp_path
    manager.desired_state_path = tmp_path / "desired_stream"

    fake_process = MagicMock()
    fake_process.returncode = None
    fake_process.pid = 42

    with patch(
        "app.services.stream_manager.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=fake_process,
    ):
        status = await manager.start()

    assert status.desired_running is True
    assert manager.is_desired_running() is True


@pytest.mark.asyncio
async def test_stop_clears_desired_running(tmp_path: Path) -> None:
    settings = Settings(youtube_stream_key="test", octoprint_webcam_url="http://cam")
    manager = StreamManager(settings)
    manager.log_dir = tmp_path
    manager.desired_state_path = tmp_path / "desired_stream"
    manager.set_desired_running(True)
    manager.process = MagicMock(returncode=None)
    manager.process.wait = AsyncMock()

    status = await manager.stop()

    assert status.desired_running is False
    assert manager.is_desired_running() is False


@pytest.mark.asyncio
async def test_stop_without_user_request_keeps_desired(tmp_path: Path) -> None:
    settings = Settings(youtube_stream_key="test", octoprint_webcam_url="http://cam")
    manager = StreamManager(settings)
    manager.log_dir = tmp_path
    manager.desired_state_path = tmp_path / "desired_stream"
    manager.set_desired_running(True)
    manager.process = MagicMock(returncode=0)

    await manager.stop(user_requested=False)

    assert manager.is_desired_running() is True


@pytest.mark.asyncio
async def test_resume_if_desired_starts_stream(tmp_path: Path) -> None:
    settings = Settings(
        youtube_stream_key="test",
        octoprint_webcam_url="http://cam",
        stream_auto_resume=True,
        stream_resume_delay_seconds=0,
    )
    manager = StreamManager(settings)
    manager.log_dir = tmp_path
    manager.desired_state_path = tmp_path / "desired_stream"
    manager.set_desired_running(True)

    fake_process = MagicMock()
    fake_process.returncode = None
    fake_process.pid = 99

    with patch(
        "app.services.stream_manager.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=fake_process,
    ) as mock_exec:
        await manager.resume_if_desired()

    mock_exec.assert_awaited_once()
    assert manager.state == StreamState.RUNNING


@pytest.mark.asyncio
async def test_resume_retries_after_failure(tmp_path: Path) -> None:
    settings = Settings(
        youtube_stream_key="test",
        octoprint_webcam_url="http://cam",
        stream_auto_resume=True,
        stream_resume_delay_seconds=0,
    )
    manager = StreamManager(settings)
    manager.log_dir = tmp_path
    manager.desired_state_path = tmp_path / "desired_stream"
    manager.set_desired_running(True)

    fake_process = MagicMock()
    fake_process.returncode = None
    fake_process.pid = 100

    with (
        patch(
            "app.services.stream_manager.asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            side_effect=[OSError("network down"), fake_process],
        ) as mock_exec,
        patch("app.services.stream_manager.asyncio.sleep", new_callable=AsyncMock),
    ):
        await manager.resume_if_desired()

    assert mock_exec.await_count == 2
    assert manager.state == StreamState.RUNNING
