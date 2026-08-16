from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Sin defaults: ver services/auth-service/config.py. Un JWT_SECRET
    # hardcodeado permite falsificar tokens de admin.
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    SERVICE_PORT: int = 8003
    MODEL_PATH: str = "model/saved/decision_tree.pkl"
    MODEL_VERSION: str = "v1.0"
    model_config = {"env_file": ".env", "extra": "ignore"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
