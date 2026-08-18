from functools import lru_cache

from pydantic import Field, field_validator, model_validator
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
    DEMO_MODE: bool = False
    UPLOAD_DIR: str = "backend/uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024
    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    URL_FIRMADA_SEGUNDOS: int = 300
    S3_ENDPOINT_URL: str = ""
    S3_REGION: str = "auto"
    S3_BUCKET: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "consorcio@local"
    SMTP_FROM_NAME: str = "Consorcio"
    SUPER_ADMIN_EMAIL: str = ""
    SUPER_ADMIN_PASSWORD: str = ""
    # Base del link que se manda por email al recuperar la contraseña. En
    # producción, el dominio real del frontend: si apunta a localhost, el link
    # que recibe el vecino no le sirve.
    FRONTEND_URL: str = "http://localhost:5173"
    RECUPERACION_TOKEN_MINUTOS: int = 60
    RECUPERACION_MAX_POR_HORA: int = 3
    # Días que se conserva un error registrado antes de borrarse solo.
    ERRORES_RETENCION_DIAS: int = 90
    # Opcional. Con esto cargado, los errores además se mandan a Sentry, que es
    # lo que avisa. Va por variable de entorno y no por la interfaz: tiene que
    # arrancar antes de que algo pueda fallar, y una config guardada en la base
    # no está disponible si el problema es justamente la base.
    SENTRY_DSN: str = ""
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:5175,http://127.0.0.1:5175"
    )
    CORS_ORIGIN_REGEX: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @field_validator("SECRET_KEY")
    @classmethod
    def _secret_required(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "SECRET_KEY no configurada. Definila en variables de entorno o en el archivo .env."
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def _fix_postgres_prefix(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    @model_validator(mode="after")
    def _s3_exige_credenciales(self) -> "Settings":
        """Con STORAGE_BACKEND=s3 faltando credenciales, cada subida fallaría
        recién en tiempo de request y con un error de boto3 incomprensible.
        Mejor no arrancar."""
        if self.STORAGE_BACKEND == "s3":
            faltan = [
                nombre
                for nombre in ("S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")
                if not getattr(self, nombre)
            ]
            if faltan:
                raise ValueError(f"STORAGE_BACKEND=s3 exige {', '.join(faltan)}.")
        elif self.STORAGE_BACKEND != "local":
            raise ValueError(
                f"STORAGE_BACKEND invalido: {self.STORAGE_BACKEND!r}. "
                "Valores validos: 'local', 's3'."
            )
        return self

    @model_validator(mode="after")
    def _demo_mode_requiere_db_demo(self) -> "Settings":
        """Candado anti-producción.

        Con DEMO_MODE=true se registra POST /auth/demo-login, que emite tokens
        sin pedir credenciales. Si ese flag se activara por error contra la base
        de producción sería un bypass total de autenticación, así que exigimos
        que la DATABASE_URL sea explícitamente una base demo y, si no, no
        arrancamos.
        """
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                "sqlite:///./demo.db" if self.DEMO_MODE else "sqlite:///./consorcio.db"
            )
        elif self.DEMO_MODE and "demo" not in self.DATABASE_URL.lower():
            raise ValueError(
                "DEMO_MODE=true exige una DATABASE_URL que contenga 'demo' "
                f"(recibida: {self.DATABASE_URL!r}). Es un candado "
                "anti-producción: el modo demo emite tokens sin credenciales."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
