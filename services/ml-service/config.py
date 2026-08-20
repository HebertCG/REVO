"""Configuracion del ml-service."""
from functools import lru_cache

from revo_comun.ajustes import AjustesBase


class Ajustes(AjustesBase):
    SERVICE_NAME: str = "revo-ml"
    SERVICE_PORT: int = 8003

    MODEL_PATH: str = "model/saved/decision_tree.pkl"
    MODEL_VERSION: str = "v1.0"

    #: Cuantas predicciones nuevas disparan un reentrenamiento automatico.
    UMBRAL_REENTRENAMIENTO: int = 50


@lru_cache
def obtener_ajustes() -> Ajustes:
    return Ajustes()


settings = obtener_ajustes()
