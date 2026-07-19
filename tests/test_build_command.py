from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.overlay import build_overlay_text, format_remaining, format_temp
from app.stream_manager import StreamManager, bufsize_from_bitrate, parse_bitrate_k


def make_settings(**overrides) -> Settings:
    data = {
        "octoprint_webcam_url": "http://192.168.2.59/webcam/?action=stream",
        "youtube_rtmps_url": "rtmps://a.rtmps.youtube.com/live2",
        "youtube_stream_key": "secret-stream-key-xyz",
        "video_width": 1280,
        "video_height": 720,
        "video_fps": 15,
        "video_bitrate": "3000k",
        "audio_bitrate": "128k",
        "overlay_enabled": False,
        "overlay_font_path": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    }
    data.update(overrides)
    return Settings(**data)


def test_parse_bitrate_k():
    assert parse_bitrate_k("3000k") == 3000
    assert parse_bitrate_k("2M") == 2000
    assert parse_bitrate_k("128") == 128


def test_bufsize_from_bitrate():
    assert bufsize_from_bitrate("3000k") == "6000k"
    assert bufsize_from_bitrate("2500k") == "5000k"


def test_build_command_structure():
    manager = StreamManager(make_settings())
    command = manager.build_command()

    assert isinstance(command, list)
    assert all(isinstance(part, str) for part in command)
    assert command[0] == "ffmpeg"
    assert "-i" in command
    assert "libx264" in command
    assert "veryfast" in command
    assert "3000k" in command
    assert "6000k" in command
    assert "15" in command
    assert any("scale=1280:720" in part for part in command)
    assert "-reconnect" in command
    assert "-reconnect_streamed" in command
    assert "+genpts" in command
    assert command[-1] == "rtmps://a.rtmps.youtube.com/live2/secret-stream-key-xyz"
    assert command[-2] == "flv"


def test_build_command_requires_stream_key():
    manager = StreamManager(make_settings(youtube_stream_key=""))
    with pytest.raises(ValueError, match="Streamschlüssel"):
        manager.build_command()


def test_build_command_requires_webcam_url():
    manager = StreamManager(make_settings(octoprint_webcam_url=""))
    with pytest.raises(ValueError, match="Webcam"):
        manager.build_command()


def test_stream_key_only_in_output_url():
    key = "secret-stream-key-xyz"
    manager = StreamManager(make_settings(youtube_stream_key=key))
    command = manager.build_command()
    occurrences = [part for part in command if key in part]
    assert len(occurrences) == 1
    assert occurrences[0].endswith(f"/{key}")


def test_redact_removes_stream_key():
    key = "secret-stream-key-xyz"
    manager = StreamManager(make_settings(youtube_stream_key=key))
    raw = f"Error opening output rtmps://a.rtmps.youtube.com/live2/{key}"
    assert key not in manager.redact(raw)
    assert "***REDACTED***" in manager.redact(raw)


def test_overlay_drawtext_when_enabled(tmp_path: Path):
    manager = StreamManager(
        make_settings(
            overlay_enabled=True,
            overlay_font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        )
    )
    manager.log_dir = tmp_path
    manager.overlay_path = tmp_path / "overlay.txt"
    vf = manager.build_video_filter()
    assert "drawtext=" in vf
    assert "reload=1" in vf
    assert "textfile=" in vf


def test_format_helpers():
    assert format_remaining(3661) == "1:01:01"
    assert format_remaining(90) == "1:30"
    assert format_remaining(None) == "--:--"
    assert format_temp({"actual": 210.4, "target": 215}) == "210/215°C"
    assert format_temp(None) == "--"


def test_build_overlay_text_connected():
    text = build_overlay_text(
        {
            "connected": True,
            "state": {"text": "Printing", "flags": {"printing": True}},
            "temperature": {
                "tool0": {"actual": 200, "target": 200},
                "bed": {"actual": 60, "target": 60},
            },
            "job": {"file": {"display": "benchy.gcode"}},
            "progress": {"completion": 42.5, "printTimeLeft": 600},
        }
    )
    assert "benchy.gcode" in text
    assert "42.5%" in text
    assert "Düse 200/200°C" in text
    assert "Bett 60/60°C" in text
    assert "Rest 10:00" in text


def test_health_and_status_endpoints(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("YOUTUBE_STREAM_KEY", "test-key")
    monkeypatch.setenv("OCTOPRINT_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()

    import app.main as main_module

    main_module.stream_manager.log_dir = tmp_path
    main_module.stream_manager.log_path = tmp_path / "ffmpeg.log"
    main_module.stream_manager.overlay_path = tmp_path / "overlay.txt"

    client = TestClient(main_module.app)
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["service"] == "PrintStream"
    assert "ffmpeg_available" in body
    assert body["stream_running"] is False

    status = client.get("/api/stream/status")
    assert status.status_code == 200
    assert status.json()["running"] is False
    assert "log_tail" in status.json()

    get_settings.cache_clear()
