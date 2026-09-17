from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

# Load .env from backend/ dir AND repo root (D:\ProjectOne\.env)
ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
LOCAL_ENV = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "Smart Expense & Spending Analyzer"
    DEBUG: bool = True

    # --- Database ---
    # Default: SQLite for zero-setup local run.
    # For PostgreSQL (per PRD): postgresql+psycopg://user:password@localhost:5432/expenses
    DATABASE_URL: str = "sqlite:///./expenses.db"

    # --- LLM / Groq ---
    # Get a key from https://console.groq.com/keys (starts with "gsk_...")
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TIMEOUT: int = 30
    # If True, use rule-based parser when no API key is set (lets the app run offline).
    LLM_FALLBACK_TO_RULES: bool = True

    # --- CORS (comma-separated frontend origins) ---
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = {
        "env_file": (str(LOCAL_ENV), str(ROOT_ENV)),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
