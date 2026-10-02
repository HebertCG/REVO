"""
catalogo.py — Nombres, iconos y colores de las especializaciones.

PROBLEMA QUE RESUELVE

Esta informacion vivia duplicada en CUATRO sitios:

    1. La tabla `specializations`            -> color #3B82F6
    2. SPECIALIZATION_MAP en predictor.py    -> color #3B82F6
    3. frontend/src/pages/Results.jsx        -> color #E10600
    4. frontend/src/pages/Admin.jsx          -> color #3B82F6

Y ya divergieron: Results.jsx usa el rojo de la identidad de la marca y los
otros tres siguen en el azul original. O sea que el alumno ve un color en la
pantalla de resultado y otro en el panel, para la misma rama.

Cuatro copias no son un problema de estilo: son cuatro sitios que hay que
acordarse de tocar, y ya se demostro que nadie se acuerda.

Este modulo hace que el servicio lea de la tabla, que es la unica de las
cuatro copias que es realmente la fuente. El mapa de predictor.py queda como
respaldo para cuando no hay base de datos (pruebas unitarias) o la consulta
falla.

POR QUE SE CACHEA

El catalogo son diez filas que cambian una vez al ano. Consultarlo en cada
prediccion es un viaje a PostgreSQL por peticion para leer algo inmutable.
La cache tiene caducidad en vez de ser eterna para que un cambio en la tabla
llegue sin reiniciar el servicio.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import Specialization

logger = logging.getLogger("revo.ml.catalogo")

#: Segundos que vive la copia en memoria. Cinco minutos: suficiente para que
#: no se note en carga y poco para que una correccion llegue sola.
VIGENCIA_SEGUNDOS = 300

_cache: dict[int, dict] | None = None
_cargado_en: float = 0.0


def obtener(db: Session) -> dict[int, dict]:
    """
    Catalogo como {id: {"name", "icon", "color"}}.

    Si la consulta falla devuelve el diccionario vacio y deja que quien llama
    caiga al respaldo. No propaga la excepcion a proposito: quedarse sin
    nombre de rama degrada el resultado, pero no poder dar resultado ninguno
    por un fallo al leer diez filas de adorno seria peor.
    """
    global _cache, _cargado_en

    if _cache is not None and (time.monotonic() - _cargado_en) < VIGENCIA_SEGUNDOS:
        return _cache

    try:
        filas = db.scalars(select(Specialization)).all()
    except Exception as exc:  # noqa: BLE001
        logger.error("No se pudo leer el catalogo de especializaciones: %s", exc)
        return _cache or {}

    _cache = {
        fila.id: {
            "name": fila.name,
            "icon": fila.icon or "",
            "color": fila.color_hex or "",
        }
        for fila in filas
    }
    _cargado_en = time.monotonic()
    return _cache


def invalidar() -> None:
    """Fuerza la relectura. La usan las pruebas y el panel de administracion."""
    global _cache, _cargado_en
    _cache = None
    _cargado_en = 0.0
