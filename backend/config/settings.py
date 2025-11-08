"""Application settings and configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application
    app_name: str = "Town of Silicon"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # LLM Configuration
    llm_provider: Literal["local", "openrouter"] = "local"
    llm_model_path: str = "../models/oss-20b-Q4_K_M.gguf"
    llm_context_size: int = 65536  # 64K context!
    llm_temperature: float = 0.7
    llm_max_tokens: int = 200
    llm_timeout: int = 30

    # Metal/GPU Configuration (M4 Pro optimized)
    llm_n_gpu_layers: int = -1  # All layers on GPU
    llm_n_threads: int = 10  # M4 Pro has 10 P-cores
    llm_n_batch: int = 512
    llm_use_mlock: bool = True  # Keep model in RAM

    # OpenRouter (fallback)
    openrouter_api_key: str | None = None
    openrouter_model: str = "anthropic/claude-3.5-sonnet"

    # Game Settings
    game_mode: Literal["classic", "ranked", "custom"] = "classic"
    day_base_duration: float = 45.0
    night_base_duration: float = 30.0
    defense_duration: float = 20.0
    judgment_duration: float = 20.0

    # AI Settings
    ai_batch_size: int = 4  # Process 4 AIs at once
    ai_enable_extensions: bool = True
    ai_max_extensions: int = 10

    # Performance
    enable_auto_calibration: bool = True
    target_ai_response_time: float = 3.0


# Global settings instance
settings = Settings()
