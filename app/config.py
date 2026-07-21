from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_host: str = "0.0.0.0"
    app_port: int = 8088
    log_level: str = "INFO"
    octoprint_base_url: str = "http://192.168.2.59"
    octoprint_api_key: str = ""
    octoprint_webcam_url: str = "http://192.168.2.59/webcam/?action=stream"
    youtube_rtmps_url: str = "rtmps://a.rtmps.youtube.com/live2"
    youtube_stream_key: str = ""
    video_width: int = 1280
    video_height: int = 720
    video_fps: int = 15
    video_bitrate: str = "3000k"
    audio_bitrate: str = "128k"
    stream_auto_resume: bool = True
    stream_resume_delay_seconds: float = 45.0
    stream_auto_restart: bool = True
    stream_restart_delay_seconds: float = 10.0
    stream_restart_max_attempts: int = 0
    overlay_enabled: bool = True
    overlay_font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    overlay_font_size: int = 28
    overlay_font_color: str = "white"
    overlay_x: str = "24"
    overlay_y: str = "24"
    overlay_interval_seconds: float = 5.0
    overlay_logo_enabled: bool = True
    overlay_logo_path: str = "assets/logo.png"
    overlay_logo_width: int = 120
    overlay_logo_x: str = "W-w-24"
    overlay_logo_y: str = "24"
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
