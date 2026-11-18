"""Application configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings for the DarGlobal & Wasalt AI Chatbot."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "DarGlobal & Wasalt AI Assistant"
    app_public_url: str = "https://huggingface.co/spaces"
    host: str = "0.0.0.0"
    port: int = 7860

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/free"

    # Ordered fallback free models if the primary model is temporarily rate-limited
    fallback_free_models: list[str] = [
        "openrouter/free",
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "nvidia/nemotron-3.5-lightning:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "inclusionai/ling-3.2-flash:free",
    ]

    knowledge_base_path: Path = BASE_DIR / "data" / "knowledge_base.json"
    top_k_chunks: int = 6
    max_history_turns: int = 6


settings = Settings()
