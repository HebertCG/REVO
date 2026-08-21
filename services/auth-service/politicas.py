"""
politicas.py — Cupos de rate limit propios del auth-service.

Viven aqui y no en la libreria compartida porque solo este servicio los usa.
Cambiar el cupo de login no deberia obligar a reconstruir el cuestionario ni
el modelo de ML.

Las rutas de acceso (login, registro) son las unicas donde hay que contar por
IP, porque todavia no hay identidad. Y ahi choca de frente el caso del aula:
50 alumnos comparten una sola IP publica y llegan todos en el mismo minuto.

Un unico cupo no puede distinguir eso de un bot: a lo largo de una hora los
dos hacen el mismo numero de peticiones. La diferencia esta en la FORMA del
trafico —el aula es una rafaga corta y luego silencio; el bot es un goteo
constante durante horas— asi que se aplican dos cupos a la vez.
"""
from revo_comun.limites.politicas import RateLimitPolicy, Scope

POLITICAS = {
    # Por cuenta atacada: frena la fuerza bruta contra un alumno concreto sin
    # tocar al resto del aula, porque cada uno usa su propio email.
    "login": RateLimitPolicy(
        name="login", limit=8, window_seconds=900, scope=Scope.CREDENTIAL, fail_open=True
    ),
    # Por IP: sin esto, un atacante prueba tres contrasenas contra diez mil
    # cuentas distintas y ningun cupo por credencial se entera.
    "login_por_ip": RateLimitPolicy(
        name="login_por_ip", limit=400, window_seconds=3600, scope=Scope.IP, fail_open=True
    ),
    # Rafaga: un aula completa registrandose el primer dia de clase.
    # Medido: con 80 en 10 minutos entran los 50 alumnos con margen.
    "register": RateLimitPolicy(
        name="register", limit=80, window_seconds=600, scope=Scope.IP, fail_open=True
    ),
    # Sostenido: ~3 aulas al dia desde la misma IP. Un bot que cree cuentas
    # en cadena topa aqui aunque respete la rafaga.
    "register_diario": RateLimitPolicy(
        name="register_diario", limit=250, window_seconds=86_400, scope=Scope.IP, fail_open=True
    ),
}
