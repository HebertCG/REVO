from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://revo_user:revo_pass_2025@localhost:5432/revo_db"
    JWT_SECRET: str = "revo_super_secret_jwt_key_2025"
    JWT_ALGORITHM: str = "HS256"
    SERVICE_PORT: int = 8003
    MODEL_PATH: str = "model/saved/decision_tree.pkl"
    MODEL_VERSION: str = "v1.0"
    model_config = {"env_file": ".env", "extra": "ignore"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
