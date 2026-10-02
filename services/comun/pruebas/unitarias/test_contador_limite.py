"""
Pruebas del contador con ventana deslizante sobre Redis.

Se usa un reloj inyectado en vez de sleep(): las pruebas de tiempo con
sleep son lentas y se vuelven intermitentes en CI.
"""
import fakeredis
import pytest

from revo_comun.limites.contador import RateLimiter
from revo_comun.limites.politicas import RateLimitPolicy, RequestContext, Scope


class RelojFalso:
    def __init__(self, inicio=1_000_000.0):
        self.ahora = inicio

    def __call__(self):
        return self.ahora

    def avanzar(self, segundos):
        self.ahora += segundos


@pytest.fixture
def reloj():
    return RelojFalso()


@pytest.fixture
def limiter(reloj):
    return RateLimiter(redis_client=fakeredis.FakeStrictRedis(), clock=reloj)


POLICY = RateLimitPolicy("prueba", limit=3, window_seconds=60, scope=Scope.USER_OR_IP)
ALUMNO = RequestContext(client_ip="200.60.1.1", user_id=1)


class TestVentanaDeslizante:
    def test_deja_pasar_hasta_agotar_el_cupo(self, limiter):
        for _ in range(3):
            assert limiter.check(POLICY, ALUMNO).allowed is True

    def test_rechaza_la_peticion_que_excede_el_cupo(self, limiter):
        for _ in range(3):
            limiter.check(POLICY, ALUMNO)

        assert limiter.check(POLICY, ALUMNO).allowed is False

    def test_informa_cuanto_queda_del_cupo(self, limiter):
        assert limiter.check(POLICY, ALUMNO).remaining == 2
        assert limiter.check(POLICY, ALUMNO).remaining == 1
        assert limiter.check(POLICY, ALUMNO).remaining == 0

    def test_el_cupo_se_libera_al_salir_de_la_ventana(self, limiter, reloj):
        for _ in range(3):
            limiter.check(POLICY, ALUMNO)
        assert limiter.check(POLICY, ALUMNO).allowed is False

        reloj.avanzar(61)

        assert limiter.check(POLICY, ALUMNO).allowed is True

    def test_la_ventana_se_desliza_no_se_reinicia_de_golpe(self, limiter, reloj):
        limiter.check(POLICY, ALUMNO)
        reloj.avanzar(30)
        limiter.check(POLICY, ALUMNO)
        limiter.check(POLICY, ALUMNO)
        assert limiter.check(POLICY, ALUMNO).allowed is False

        # A los 61s solo caduca la PRIMERA peticion, no las tres.
        reloj.avanzar(31)
        assert limiter.check(POLICY, ALUMNO).allowed is True
        assert limiter.check(POLICY, ALUMNO).allowed is False

    def test_una_peticion_rechazada_no_consume_cupo(self, limiter, reloj):
        for _ in range(3):
            limiter.check(POLICY, ALUMNO)
        for _ in range(20):
            limiter.check(POLICY, ALUMNO)

        # Si los rechazos contaran, la ventana quedaria envenenada y el
        # alumno seguiria bloqueado despues de que expire el cupo real.
        reloj.avanzar(61)
        assert limiter.check(POLICY, ALUMNO).allowed is True

    def test_indica_en_cuantos_segundos_reintentar(self, limiter, reloj):
        for _ in range(3):
            limiter.check(POLICY, ALUMNO)
        reloj.avanzar(20)

        resultado = limiter.check(POLICY, ALUMNO)

        assert resultado.allowed is False
        assert 35 <= resultado.retry_after <= 41


class TestAislamientoEnElAula:
    def test_cincuenta_alumnos_tras_la_misma_ip_pasan_todos(self, limiter):
        aula = [RequestContext(client_ip="200.60.1.1", user_id=i) for i in range(1, 51)]

        permitidos = sum(limiter.check(POLICY, alumno).allowed for alumno in aula)

        assert permitidos == 50

    def test_un_alumno_agotado_no_bloquea_a_su_companero(self, limiter):
        agotado = RequestContext(client_ip="200.60.1.1", user_id=1)
        companero = RequestContext(client_ip="200.60.1.1", user_id=2)
        for _ in range(4):
            limiter.check(POLICY, agotado)

        assert limiter.check(POLICY, companero).allowed is True


class TestDegradacionSinRedis:
    def test_sin_redis_las_rutas_de_juego_dejan_pasar(self, reloj):
        limiter = RateLimiter(redis_client=None, clock=reloj)
        policy = RateLimitPolicy("juego", limit=3, window_seconds=60, scope=Scope.USER_OR_IP, fail_open=True)

        resultado = limiter.check(policy, ALUMNO)

        assert resultado.allowed is True
        assert resultado.degraded is True

    def test_sin_redis_las_rutas_de_administracion_se_cierran(self, reloj):
        limiter = RateLimiter(redis_client=None, clock=reloj)
        policy = RateLimitPolicy("admin", limit=3, window_seconds=60, scope=Scope.USER_OR_IP, fail_open=False)

        resultado = limiter.check(policy, ALUMNO)

        assert resultado.allowed is False
        assert resultado.degraded is True

    def test_si_redis_falla_a_media_sesion_no_revienta_la_peticion(self, reloj):
        class RedisRoto:
            def pipeline(self, *args, **kwargs):
                raise ConnectionError("redis caido")

        limiter = RateLimiter(redis_client=RedisRoto(), clock=reloj)
        policy = RateLimitPolicy("juego", limit=3, window_seconds=60, scope=Scope.USER_OR_IP, fail_open=True)

        resultado = limiter.check(policy, ALUMNO)

        assert resultado.allowed is True
        assert resultado.degraded is True

    def test_el_respaldo_en_memoria_sigue_frenando_un_flood(self, reloj):
        limiter = RateLimiter(redis_client=None, clock=reloj)
        policy = RateLimitPolicy("juego", limit=3, window_seconds=60, scope=Scope.USER_OR_IP, fail_open=True)

        # Aunque fail_open deje pasar el trafico normal, un flood contra el
        # mismo bucket debe seguir topando contra el respaldo local.
        resultados = [limiter.check(policy, ALUMNO) for _ in range(200)]

        assert any(r.allowed is False for r in resultados)


class TestHigiene:
    def test_las_llaves_expiran_solas(self, limiter):
        redis = limiter._redis
        limiter.check(POLICY, ALUMNO)

        clave = next(iter(redis.keys("*")))

        assert redis.ttl(clave) > 0
