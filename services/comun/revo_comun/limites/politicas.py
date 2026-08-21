"""
policy.py — Decide QUE cupo aplica a una peticion y BAJO QUE llave se cuenta.

Es logica pura y sin dependencias de red a proposito: la eleccion de la
llave es la parte del rate limiting que tiene consecuencias de producto
(un salon entero bloqueado) y debe poder probarse sin Redis.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

# Prefijo de todas las llaves en Redis. Permite un FLUSH selectivo y evita
# colisiones si la instancia se comparte con otro sistema.
KEY_PREFIX = "revo:rl"

# La credencial (email) jamas se escribe en claro en Redis: se guarda un
# prefijo del SHA-256. 16 hex = 64 bits, suficiente para no colisionar en
# un contador efimero y no reversible a un email.
_CREDENTIAL_HASH_CHARS = 16


class Scope(str, Enum):
    """Contra que identidad se cuenta el gasto."""

    #: Por alumno autenticado; solo cae a la IP si no hay token valido.
    USER_OR_IP = "user_or_ip"
    #: Siempre por IP. Reservado para el techo global anti-abuso.
    IP = "ip"
    #: Por cuenta objetivo (email). Frena fuerza bruta sin castigar al aula.
    CREDENTIAL = "credential"


@dataclass(frozen=True)
class RateLimitPolicy:
    """Un cupo con nombre: N peticiones por ventana, contra una identidad."""

    name: str
    limit: int
    window_seconds: int
    scope: Scope
    #: Que hacer si Redis no responde. True = dejar pasar (prioriza que la
    #: clase no se caiga), False = rechazar (prioriza no perder el control).
    fail_open: bool = True

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError(f"La politica '{self.name}' necesita un cupo positivo")
        if self.window_seconds <= 0:
            raise ValueError(f"La politica '{self.name}' necesita una ventana positiva")


@dataclass(frozen=True)
class RequestContext:
    """Lo minimo que el limitador necesita saber de una peticion."""

    client_ip: str
    user_id: int | None = None
    credential: str | None = None


def _hash_credential(raw: str) -> str:
    normalized = raw.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:_CREDENTIAL_HASH_CHARS]


def resolve_bucket(policy: RateLimitPolicy, context: RequestContext) -> str:
    """
    Devuelve la llave de Redis bajo la que se cuenta esta peticion.

    La regla que sostiene el caso del aula: cuando hay alumno identificado
    se cuenta por alumno. Cincuenta alumnos tras el mismo router salen con
    cincuenta llaves distintas y cincuenta cupos independientes.
    """
    if policy.scope is Scope.CREDENTIAL:
        if context.credential:
            return f"{KEY_PREFIX}:{policy.name}:c:{_hash_credential(context.credential)}"
        return f"{KEY_PREFIX}:{policy.name}:i:{context.client_ip}"

    if policy.scope is Scope.USER_OR_IP and context.user_id is not None:
        return f"{KEY_PREFIX}:{policy.name}:u:{context.user_id}"

    return f"{KEY_PREFIX}:{policy.name}:i:{context.client_ip}"


# ── Catalogo de politicas ────────────────────────────────────
# Los numeros salen del uso real, no de una cifra redonda:
#   - un cuestionario completo son 25 respuestas + guardado masivo + reintentos
#   - un alumno hace como mucho un par de sesiones seguidas
#   - el techo por IP debe aguantar un aula entera trabajando a la vez
POLICIES: dict[str, RateLimitPolicy] = {
    # Escritura de respuestas durante el juego. Por alumno, generoso:
    # el front guarda tras cada pregunta y ademas hace un guardado masivo.
    "answers": RateLimitPolicy(
        name="answers", limit=120, window_seconds=60, scope=Scope.USER_OR_IP, fail_open=True
    ),
    # Cierre de fase. Dispara la prediccion, es caro; pero el front reintenta
    # hasta 3 veces cuando Render despierta el servicio.
    "submit_phase": RateLimitPolicy(
        name="submit_phase", limit=20, window_seconds=300, scope=Scope.USER_OR_IP, fail_open=True
    ),
    # Inferencia del modelo.
    "predict": RateLimitPolicy(
        name="predict", limit=20, window_seconds=300, scope=Scope.USER_OR_IP, fail_open=True
    ),
    # Lectura de preguntas y catalogos.
    "read": RateLimitPolicy(
        name="read", limit=240, window_seconds=60, scope=Scope.USER_OR_IP, fail_open=True
    ),
    # ── Acceso: dos cupos a la vez, no uno ───────────────────
    # Las rutas sin identidad previa (login, registro) son las unicas donde
    # hay que contar por IP, y ahi choca de frente el caso del aula: 50
    # alumnos comparten una sola IP publica y llegan todos en el mismo
    # minuto. Un unico cupo no puede distinguir eso de un bot, porque a lo
    # largo de una hora los dos hacen el mismo numero de peticiones.
    #
    # La diferencia esta en la FORMA del trafico: el aula es una rafaga
    # corta y luego silencio; el bot es un goteo constante durante horas.
    # Por eso se aplican dos cupos simultaneos a cada ruta: uno ancho y
    # corto que deja pasar la rafaga, y uno estrecho y largo que corta el
    # goteo sostenido.

    # Login por cuenta atacada. Frena la fuerza bruta contra un alumno
    # concreto sin tocar al resto del aula, porque cada uno usa su email.
    "login": RateLimitPolicy(
        name="login", limit=8, window_seconds=900, scope=Scope.CREDENTIAL, fail_open=True
    ),
    # Login por IP, cupo sostenido. Sin esto, un atacante prueba tres
    # contrasenas contra diez mil cuentas distintas y ningun cupo por
    # credencial se entera. 400/hora deja entrar a un aula con reintentos y
    # corta el rociado de credenciales.
    "login_por_ip": RateLimitPolicy(
        name="login_por_ip", limit=400, window_seconds=3600, scope=Scope.IP, fail_open=True
    ),

    # Alta de cuentas, rafaga: un aula completa registrandose a la vez el
    # primer dia de clase. 80 en 10 minutos cubre 50 alumnos con reintentos.
    "register": RateLimitPolicy(
        name="register", limit=80, window_seconds=600, scope=Scope.IP, fail_open=True
    ),
    # Alta de cuentas, sostenido: ~3 aulas al dia desde la misma IP. Un bot
    # creando cuentas en cadena topa aqui aunque respete la rafaga.
    "register_diario": RateLimitPolicy(
        name="register_diario", limit=250, window_seconds=86_400, scope=Scope.IP, fail_open=True
    ),
    # Panel de administracion. Poco trafico y alto valor: si Redis cae,
    # se cierra en vez de quedar sin control.
    "admin": RateLimitPolicy(
        name="admin", limit=120, window_seconds=60, scope=Scope.USER_OR_IP, fail_open=False
    ),
    # Techo global anti-abuso por IP. Existe para absorber un flood, no para
    # regular el uso normal: un aula de 50 alumnos jugando genera muy por
    # debajo de este numero.
    "global": RateLimitPolicy(
        name="global", limit=1200, window_seconds=60, scope=Scope.IP, fail_open=True
    ),
}
