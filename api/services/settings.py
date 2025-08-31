from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore", 
        env_file=Path(__file__).parent.parent.parent / ".env"  # Points to InvisiScan/.env
    )
    GEMINI_API_KEY: str