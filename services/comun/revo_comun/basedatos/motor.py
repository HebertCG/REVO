"""
motor.py — Motor de base de datos y sesiones con contexto de seguridad.

Dos responsabilidades:

1. Crear el engine con los limites que evitan que el servicio se ahogue con
   mucha afluencia: tamano de pool, reciclado de conexiones, timeout de
   sentencia y timeout de transaccion ociosa.

2. Garantizar que el contexto RLS se aplica en CADA transaccion. Esto ultimo
   no es un detalle: un `commit()` a mitad de peticion cierra la transaccion
   y abre otra. Si el contexto no se reaplica, las consultas que vienen
   despues corren sin identidad y RLS las deja sin filas.
"""
from __future__ import annotations

import logging

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from revo_comun.basedatos.contexto import (
    ContextoSeguridad,
    SENTENCIA_CONTEXTO,
    parametros_contexto,
)

logger = logging.getLogger("revo.basedatos")

#: Clave bajo la que se guarda el contexto en `session.info`.
CLAVE_CONTEXTO = "revo_contexto"

#: Una consulta de este sistema no deberia pasar de unos pocos cientos de ms.
#: 10 s es un techo generoso que solo alcanza una consulta patologica.
STATEMENT_TIMEOUT_MS = 10_000

#: Una transaccion abierta y olvidada retiene cerrojos y bloquea el VACUUM.
IDLE_TIMEOUT_MS = 30_000

#: Render y varios proxies cortan conexiones ociosas a los 5 minutos. Al
#: reciclar antes se evita entregar una conexion ya muerta a una peticion.
POOL_RECYCLE_SECONDS = 240

PREFIJOS_VALIDOS = ("postgresql://", "postgresql+psycopg2://", "postgresql+psycopg://")


def opciones_de_conexion(
    application_name: str = "revo",
    statement_timeout_ms: int = STATEMENT_TIMEOUT_MS,
    idle_timeout_ms: int = IDLE_TIMEOUT_MS,
    require_ssl: bool = False,
) -> dict:
    """
    Parametros que se le pasan al driver en cada conexion.

    Los dos timeouts son limites del SERVIDOR, no del cliente: Postgres corta
    la consulta y libera la conexion aunque el proceso de Python se quede
    esperando. Es la diferencia entre una consulta lenta y un pool agotado.
    """
    opciones = {
        "application_name": application_name,
        "options": (
            f"-c statement_timeout={statement_timeout_ms} "
            f"-c idle_in_transaction_session_timeout={idle_timeout_ms}"
        ),
    }
    if require_ssl:
        opciones["sslmode"] = "require"
    return opciones


def crear_motor(
    url: str,
    application_name: str = "revo",
    pool_size: int = 10,
    max_overflow: int = 10,
    require_ssl: bool = False,
    echo: bool = False,
) -> Engine:
    """
    Crea el engine con los limites de produccion.

    Sobre el tamano del pool: cada worker de uvicorn abre su propio pool. Con
    3 servicios x 2 workers x (10 + 10) salen hasta 120 conexiones, y el
    limite por defecto de Postgres es 100. Los numeros de aqui estan pensados
    para un despliegue pequeno; si se suben los workers, hay que subir
    max_connections en Postgres o poner PgBouncer delante.
    """
    if not url:
        raise ValueError("DATABASE_URL no puede estar vacia")
    if not url.startswith(PREFIJOS_VALIDOS):
        raise ValueError(f"DATABASE_URL debe apuntar a PostgreSQL, no a {url.split('://')[0]!r}")

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=POOL_RECYCLE_SECONDS,
        connect_args=opciones_de_conexion(
            application_name=application_name, require_ssl=require_ssl
        ),
        echo=echo,
    )


def aplicar_contexto(ejecutor, contexto: ContextoSeguridad | None) -> None:
    """
    Escribe el contexto de seguridad usando el ejecutor que se le pase.

    El ejecutor puede ser una Session o una Connection. La distincion importa:
    dentro del evento `after_begin` hay que usar la CONEXION que el evento
    entrega, nunca la sesion. Llamar a `sesion.execute()` ahi hace que la
    sesion pida una conexion mientras esta provisionandola, y SQLAlchemy
    aborta con "This session is provisioning a new connection". Lo detectaron
    las pruebas de integracion del registro.
    """
    if contexto is None:
        # Sesiones sin usuario (arranque, tareas de fondo). Se quedan sin
        # identidad a proposito: RLS les niega las tablas de alumnos.
        return

    ejecutor.execute(SENTENCIA_CONTEXTO, parametros_contexto(contexto))


def aplicar_contexto_en_sesion(sesion) -> None:
    """Aplica a una sesion el contexto que lleva guardado."""
    aplicar_contexto(sesion, sesion.info.get(CLAVE_CONTEXTO))


def crear_fabrica_sesiones(motor: Engine) -> sessionmaker:
    """Crea la fabrica de sesiones con el contexto RLS ya cableado."""
    fabrica = sessionmaker(bind=motor, autocommit=False, autoflush=False, class_=Session)

    @event.listens_for(fabrica, "after_begin")
    def _al_empezar_transaccion(sesion, transaccion, conexion):  # noqa: ARG001
        # Sobre la conexion, no sobre la sesion: ver aplicar_contexto().
        aplicar_contexto(conexion, sesion.info.get(CLAVE_CONTEXTO))

    return fabrica


def fijar_contexto(sesion, contexto: ContextoSeguridad | None) -> None:
    """
    Asocia una identidad a la sesion y la aplica ya mismo si hay transaccion.

    Se llama desde la dependencia de FastAPI, en cuanto el token esta
    verificado y antes de tocar ninguna tabla.
    """
    if contexto is None:
        sesion.info.pop(CLAVE_CONTEXTO, None)
        return

    sesion.info[CLAVE_CONTEXTO] = contexto

    if sesion.in_transaction():
        # Ya hay transaccion abierta: `after_begin` no volvera a dispararse
        # hasta el proximo commit, asi que se aplica ahora sobre la conexion
        # viva. Sin esto, un cambio de identidad a mitad de peticion (el
        # login, que empieza sin identidad y la adquiere) no llegaria a RLS.
        aplicar_contexto(sesion.connection(), contexto)
