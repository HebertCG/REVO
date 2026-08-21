"""
tokens.py — Emision y verificacion de los JWT de REVO, en un solo sitio.

Antes cada microservicio traia su propio `extract_user_id` de seis lineas
que solo comprobaba firma y expiracion. Tres copias significan tres sitios
donde arreglar el mismo fallo, y ninguna comprobaba emisor, audiencia ni
proposito del token.

Decisiones que importan:
  - Se usa PyJWT y no python-jose. python-jose se quedo en la version 3.3.0
    de 2021 y arrastra CVE conocidos (CVE-2024-33663 de confusion de
    algoritmo y CVE-2024-33664 de denegacion de servicio al descomprimir).
    El uso de aqui no es explotable por ninguno de los dos, porque la lista
    de algoritmos es fija y no se descifra JWE, pero una libreria sin
    mantenimiento en la pieza que decide QUIEN eres no es defendible: el
    proximo fallo no tendria arreglo. Es el mismo motivo por el que se
    quito passlib.
  - `algorithms` es una lista fija. Si se pasa el algoritmo del propio token
    a la verificacion, un atacante elige "none" y firma lo que quiera.
  - `aud` e `iss` se verifican siempre: sin ellos, un token de cualquier otro
    sistema que comparta secreto vale aqui.
  - `typ` distingue el token de acceso de cualquier otro que emitamos luego
    (refresco, reset de password). Sin el, todos son intercambiables.
  - `sub` debe ser un entero. Es lo que acaba en un WHERE user_id = ...
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from jwt import PyJWTError

ACCESS_TOKEN_TYPE = "access"

ALGORITHM = "HS256"

#: Roles reconocidos. Un rol fuera de esta lista no existe, aunque venga
#: firmado: asi un fallo en el alta de usuarios no se convierte en una
#: escalada de privilegios.
VALID_ROLES = frozenset({"student", "admin"})

#: Longitud minima del secreto HS256. Por debajo de esto el secreto se puede
#: atacar por fuerza bruta fuera de linea con un solo token capturado.
MIN_SECRET_LENGTH = 32

#: Valores de ejemplo que aparecen en plantillas y tutoriales. Si alguno
#: llega a produccion, el sistema entero es publico.
FORBIDDEN_SECRET_MARKERS = (
    "cambia_esta",
    "changeme",
    "your-secret",
    "secret-key",
    "supersecret",
    "revo-secret",
    "test",
)


class TokenError(Exception):
    """El token no es utilizable. Nunca detalla por que, de cara al cliente."""


@dataclass(frozen=True)
class Principal:
    """Quien hace la peticion, ya verificado."""

    user_id: int
    role: str
    jti: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _validate_secret(secret: str) -> None:
    if not secret or len(secret) < MIN_SECRET_LENGTH:
        raise ValueError(
            f"JWT_SECRET debe tener al menos {MIN_SECRET_LENGTH} caracteres. "
            "Genera uno con: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    minusculas = secret.lower()
    for marcador in FORBIDDEN_SECRET_MARKERS:
        if marcador in minusculas:
            raise ValueError(
                f"JWT_SECRET contiene el valor de ejemplo '{marcador}'. "
                "Genera un secreto propio antes de arrancar."
            )


class TokenIssuer:
    """Emite y verifica los tokens de acceso de REVO."""

    def __init__(
        self,
        secret: str,
        issuer: str,
        audience: str,
        expire_hours: int = 24,
    ):
        _validate_secret(secret)
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._expire = timedelta(hours=expire_hours)

    # ── Emision ──────────────────────────────────────────────
    def issue(self, user_id: int, role: str, expire_seconds: int | None = None) -> str:
        """
        Emite un token de acceso.

        Args:
            user_id: identificador del alumno.
            role: "student" o "admin".
            expire_seconds: caducidad propia en segundos. Se usa para las
                llamadas entre servicios, donde el token solo tiene que vivir
                lo que dura una peticion: un token interno con la caducidad
                de sesion (24 h) que acabe en un log es reutilizable durante
                un dia entero.
        """
        if role not in VALID_ROLES:
            raise ValueError(f"Rol no reconocido: {role!r}")

        if expire_seconds is not None and expire_seconds <= 0:
            raise ValueError("La caducidad debe ser positiva")

        vigencia = (
            timedelta(seconds=expire_seconds) if expire_seconds is not None else self._expire
        )
        ahora = datetime.now(timezone.utc)
        claims = {
            "sub": str(int(user_id)),
            "role": role,
            "iss": self._issuer,
            "aud": self._audience,
            "typ": ACCESS_TOKEN_TYPE,
            "iat": int(ahora.timestamp()),
            "exp": int((ahora + vigencia).timestamp()),
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(claims, self._secret, algorithm=ALGORITHM)

    @property
    def expires_in_seconds(self) -> int:
        return int(self._expire.total_seconds())

    # ── Verificacion ─────────────────────────────────────────
    def verify(self, token: str | None) -> Principal:
        if not token or not isinstance(token, str) or not token.strip():
            raise TokenError("Token ausente")

        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                issuer=self._issuer,
                audience=self._audience,
                # `require` obliga a que las tres esten presentes: un token
                # sin exp no caduca nunca, y uno sin iat no se puede fechar.
                options={"require": ["exp", "iat", "sub"]},
            )
        except PyJWTError as exc:
            raise TokenError("Token invalido o expirado") from exc

        if claims.get("typ") != ACCESS_TOKEN_TYPE:
            raise TokenError("El token no es de acceso")

        role = claims.get("role")
        if role not in VALID_ROLES:
            raise TokenError("Rol no reconocido")

        try:
            user_id = int(claims["sub"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TokenError("Identidad no utilizable") from exc

        if user_id <= 0:
            raise TokenError("Identidad no utilizable")

        return Principal(user_id=user_id, role=role, jti=str(claims.get("jti", "")))

    def verify_header(self, authorization: str | None) -> Principal:
        """Verifica una cabecera `Authorization: Bearer <token>` completa."""
        if not authorization or not isinstance(authorization, str):
            raise TokenError("Falta la cabecera Authorization")

        partes = authorization.split(None, 1)
        if len(partes) != 2 or partes[0].lower() != "bearer":
            raise TokenError("Esquema de autorizacion no soportado")

        return self.verify(partes[1].strip())
