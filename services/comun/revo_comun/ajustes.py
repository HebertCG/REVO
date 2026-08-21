"""
ajustes.py — Configuracion base que comparten los tres microservicios.

Regla de esta configuracion: **lo que compromete la seguridad no tiene valor
por defecto**. Si falta JWT_SECRET o DATABASE_URL, el servicio no arranca. Un
default comodo aqui es un agujero en produccion que nadie nota hasta que es
tarde, porque todo "funciona".

Cada servicio hereda de AjustesBase y anade lo suyo.
"""
from __future__ import annotations

from functools import cached_property

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class AjustesBase(BaseSettings):
    # ── Identidad del servicio ───────────────────────────────
    SERVICE_NAME: str = "revo"
    SERVICE_PORT: int = 8000

    #: "development" o "production". Controla si se publican los docs, si se
    #: manda HSTS y si los errores devuelven detalle.
    ENVIRONMENT: str = "development"

    # ── Base de datos ────────────────────────────────────────
    #: Sin default: si falta, el arranque falla en vez de conectarse en
    #: silencio a una base de datos equivocada.
    DATABASE_URL: str

    # El pool es POR PROCESO. El total contra Postgres es
    #     servicios x workers x (pool + overflow)
    # y si esa cuenta pasa de max_connections, el sintoma en produccion es
    # "FATAL: sorry, too many clients already" bajo carga, justo cuando peor
    # viene. Con los valores de aqui: 3 x 2 x 10 = 60, dentro de los 100 por
    # defecto de PostgreSQL y con margen para mantenimiento.
    #
    # Estas consultas duran milisegundos, asi que un pool pequeno basta: a
    # 30 peticiones por segundo con 5 ms de consulta hacen falta 0,15
    # conexiones simultaneas. El pool grande no da velocidad, solo agota
    # antes el limite del servidor.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_REQUIRE_SSL: bool = False

    #: Procesos uvicorn de ESTE servicio. Solo se usa para calcular el
    #: presupuesto de conexiones; quien los arranca es el comando del compose.
    WORKERS: int = 1

    #: Cuantos servicios comparten esta base de datos. Entra en la cuenta del
    #: presupuesto de conexiones.
    DB_SERVICIOS_COMPARTIDOS: int = 3

    # ── Tokens ───────────────────────────────────────────────
    #: Sin default a proposito: un secreto publicado en el repositorio deja
    #: firmar tokens de administrador a cualquiera que lo lea.
    JWT_SECRET: str
    JWT_ISSUER: str = "revo-auth"
    JWT_AUDIENCE: str = "revo-api"
    JWT_EXPIRE_HOURS: int = 24

    # ── Rate limit ───────────────────────────────────────────
    #: Vacio = sin Redis. El servicio arranca igual y usa el respaldo local,
    #: pero deja un aviso en el log: es una degradacion, no un modo normal.
    REDIS_URL: str = ""

    # ── Pasarela ─────────────────────────────────────────────
    #: Cuando esta activo, el servicio solo atiende peticiones que traigan el
    #: secreto de la pasarela. Es la segunda capa detras del aislamiento de red.
    REQUIRE_GATEWAY: bool = False
    GATEWAY_SECRET: str = ""

    #: Cuantos proxies propios hay delante. 0 = trafico directo (se ignora
    #: X-Forwarded-For). 1 = Nginx. 2 = Cloudflare y Nginx.
    TRUSTED_PROXY_COUNT: int = 0

    # ── Registro ─────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    #: Deja pasar el detalle de SQLAlchemy y terceros. Solo para depurar: en
    #: DEBUG, SQLAlchemy registra cada sentencia con sus parametros, y ahi van
    #: correos y respuestas de alumnos.
    LOG_RUIDOSO: bool = False

    # ── CORS ─────────────────────────────────────────────────
    #: Lista separada por comas. Sin comodines y sin expresiones regulares:
    #: un patron como "https://.*\\.vercel\\.app" convierte en origen valido
    #: cualquier despliegue que un tercero suba a Vercel.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = {"env_file": ".env", "extra": "ignore"}

    # ── Validaciones ─────────────────────────────────────────
    @field_validator("ENVIRONMENT")
    @classmethod
    def entorno_conocido(cls, valor: str) -> str:
        normalizado = valor.strip().lower()
        if normalizado not in {"development", "production", "test"}:
            raise ValueError(
                f"ENVIRONMENT debe ser development, production o test; llego {valor!r}"
            )
        return normalizado

    # ── Derivados ────────────────────────────────────────────
    @property
    def conexiones_maximas_estimadas(self) -> int:
        """Conexiones que puede llegar a abrir el conjunto de servicios."""
        return (
            self.DB_SERVICIOS_COMPARTIDOS
            * max(1, self.WORKERS)
            * (self.DB_POOL_SIZE + self.DB_MAX_OVERFLOW)
        )

    @property
    def es_produccion(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def debug(self) -> bool:
        """En produccion nunca: el detalle del error se queda en el log."""
        return not self.es_produccion

    @property
    def publicar_documentacion(self) -> bool:
        """
        /docs y /redoc describen cada endpoint, cada parametro y cada esquema.
        En produccion es un mapa del sistema servido al atacante.
        """
        return not self.es_produccion

    @cached_property
    def origenes_cors(self) -> list[str]:
        return [origen.strip() for origen in self.CORS_ORIGINS.split(",") if origen.strip()]

    def validar_para_produccion(self) -> list[str]:
        """
        Devuelve los problemas que impiden salir a produccion.

        Se llama en el arranque. Es preferible no arrancar a arrancar con una
        configuracion que parece correcta y no lo es.
        """
        problemas: list[str] = []

        if not self.es_produccion:
            return problemas

        if not self.REDIS_URL:
            problemas.append(
                "REDIS_URL vacia: el rate limit quedaria solo en memoria y "
                "cada worker contaria por su cuenta"
            )

        if self.REQUIRE_GATEWAY and not self.GATEWAY_SECRET:
            problemas.append("REQUIRE_GATEWAY activo pero GATEWAY_SECRET vacio")

        if not self.REQUIRE_GATEWAY:
            problemas.append(
                "REQUIRE_GATEWAY desactivado: el servicio atenderia peticiones "
                "que no vengan de la pasarela"
            )

        if self.TRUSTED_PROXY_COUNT == 0:
            problemas.append(
                "TRUSTED_PROXY_COUNT en 0 detras de una pasarela: todas las "
                "peticiones se contarian contra la IP del proxy"
            )

        if not self.DB_REQUIRE_SSL:
            problemas.append("DB_REQUIRE_SSL desactivado: la conexion a la base de datos iria en claro")

        for origen in self.origenes_cors:
            if not origen.startswith("https://"):
                problemas.append(f"Origen CORS sin https: {origen}")
            if "*" in origen:
                problemas.append(f"Origen CORS con comodin: {origen}")

        return problemas
