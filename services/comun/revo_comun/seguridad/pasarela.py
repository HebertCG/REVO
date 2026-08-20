"""
pasarela.py — Solo la pasarela puede hablar con los microservicios.

La defensa de verdad es de red: en el compose los servicios no publican
puertos y solo Nginx queda expuesto. Pero una regla de firewall mal puesta,
un `ports:` que alguien reanade para depurar o un despliegue en Render donde
cada servicio es una URL publica dejan el microservicio al aire.

Este middleware es la segunda capa: el servicio exige una cabecera con un
secreto compartido que solo conoce la pasarela. Es barato, no depende de la
red y convierte un error de infraestructura en un 403 en vez de en una fuga.
"""
from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

GATEWAY_HEADER = "x-revo-gateway"

#: Rutas que el orquestador consulta sin pasar por Nginx. Si se bloquean,
#: Docker marca el contenedor como enfermo y lo reinicia en bucle.
RUTAS_LIBRES = frozenset({"/health", "/healthz", "/ready"})

MIN_SECRET_LENGTH = 32


class PasarelaMiddleware(BaseHTTPMiddleware):
    """Rechaza cualquier peticion que no traiga el secreto de la pasarela."""

    def __init__(self, app, secret: str, enabled: bool = False, rutas_libres=RUTAS_LIBRES):
        super().__init__(app)

        if enabled and (not secret or len(secret) < MIN_SECRET_LENGTH):
            raise ValueError(
                "GATEWAY_SECRET debe tener al menos "
                f"{MIN_SECRET_LENGTH} caracteres cuando se exige pasarela. "
                "Genera uno con: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )

        self._secret = secret
        self._enabled = enabled
        self._rutas_libres = frozenset(rutas_libres)

    async def dispatch(self, request, call_next):
        if not self._enabled or request.url.path in self._rutas_libres:
            return await call_next(request)

        recibido = request.headers.get(GATEWAY_HEADER, "")

        # compare_digest en vez de == para no filtrar el secreto por el
        # tiempo que tarda la comparacion en fallar.
        if not hmac.compare_digest(recibido, self._secret):
            # El mensaje es deliberadamente mudo: no confirma si la ruta
            # existe ni menciona que falta una cabecera concreta.
            return JSONResponse(status_code=403, content={"detail": "Acceso denegado."})

        return await call_next(request)
