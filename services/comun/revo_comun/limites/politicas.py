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


# ── Politicas comunes ────────────────────────────────────────
# Aqui SOLO viven los cupos que necesita cualquier servicio. Los cupos de un
# dominio concreto (responder el cuestionario, pedir una prediccion) los
# declara el servicio dueno, en su propio modulo `politicas.py`.
#
# El motivo no es estetico. Con todos los cupos aqui, cambiar el limite de
# respuestas del cuestionario obligaba a tocar la libreria compartida y a
# reconstruir las tres imagenes: un cambio que solo afecta a survey-service
# se convertia en un despliegue de todo el sistema. La libreria aporta el
# MECANISMO; cada servicio decide su POLITICA.
POLITICAS_COMUNES: dict[str, RateLimitPolicy] = {
    # Lecturas de catalogos y perfil. Las hacen los tres.
    "read": RateLimitPolicy(
        name="read", limit=240, window_seconds=60, scope=Scope.USER_OR_IP, fail_open=True
    ),
    # Panel de administracion. Poco trafico y alto valor: si Redis cae, se
    # cierra en vez de quedar sin control.
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


def combinar_politicas(
    propias: dict[str, RateLimitPolicy] | None = None,
) -> dict[str, RateLimitPolicy]:
    """
    Une las politicas comunes con las que declara el servicio.

    Si un servicio define una politica con un nombre comun, la suya gana: es
    su decision y la libreria no debe imponerle un limite que no le encaja.
    """
    catalogo = dict(POLITICAS_COMUNES)
    if propias:
        catalogo.update(propias)
    return catalogo
