"""
cabeceras.py — Cabeceras de seguridad y techo de tamano de peticion.

Son dos middlewares pequenos y sin estado. Cierran ataques que no dependen
de ningun fallo del codigo de negocio:

  - Clickjacking: alguien mete la API o el panel en un iframe.
  - Sniffing MIME: el navegador decide ejecutar como script una respuesta JSON.
  - Fuga por Referer: la URL con identificadores viaja a un tercero.
  - Cache compartida: un proxy del aula guarda la respuesta de un alumno.
  - Agotamiento de memoria: un cuerpo de 500 MB tumba el worker.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

#: Un ano. Solo se manda sobre HTTPS real; en localhost dejaria el navegador
#: del desarrollador forzando https contra un servidor que habla http.
HSTS_MAX_AGE = 31_536_000

#: La API solo devuelve JSON: no carga scripts, ni imagenes, ni fuentes.
#: 'none' por defecto es la politica mas restrictiva posible y no rompe nada.
CSP_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"

#: 256 KB. El cuerpo mas grande que manda el frontend es el guardado masivo
#: de 25 respuestas, que no llega a 2 KB. El margen es enorme a proposito.
DEFAULT_MAX_BODY_BYTES = 256 * 1024


class CabecerasSeguridadMiddleware(BaseHTTPMiddleware):
    """Anade las cabeceras de seguridad a toda respuesta y borra las que sobran."""

    def __init__(self, app, hsts: bool = False, csp: str = CSP_API):
        super().__init__(app)
        self._hsts = hsts
        self._csp = csp

    async def dispatch(self, request, call_next):
        respuesta = await call_next(request)

        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        respuesta.headers["Content-Security-Policy"] = self._csp
        respuesta.headers["Permissions-Policy"] = PERMISSIONS_POLICY
        respuesta.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        respuesta.headers["Pragma"] = "no-cache"

        if self._hsts:
            respuesta.headers["Strict-Transport-Security"] = (
                f"max-age={HSTS_MAX_AGE}; includeSubDomains"
            )

        # La version del servidor le ahorra trabajo de reconocimiento a un
        # atacante: le dice exactamente que CVEs probar.
        #
        # Ojo: uvicorn escribe su propia cabecera Server por debajo de los
        # middlewares, asi que esto solo limpia la que ponga la aplicacion.
        # Para quitar la de uvicorn hay que arrancarlo con --no-server-header
        # (ya configurado en los Dockerfile y en el compose).
        if "server" in respuesta.headers:
            del respuesta.headers["server"]

        return respuesta


class LimiteTamanoMiddleware(BaseHTTPMiddleware):
    """
    Rechaza cuerpos desmesurados por Content-Length, antes de leerlos.

    Sin esto, una sola peticion con un cuerpo de cientos de megas obliga al
    worker a reservar esa memoria: un ataque de denegacion de servicio que
    no necesita volumen, solo una peticion bien elegida.
    """

    def __init__(self, app, max_bytes: int = DEFAULT_MAX_BODY_BYTES):
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request, call_next):
        declarado = request.headers.get("content-length")
        if declarado is not None:
            try:
                if int(declarado) > self._max_bytes:
                    return self._demasiado_grande()
            except ValueError:
                return self._demasiado_grande()

        return await call_next(request)

    @staticmethod
    def _demasiado_grande() -> JSONResponse:
        # El mensaje no menciona el limite exacto: no hace falta darle al
        # atacante el numero con el que calibrar.
        return JSONResponse(
            status_code=413,
            content={"detail": "El contenido enviado es demasiado grande."},
        )
