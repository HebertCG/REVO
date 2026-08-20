"""Configuracion del survey-service."""
from functools import lru_cache

from revo_comun.ajustes import AjustesBase


class Ajustes(AjustesBase):
    SERVICE_NAME: str = "revo-survey"
    SERVICE_PORT: int = 8002

    #: URL interna del ml-service. En produccion apunta a la red privada del
    #: compose, nunca a una URL publica.
    ML_SERVICE_URL: str = "http://ml-service:8003"

    #: Timeout de la llamada al ml-service. El valor anterior era 30 s, que
    #: con el plan gratuito de Render tiene sentido (el servicio duerme) pero
    #: retiene un worker del survey-service bloqueado todo ese tiempo.
    ML_TIMEOUT_SECONDS: float = 30.0


@lru_cache
def obtener_ajustes() -> Ajustes:
    return Ajustes()


settings = obtener_ajustes()
