from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Sin defaults: ver services/auth-service/config.py. Un JWT_SECRET
    # hardcodeado permite falsificar tokens de admin.
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    SERVICE_PORT: int = 8002
    ML_SERVICE_URL: str = "http://localhost:8013"
    model_config = {"env_file": ".env", "extra": "ignore"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
