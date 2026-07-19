import pytest
from app.config import Settings
from app.services.stream_manager import StreamManager

def test_build_command() -> None:
    s=Settings(octoprint_webcam_url="http://cam",youtube_rtmps_url="rtmps://example/live2",youtube_stream_key="test")
    c=StreamManager(s).build_command()
    assert c[0]=="ffmpeg"
    assert "http://cam" in c
    assert "rtmps://example/live2/test" in c

def test_requires_stream_key() -> None:
    with pytest.raises(ValueError):
        StreamManager(Settings(youtube_stream_key="")).build_command()
