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
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

@lru_cache
def get_settings() -> Settings:
    return Settings()
