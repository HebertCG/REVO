"""
politicas.py — Cupos de rate limit propios del survey-service.

Todas cuentan por alumno y no por IP. Es la decision que sostiene el caso del
aula: cincuenta alumnos tras el mismo router salen con cincuenta cupos
independientes, asi que ninguno puede agotar el de otro.
"""
from revo_comun.limites.politicas import RateLimitPolicy, Scope

POLITICAS = {
    # El frontend guarda tras cada pregunta y ademas hace un guardado masivo
    # al final, asi que un cuestionario completo son bastantes escrituras.
    "answers": RateLimitPolicy(
        name="answers", limit=120, window_seconds=60, scope=Scope.USER_OR_IP, fail_open=True
    ),
    # Cierre de fase: dispara la prediccion y es la peticion mas cara. El
    # frontend reintenta hasta 3 veces cuando un servicio esta despertando.
    "submit_phase": RateLimitPolicy(
        name="submit_phase", limit=20, window_seconds=300, scope=Scope.USER_OR_IP, fail_open=True
    ),
}
