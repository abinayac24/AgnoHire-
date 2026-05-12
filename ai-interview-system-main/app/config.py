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

    def __post_init__(self) -> None:
        origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5000,http://127.0.0.1:5000,http://localhost:49180,http://127.0.0.1:49180")
        self.cors_origins = [origin.strip() for origin in origins.split(",") if origin.strip()]
        # Also allow all localhost origins for development
        self.cors_origins.extend([
            "http://localhost:*",
            "http://127.0.0.1:*",
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ])
        # Remove duplicates
        self.cors_origins = list(dict.fromkeys(self.cors_origins))


settings = Settings()
