"""
contexto.py — Fija en la transaccion QUIEN esta haciendo la consulta.

Las politicas RLS de Postgres (ver database/10_rls.sql) comparan cada fila
contra `current_setting('revo.user_id')`. Este modulo es el unico sitio que
escribe ese valor.

Por que `set_config(...)` y no `SET LOCAL`:
  `SET LOCAL revo.user_id = '42'` no admite parametros ligados, asi que
  obliga a construir la sentencia concatenando texto. Concatenar el
  identificador del usuario dentro de la sentencia que DEFINE su identidad
  es la inyeccion mas grave que puede tener el sistema. `set_config` es una
  funcion normal: acepta parametros y el valor viaja como dato.

El tercer argumento `true` hace el valor local a la transaccion. Sin el, el
valor se queda pegado a la conexion; cuando el pool se la entrega al
siguiente alumno, este hereda la identidad del anterior y RLS le abre las
filas equivocadas.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

#: Rol de las tareas de fondo (reentrenamiento del modelo). NO existe en
#: revo_comun.seguridad.tokens: nunca se emite ni se acepta dentro de un JWT.
#: Vive solo aqui para que un trabajo sin usuario tenga identidad propia en
#: lugar de correr como admin, que abriria todas las tablas ante cualquier
#: fallo en esa ruta.
ROL_SERVICIO = "service"

#: Identificador reservado del contexto de servicio. Ningun usuario real lo
#: tiene: la secuencia de `users` empieza en 1.
USUARIO_SERVICIO = 0

#: Roles que las politicas RLS reconocen. Es un superconjunto de VALID_ROLES
#: de revo_comun.seguridad.tokens, por el rol de servicio.
ROLES_VALIDOS = frozenset({"student", "admin", ROL_SERVICIO})

SENTENCIA_CONTEXTO = text(
    "SELECT set_config('revo.user_id', :user_id, true), "
    "       set_config('revo.role', :role, true)"
)

SENTENCIA_LIMPIEZA = text(
    "SELECT set_config('revo.user_id', '', true), "
    "       set_config('revo.role', '', true)"
)


@dataclass(frozen=True)
class ContextoSeguridad:
    """Identidad verificada que se propaga a la base de datos."""

    user_id: int
    role: str

    @classmethod
    def de_servicio(cls) -> "ContextoSeguridad":
        """Identidad de las tareas de fondo: sin alumno detras y sin ser admin."""
        return cls(user_id=USUARIO_SERVICIO, role=ROL_SERVICIO)

    def __post_init__(self) -> None:
        if self.role not in ROLES_VALIDOS:
            raise ValueError(f"Rol no reconocido para RLS: {self.role!r}")

        try:
            numero = int(self.user_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"user_id no es un identificador valido: {self.user_id!r}") from exc

        if self.role == ROL_SERVICIO:
            # El contexto de servicio se construye solo con de_servicio(),
            # que fija el identificador reservado.
            if numero != USUARIO_SERVICIO:
                raise ValueError("El rol de servicio no lleva un alumno asociado")
        elif numero <= 0:
            raise ValueError(f"user_id debe ser positivo: {numero}")

        # Se normaliza a entero para que "42" y 42 produzcan el mismo valor
        # y para que nada que no sea un numero llegue a la base de datos.
        object.__setattr__(self, "user_id", numero)


def parametros_contexto(contexto: ContextoSeguridad) -> dict[str, str]:
    """Parametros ligados para SENTENCIA_CONTEXTO."""
    return {"user_id": str(contexto.user_id), "role": contexto.role}
