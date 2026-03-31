from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Base de datos
    DATABASE_URL: str = "postgresql://revo_user:revo_pass_2025@localhost:5432/revo_db"

    # JWT
    JWT_SECRET: str = "revo_super_secret_jwt_key_2025"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # Servicio
    SERVICE_PORT: int = 8001
    SERVICE_NAME: str = "auth-service"
    DEBUG: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
