"""
errores.py — Convierte cualquier fallo en una respuesta que no informa al atacante.

FastAPI en modo por defecto devuelve el detalle de la excepcion. Eso incluye
rutas del servidor, nombres de tablas, restricciones de la base de datos y, en
el peor caso, credenciales que aparecian en el mensaje.

La regla aqui: al cliente le llega QUE fallo y un identificador; el POR QUE se
queda en el log del servidor, asociado a ese mismo identificador.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("revo.errores")

ERROR_HEADER = "X-Error-Id"

MENSAJE_GENERICO = "Ocurrio un error procesando la solicitud."
MENSAJE_CONFLICTO = "El recurso ya existe o entra en conflicto con otro."
MENSAJE_BASE_DATOS = "El servicio no esta disponible en este momento."


def _nuevo_id() -> str:
    return uuid.uuid4().hex[:12]


def _respuesta(status: int, detalle: str, error_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"detail": detalle, "error_id": error_id},
        headers={ERROR_HEADER: error_id},
    )


def _resumen_validacion(exc: RequestValidationError) -> list[dict]:
    """
    Devuelve que campo falla y por que, SIN devolver el valor recibido.

    Pydantic incluye el input original en el error. Reflejarlo convierte la
    respuesta de error en un espejo de la entrada del atacante.
    """
    resumen = []
    for error in exc.errors():
        ubicacion = [str(parte) for parte in error.get("loc", []) if parte != "body"]
        resumen.append(
            {
                "campo": ".".join(ubicacion) or "cuerpo",
                "problema": str(error.get("type", "invalido")),
            }
        )
    return resumen


def registrar_manejadores(app: FastAPI, debug: bool = False) -> None:
    """
    Instala los manejadores de error en la aplicacion.

    Args:
        app: la aplicacion FastAPI.
        debug: si es True devuelve el detalle real al cliente. Solo para
            desarrollo local; en produccion filtra informacion sensible.
    """

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError):
        error_id = _nuevo_id()
        logger.info("Validacion fallida [%s] en %s", error_id, request.url.path)
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Los datos enviados no son validos.",
                "errores": _resumen_validacion(exc),
                "error_id": error_id,
            },
            headers={ERROR_HEADER: error_id},
        )

    @app.exception_handler(IntegrityError)
    async def _integridad(request: Request, exc: IntegrityError):
        error_id = _nuevo_id()
        # El mensaje de Postgres nombra la restriccion y el valor duplicado.
        # Al cliente solo le llega que hubo conflicto.
        logger.warning(
            "Conflicto de integridad [%s] en %s: %s", error_id, request.url.path, exc
        )
        detalle = str(exc) if debug else MENSAJE_CONFLICTO
        return _respuesta(409, detalle, error_id)

    @app.exception_handler(SQLAlchemyError)
    async def _base_datos(request: Request, exc: SQLAlchemyError):
        error_id = _nuevo_id()
        logger.error(
            "Fallo de base de datos [%s] en %s: %s",
            error_id,
            request.url.path,
            exc,
            exc_info=True,
        )
        detalle = str(exc) if debug else MENSAJE_BASE_DATOS
        return _respuesta(503, detalle, error_id)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        # Un HTTPException lo lanza nuestro codigo a proposito: su mensaje
        # esta pensado para el usuario y se conserva tal cual.
        error_id = _nuevo_id()
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error_id": error_id},
            headers={**(exc.headers or {}), ERROR_HEADER: error_id},
        )

    @app.exception_handler(Exception)
    async def _no_controlado(request: Request, exc: Exception):
        error_id = _nuevo_id()
        logger.error(
            "Error no controlado [%s] en %s: %s",
            error_id,
            request.url.path,
            exc,
            exc_info=True,
        )
        detalle = f"{type(exc).__name__}: {exc}" if debug else MENSAJE_GENERICO
        return _respuesta(500, detalle, error_id)
