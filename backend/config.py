from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    SECRET_KEY: str = Field(default="", description="HS256 signing key (required)")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MIN: int = 60
    DATABASE_URL: str = "sqlite:///./consorcio.db"
    SEED_ENABLED: bool = True
    SEED_DEFAULT_PASSWORD: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def _secret_required(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "SECRET_KEY no configurada. Definila en variables de entorno o en el archivo .env."
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
