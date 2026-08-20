"""Configuracion del auth-service."""
from functools import lru_cache

from revo_comun.ajustes import AjustesBase


class Ajustes(AjustesBase):
    SERVICE_NAME: str = "revo-auth"
    SERVICE_PORT: int = 8001

    #: Longitud minima de contrasena. 6 caracteres (el valor anterior) se
    #: rompen en segundos con un diccionario; 10 con las comprobaciones de
    #: schemas.py deja fuera lo mas evidente sin volverse hostil para un
    #: estudiante que se registra desde el movil.
    PASSWORD_MIN_LENGTH: int = 10


@lru_cache
def obtener_ajustes() -> Ajustes:
    return Ajustes()


settings = obtener_ajustes()
