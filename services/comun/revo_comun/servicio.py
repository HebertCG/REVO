"""
servicio.py — Ensambla un microservicio de REVO con todo lo transversal ya puesto.

Sin esto, cada servicio repite el mismo cableado de middlewares, motor de base
de datos, verificacion de token y rate limit. Tres copias del cableado son
tres sitios donde olvidarse de una capa.

Uso en cada servicio:

    servicio = ServicioREVO(ajustes)
    app = servicio.crear_app(titulo="REVO - Auth Service")
    app.include_router(mi_router)

Y en los endpoints:

    @router.get("/mio")
    def mio(
        alumno: Principal = Depends(servicio.alumno),
        db: Session = Depends(servicio.sesion),
        _: None = Depends(servicio.limitar("read")),
    ):
        ...
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from revo_comun.ajustes import AjustesBase
from revo_comun.basedatos.contexto import ContextoSeguridad
from revo_comun.basedatos.motor import crear_fabrica_sesiones, crear_motor, fijar_contexto
from revo_comun.errores import registrar_manejadores
from revo_comun.limites.contador import RateLimiter
from revo_comun.limites.politicas import POLICIES, RequestContext
from revo_comun.registro import configurar_registro
from revo_comun.seguridad.cabeceras import CabecerasSeguridadMiddleware, LimiteTamanoMiddleware
from revo_comun.seguridad.ip_cliente import extract_client_ip
from revo_comun.seguridad.pasarela import PasarelaMiddleware
from revo_comun.seguridad.tokens import Principal, TokenError, TokenIssuer

logger = logging.getLogger("revo.servicio")

#: Metodos que realmente usa el frontend. "*" incluye TRACE y verbos que no
#: hacen falta y solo amplian la superficie.
METODOS_CORS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

#: Cabeceras que el frontend necesita mandar. "*" tampoco hace falta aqui.
CABECERAS_CORS = ["Authorization", "Content-Type"]

#: Cabeceras del rate limit que el frontend puede leer para avisar al alumno
#: antes de que le rechacen la peticion.
CABECERAS_EXPUESTAS = ["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After", "X-Error-Id"]

#: Conexiones que se dejan libres para el superusuario y el mantenimiento.
#: Sin reserva, un pico de trafico deja al administrador sin poder entrar
#: a la base de datos justo cuando hace falta.
RESERVA_CONEXIONES_MANTENIMIENTO = 15

#: Valor por defecto de max_connections en PostgreSQL. Se usa como
#: referencia conservadora cuando no se puede consultar el real.
MAX_CONNECTIONS_POR_DEFECTO = 100


class ServicioREVO:
    """Contenedor de las piezas transversales de un microservicio."""

    def __init__(self, ajustes: AjustesBase, cliente_redis=None):
        """
        Args:
            ajustes: configuracion del servicio.
            cliente_redis: cliente ya construido. Se inyecta en las pruebas
                para no depender de un Redis real; en produccion se deja en
                None y se conecta desde REDIS_URL.
        """
        self.ajustes = ajustes

        self.tokens = TokenIssuer(
            secret=ajustes.JWT_SECRET,
            issuer=ajustes.JWT_ISSUER,
            audience=ajustes.JWT_AUDIENCE,
            expire_hours=ajustes.JWT_EXPIRE_HOURS,
        )

        self.motor = crear_motor(
            ajustes.DATABASE_URL,
            application_name=ajustes.SERVICE_NAME,
            pool_size=ajustes.DB_POOL_SIZE,
            max_overflow=ajustes.DB_MAX_OVERFLOW,
            require_ssl=ajustes.DB_REQUIRE_SSL,
        )
        self.fabrica_sesiones = crear_fabrica_sesiones(self.motor)

        self.limitador = RateLimiter(
            redis_client=cliente_redis if cliente_redis is not None else self._conectar_redis()
        )

    # ── Infraestructura ──────────────────────────────────────
    def _conectar_redis(self):
        if not self.ajustes.REDIS_URL:
            logger.warning(
                "REDIS_URL vacia: el rate limit usara el respaldo en memoria. "
                "Cada worker contara por su cuenta y el limite real sera el "
                "configurado multiplicado por el numero de workers."
            )
            return None

        try:
            import redis

            cliente = redis.Redis.from_url(
                self.ajustes.REDIS_URL,
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=2,
                health_check_interval=30,
            )
            cliente.ping()
            logger.info("Rate limit conectado a Redis")
            return cliente
        except Exception as exc:  # noqa: BLE001
            # Que Redis no este no debe impedir arrancar: el limitador degrada
            # solo al respaldo local y lo deja registrado.
            logger.error("No se pudo conectar a Redis (%s). Rate limit degradado.", exc)
            return None

    def crear_app(
        self,
        titulo: str,
        descripcion: str = "",
        version: str = "1.0.0",
        al_arrancar: Callable[[], None] | None = None,
    ) -> FastAPI:
        """
        Args:
            al_arrancar: tarea que se ejecuta una vez al levantar el servicio
                (por ejemplo, entrenar el modelo si no hay ninguno). Se pasa
                aqui en vez de con @app.on_event("startup"), que esta
                obsoleto y no garantiza el orden respecto al lifespan.
        """
        ajustes = self.ajustes

        # Lo primero: sin esto, los avisos de abajo no llegan a ninguna parte.
        configurar_registro(nivel=ajustes.LOG_LEVEL, ruidoso=ajustes.LOG_RUIDOSO)

        problemas = ajustes.validar_para_produccion()
        if problemas:
            for problema in problemas:
                logger.error("Configuracion insegura para produccion: %s", problema)
            raise RuntimeError(
                "El servicio no puede arrancar en produccion con esta configuracion:\n  - "
                + "\n  - ".join(problemas)
            )

        @asynccontextmanager
        async def ciclo_vida(app: FastAPI):
            self._comprobar_presupuesto_de_conexiones()
            logger.info(
                "%s arrancando en modo %s (docs %s)",
                ajustes.SERVICE_NAME,
                ajustes.ENVIRONMENT,
                "publicos" if ajustes.publicar_documentacion else "cerrados",
            )
            if al_arrancar is not None:
                try:
                    al_arrancar()
                except Exception as exc:  # noqa: BLE001
                    # Una tarea de arranque que falla no debe dejar el
                    # servicio sin levantar: es preferible responder 503 en
                    # la ruta afectada que caerse entero y reiniciar en bucle.
                    logger.error("La tarea de arranque fallo: %s", exc, exc_info=True)
            yield
            self.motor.dispose()

        app = FastAPI(
            title=titulo,
            description=descripcion,
            version=version,
            # En produccion no se publica el mapa de la API.
            docs_url="/docs" if ajustes.publicar_documentacion else None,
            redoc_url="/redoc" if ajustes.publicar_documentacion else None,
            openapi_url="/openapi.json" if ajustes.publicar_documentacion else None,
            lifespan=ciclo_vida,
        )

        # El orden importa: en Starlette el ultimo anadido es el mas externo.
        # Se quiere que la pasarela filtre ANTES de gastar trabajo en el resto.
        app.add_middleware(CabecerasSeguridadMiddleware, hsts=ajustes.es_produccion)
        app.add_middleware(LimiteTamanoMiddleware)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=ajustes.origenes_cors,
            allow_credentials=False,  # el token va en la cabecera, no en cookie
            allow_methods=METODOS_CORS,
            allow_headers=CABECERAS_CORS,
            expose_headers=CABECERAS_EXPUESTAS,
            max_age=600,
        )
        app.add_middleware(
            PasarelaMiddleware,
            secret=ajustes.GATEWAY_SECRET,
            enabled=ajustes.REQUIRE_GATEWAY,
        )

        registrar_manejadores(app, debug=ajustes.debug)

        @app.get("/health", tags=["Salud"])
        def salud():
            # Deliberadamente escueto: la version y el nombre del servicio son
            # informacion de reconocimiento gratuita para un atacante.
            return {"status": "ok"}

        return app

    def _comprobar_presupuesto_de_conexiones(self) -> None:
        """
        Contrasta el pool configurado con el max_connections real del servidor.

        Sin esto, el error aparece bajo carga y en forma de
        "FATAL: sorry, too many clients already", que no dice nada sobre la
        causa. Aqui se detecta al arrancar, con la cuenta hecha.
        """
        estimadas = self.ajustes.conexiones_maximas_estimadas
        try:
            with self.motor.connect() as conexion:
                maximas = int(conexion.execute(text("SHOW max_connections")).scalar())
        except Exception as exc:  # noqa: BLE001
            # No poder preguntar no es motivo para dar el visto bueno: se
            # asume el valor por defecto de PostgreSQL y se aplica la misma
            # regla. Antes esto devolvia sin mas, asi que una base de datos
            # inalcanzable al arrancar dejaba pasar cualquier pool.
            maximas = MAX_CONNECTIONS_POR_DEFECTO
            logger.warning(
                "No se pudo consultar max_connections (%s). Se asume el valor "
                "por defecto de PostgreSQL (%d) para comprobar el presupuesto.",
                type(exc).__name__, maximas,
            )

        # Se reservan unas cuantas para superusuario y mantenimiento; si no,
        # un pico deja fuera al propio administrador.
        disponibles = maximas - RESERVA_CONEXIONES_MANTENIMIENTO

        mensaje = (
            f"Presupuesto de conexiones: {self.ajustes.DB_SERVICIOS_COMPARTIDOS} servicios "
            f"x {max(1, self.ajustes.WORKERS)} workers x "
            f"({self.ajustes.DB_POOL_SIZE}+{self.ajustes.DB_MAX_OVERFLOW}) = {estimadas}; "
            f"el servidor admite {maximas}"
        )

        if estimadas > disponibles:
            aviso = (
                f"{mensaje}. Bajo carga daria 'too many clients already'. "
                f"Reduce DB_POOL_SIZE/DB_MAX_OVERFLOW o WORKERS, o sube "
                f"max_connections en PostgreSQL."
            )
            if self.ajustes.es_produccion:
                raise RuntimeError(aviso)
            logger.warning(aviso)
        else:
            logger.info(mensaje)

    # ── Dependencias ─────────────────────────────────────────
    def principal_opcional(self, request: Request) -> Principal | None:
        """Identidad si el token es valido; None si no hay token o no sirve."""
        try:
            return self.tokens.verify_header(request.headers.get("authorization"))
        except TokenError:
            return None

    def principal(self, request: Request) -> Principal:
        """Identidad obligatoria. 401 si no hay token valido."""
        try:
            return self.tokens.verify_header(request.headers.get("authorization"))
        except TokenError:
            raise HTTPException(
                status_code=401,
                detail="Token invalido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

    def admin(self, request: Request) -> Principal:
        """Identidad de administrador. 403 si es un alumno."""
        quien = self.principal(request)
        if not quien.is_admin:
            raise HTTPException(status_code=403, detail="Acceso restringido a administradores")
        return quien

    def sesion(self, request: Request):
        """
        Sesion de base de datos con el contexto RLS del solicitante.

        Si no hay token, la sesion queda SIN identidad y las politicas RLS no
        devuelven ninguna fila de alumno. Es el comportamiento deseado: una
        ruta que se olvide de pedir autenticacion no filtra datos, se queda
        sin resultados.
        """
        quien = self.principal_opcional(request)
        sesion = self.fabrica_sesiones()
        try:
            if quien is not None:
                fijar_contexto(sesion, ContextoSeguridad(user_id=quien.user_id, role=quien.role))
            yield sesion
        finally:
            sesion.close()

    def sesion_de_servicio(self):
        """
        Sesion para tareas de fondo (reentrenamiento), sin alumno detras.

        No es un contextmanager de FastAPI: se usa con `with` en el codigo de
        la tarea.
        """
        sesion = self.fabrica_sesiones()
        fijar_contexto(sesion, ContextoSeguridad.de_servicio())
        return sesion

    def limitar(self, nombre_politica: str, por_credencial: bool = False):
        """
        Crea la dependencia de rate limit para una politica del catalogo.

        Args:
            nombre_politica: clave de revo_comun.limites.politicas.POLICIES.
            por_credencial: si es True, lee el email del cuerpo para contar
                por cuenta objetivo en vez de por IP. Solo para /login.
        """
        if nombre_politica not in POLICIES:
            raise KeyError(f"Politica de rate limit desconocida: {nombre_politica!r}")

        politica = POLICIES[nombre_politica]

        async def dependencia(request: Request):
            quien = self.principal_opcional(request)
            credencial = await self._leer_credencial(request) if por_credencial else None

            contexto = RequestContext(
                client_ip=extract_client_ip(request, self.ajustes.TRUSTED_PROXY_COUNT),
                user_id=quien.user_id if quien else None,
                credential=credencial,
            )
            resultado = self.limitador.check(politica, contexto)

            if not resultado.allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Demasiadas peticiones. Espera un momento e intentalo de nuevo.",
                    headers={
                        "Retry-After": str(resultado.retry_after),
                        "X-RateLimit-Limit": str(resultado.limit),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            # Se guarda para que el endpoint pueda devolver las cabeceras.
            request.state.rate_limit = resultado

        return dependencia

    @staticmethod
    async def _leer_credencial(request: Request) -> str | None:
        """
        Extrae el email del cuerpo para el cupo de login, sin romper nada si
        el cuerpo no es JSON o viene mal formado.
        """
        try:
            cuerpo = await request.json()
        except Exception:  # noqa: BLE001
            return None

        if not isinstance(cuerpo, dict):
            return None

        email = cuerpo.get("email") or cuerpo.get("username")
        return email if isinstance(email, str) else None
