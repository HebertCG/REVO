"""
registro.py — Configuracion de logging de los microservicios.

Sin esto, uvicorn configura sus propios loggers y deja el logger raiz sin
manejador. El efecto practico es que **todo lo que la aplicacion registra por
debajo de WARNING desaparece**: el aviso de que Redis se cayo y el rate limit
esta degradado, el presupuesto de conexiones, el motivo de un 401. En
produccion eso significa operar a ciegas.

Formato en una sola linea y con campos fijos para que un `grep` o un
recolector de logs pueda partirlo sin adivinar.
"""
from __future__ import annotations

import logging
import sys

FORMATO = "%(asctime)s %(levelname)-7s %(name)-22s %(message)s"
FECHA = "%Y-%m-%dT%H:%M:%S"

#: Loggers de la aplicacion. Se listan para poder subirles el nivel sin
#: inundar el log con el detalle interno de librerias de terceros.
LOGGERS_REVO = (
    "revo.servicio",
    "revo.errores",
    "revo.ratelimit",
    "revo.basedatos",
)


def configurar_registro(nivel: str = "INFO", ruidoso: bool = False) -> None:
    """
    Args:
        nivel: nivel de los loggers propios (DEBUG, INFO, WARNING, ERROR).
        ruidoso: si es True, tambien deja pasar el detalle de SQLAlchemy y
            librerias de terceros. Solo para depurar: SQLAlchemy en DEBUG
            registra cada sentencia y cada parametro, incluidos datos
            personales de los alumnos.
    """
    nivel_num = getattr(logging, nivel.upper(), logging.INFO)

    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(logging.Formatter(FORMATO, datefmt=FECHA))

    raiz = logging.getLogger()
    # Se reemplazan los manejadores en vez de anadir: si esta funcion se
    # llama dos veces (por ejemplo al recargar en desarrollo), sin esto cada
    # linea saldria duplicada.
    raiz.handlers = [manejador]
    raiz.setLevel(logging.WARNING if not ruidoso else logging.DEBUG)

    for nombre in LOGGERS_REVO:
        logging.getLogger(nombre).setLevel(nivel_num)

    if not ruidoso:
        # Estas librerias registran en INFO cosas que no aportan nada en
        # operacion normal y que si pueden llevar datos sensibles.
        for nombre in ("sqlalchemy.engine", "urllib3", "asyncio", "watchfiles"):
            logging.getLogger(nombre).setLevel(logging.WARNING)
