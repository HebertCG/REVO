from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Base de datos. Sin default: si falta, el arranque falla en vez de
    # conectarse silenciosamente a una BD equivocada.
    DATABASE_URL: str

    # JWT. SIN valor por defecto a proposito: un default hardcodeado aqui
    # permite firmar tokens de admin a cualquiera que lea el repositorio.
    # Debe venir de la variable de entorno JWT_SECRET (ver .env.example).
    JWT_SECRET: str
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
