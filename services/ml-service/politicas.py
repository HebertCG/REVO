"""
politicas.py — Cupos de rate limit propios del ml-service.

La inferencia es la operacion con mas coste de CPU del sistema, asi que su
cupo es el mas estrecho de las rutas de alumno.
"""
from revo_comun.limites.politicas import RateLimitPolicy, Scope

POLITICAS = {
    "predict": RateLimitPolicy(
        name="predict", limit=20, window_seconds=300, scope=Scope.USER_OR_IP, fail_open=True
    ),
}
