"""
artefacto.py — Carga el modelo que el motor consume.

QUE CONTIENE EL ARTEFACTO

El tensor de log-verosimilitudes ya evaluado: para cada item, cada rama y
cada respuesta posible, la probabilidad de esa respuesta. Lo compila
database/motor_adaptativo/generar_artefacto.py.

POR QUE VIAJA EL TENSOR Y NO LOS PARAMETROS

Podrian enviarse los parametros del modelo (delta, tau, la matriz S) y
calcular aqui. No se hace: enviando el tensor YA EVALUADO, survey-service no
contiene ni una linea de modelado psicometrico. Solo busca en una tabla y
suma en log-espacio.

El modelo sigue siendo de quien lo compila; survey solo lo ejecuta. Es lo
que mantiene la cohesion del reparto entre servicios aunque el motor corra
del lado del cuestionario.

EL HASH DEL BANCO

Si alguien anade preguntas y no recompila el artefacto, el motor estaria
usando verosimilitudes de un banco que ya no existe: preguntaria por items
que no estan y no conoceria los nuevos.

Al cargar se comprueba el hash. Si no cuadra, NO se rechaza el arranque: se
avisa y se sigue. Dejar el cuestionario inoperativo porque alguien anadio un
item seria peor que servirlo con un artefacto algo desfasado, y quien tiene
que enterarse es el equipo, por el log, no el alumno.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache

logger = logging.getLogger("revo.survey.motor")

#: Copia empaquetada en el repositorio. El motor nunca se queda sin modelo
#: por un fallo de red: si no hay nada mas reciente, usa esta.
RUTA_EMPAQUETADO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "artefactos", "adapt-v0.json"
)

#: Claves que un artefacto tiene que traer. Sin esta comprobacion, un JSON
#: truncado o de otra version fallaria mucho mas tarde con un KeyError en
#: mitad de una peticion, que es el peor momento para enterarse.
CLAVES = ("version", "hash_banco", "n_ramas", "niveles", "likert", "eleccion_forzada")


class ArtefactoInvalido(ValueError):
    """El artefacto no tiene la forma que el motor espera."""


def validar(datos: dict) -> None:
    """Comprueba la estructura antes de dar el artefacto por bueno."""
    faltan = [c for c in CLAVES if c not in datos]
    if faltan:
        raise ArtefactoInvalido(f"Al artefacto le faltan claves: {faltan}")

    for nombre in ("likert", "eleccion_forzada"):
        bloque = datos[nombre]
        for sub in ("indice", "meta", "log_verosimilitud"):
            if sub not in bloque:
                raise ArtefactoInvalido(f"A {nombre} le falta '{sub}'")
        if len(bloque["meta"]) != len(bloque["log_verosimilitud"]):
            raise ArtefactoInvalido(
                f"{nombre}: {len(bloque['meta'])} metadatos frente a "
                f"{len(bloque['log_verosimilitud'])} filas de verosimilitud"
            )

    if not datos["likert"]["indice"]:
        raise ArtefactoInvalido("El artefacto no trae ningun item Likert")


def cargar(ruta: str | None = None) -> dict:
    """Lee y valida un artefacto."""
    destino = ruta or RUTA_EMPAQUETADO
    if not os.path.exists(destino):
        raise ArtefactoInvalido(
            f"No hay artefacto en {destino}. Compilalo con:\n"
            "  python database/motor_adaptativo/generar_artefacto.py"
        )

    with open(destino, encoding="utf-8") as fichero:
        datos = json.load(fichero)

    validar(datos)
    return datos


@lru_cache(maxsize=1)
def activo() -> dict:
    """
    Artefacto en uso, cacheado.

    El tensor son ~70 KB de JSON. Releerlo y parsearlo en cada pregunta de
    cada alumno seria un desperdicio, y el fichero no cambia entre
    despliegues.
    """
    datos = cargar()
    logger.info(
        "Motor adaptativo: artefacto %s (%s items Likert, %s de eleccion forzada)",
        datos["version"],
        len(datos["likert"]["meta"]),
        len(datos["eleccion_forzada"]["meta"]),
    )
    return datos


def coincide_el_banco(datos: dict, hash_actual: str) -> bool:
    """
    ¿El artefacto describe el banco que hay ahora en la base?

    Devuelve un booleano en vez de lanzar: la decision de que hacer cuando no
    coincide es de quien llama, y aqui la respuesta correcta es avisar y
    seguir, no dejar el cuestionario sin servicio.
    """
    if datos.get("hash_banco") == hash_actual:
        return True

    logger.warning(
        "El artefacto %s se compilo para el banco %s, pero el banco actual es "
        "%s. El motor sigue funcionando con verosimilitudes desfasadas: "
        "recompila con database/motor_adaptativo/generar_artefacto.py",
        datos.get("version"), datos.get("hash_banco"), hash_actual,
    )
    return False


def meta_de(datos: dict, clave: str) -> dict | None:
    """Metadatos de un item por su clave ('q:1001' o 'f:4')."""
    tipo, _, ident = clave.partition(":")
    bloque = datos["likert"] if tipo == "q" else datos["eleccion_forzada"]
    posicion = bloque["indice"].get(ident)
    return None if posicion is None else bloque["meta"][posicion]


def tabla_de(datos: dict, clave: str) -> list[list[float]] | None:
    """Tabla de log-verosimilitudes de un item por su clave."""
    tipo, _, ident = clave.partition(":")
    bloque = datos["likert"] if tipo == "q" else datos["eleccion_forzada"]
    posicion = bloque["indice"].get(ident)
    return None if posicion is None else bloque["log_verosimilitud"][posicion]
