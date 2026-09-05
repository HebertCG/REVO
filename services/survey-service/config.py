"""Configuracion del survey-service."""
from functools import lru_cache

from revo_comun.ajustes import AjustesBase


class Ajustes(AjustesBase):
    SERVICE_NAME: str = "revo-survey"
    SERVICE_PORT: int = 8002

    #: URL interna del ml-service. En produccion apunta a la red privada del
    #: compose, nunca a una URL publica.
    ML_SERVICE_URL: str = "http://ml-service:8003"

    #: Timeout de la llamada al ml-service.
    #:
    #: Tiene que cubrir el arranque en frio del ml-service. Con 30 s y un
    #: servicio dormido, la llamada expiraba antes de que despertase y el
    #: alumno terminaba el cuestionario sin prediccion: el error se convierte
    #: en "ml_no_disponible", que no distingue "estaba arrancando" de "esta
    #: roto". El coste de subirlo es un worker retenido mas tiempo cuando el
    #: ml-service si esta caido de verdad.
    ML_TIMEOUT_SECONDS: float = 90.0


@lru_cache
def obtener_ajustes() -> Ajustes:
    return Ajustes()


settings = obtener_ajustes()
