from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(slots=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "AI Voice Interview System API")
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    cors_origins: list[str] = None
    mongodb_url: str = os.getenv("MONGODB_URL", os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    mongodb_db_name: str = os.getenv("MONGODB_DB_NAME", os.getenv("MONGODB_DB", "ai_voice_interview"))
    use_in_memory_db: bool = os.getenv("USE_IN_MEMORY_DB", "false").lower() == "true"
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    gemini_timeout_seconds: float = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "3"))
    result_email_delay_seconds: int = int(os.getenv("RESULT_EMAIL_DELAY_SECONDS", "300"))
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_email: str = os.getenv("ADMIN_EMAIL", os.getenv("ADMIN_USERNAME", "admin"))
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")
    admin_password_hash: str = os.getenv("ADMIN_PASSWORD_HASH", "")
    interviewer_provider: str = os.getenv("INTERVIEWER_PROVIDER", "local").lower()
    interviewer_timeout_seconds: int = int(os.getenv("INTERVIEWER_TIMEOUT_SECONDS", "8"))
    did_api_key: str = os.getenv("DID_API_KEY", "")
    did_base_url: str = os.getenv("DID_BASE_URL", "https://api.d-id.com")
    did_source_url: str = os.getenv("DID_SOURCE_URL", "")
    did_voice_provider: str = os.getenv("DID_VOICE_PROVIDER", "microsoft")
    did_voice_id: str = os.getenv("DID_VOICE_ID", "en-US-JennyNeural")
    heygen_api_key: str = os.getenv("HEYGEN_API_KEY", "")
    heygen_base_url: str = os.getenv("HEYGEN_BASE_URL", "https://api.heygen.com")
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "")
    elevenlabs_model_id: str = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    local_avatar_video_url: str = os.getenv("LOCAL_AVATAR_VIDEO_URL", "")
    azure_tts_key: str = os.getenv("AZURE_TTS_KEY", "")
    azure_tts_region: str = os.getenv("AZURE_TTS_REGION", "")
    azure_tts_voice: str = os.getenv("AZURE_TTS_VOICE", "en-US-JennyNeural")
    sadtalker_enabled: bool = os.getenv("SADTALKER_ENABLED", "false").lower() == "true"
    sadtalker_python: str = os.getenv("SADTALKER_PYTHON", "")
    sadtalker_inference_script: str = os.getenv("SADTALKER_INFERENCE_SCRIPT", "")
    sadtalker_driven_audio_arg: str = os.getenv("SADTALKER_DRIVEN_AUDIO_ARG", "--driven_audio")
    sadtalker_source_image_arg: str = os.getenv("SADTALKER_SOURCE_IMAGE_ARG", "--source_image")
    sadtalker_result_dir_arg: str = os.getenv("SADTALKER_RESULT_DIR_ARG", "--result_dir")
    sadtalker_source_image_path: str = os.getenv("SADTALKER_SOURCE_IMAGE_PATH", "")

    def __post_init__(self) -> None:
        origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:52900,http://127.0.0.1:5000,http://localhost:5000,http://127.0.0.1:8000,http://localhost:8000")
        self.cors_origins = [origin.strip() for origin in origins.split(",") if origin.strip()]
        # Also allow any localhost origin for development
        self.cors_origins.extend(["http://localhost:5000", "http://127.0.0.1:5000", "http://localhost:8000", "http://127.0.0.1:8000"])
        # Remove duplicates while preserving order
        seen = set()
        self.cors_origins = [x for x in self.cors_origins if not (x in seen or seen.add(x))]


settings = Settings()
