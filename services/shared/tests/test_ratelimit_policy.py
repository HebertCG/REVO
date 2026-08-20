"""
El requisito que motiva estas pruebas: un salon de 50 alumnos comparte
una sola IP publica. Si el rate limit se aplica por IP, el alumno 11
recibe HTTP 429 y el examen se cae para toda la clase.
"""
import pytest

from revo_common.ratelimit.policy import (
    POLICIES,
    RateLimitPolicy,
    RequestContext,
    Scope,
    resolve_bucket,
)


def ctx(user_id=None, ip="200.60.1.1", credential=None):
    return RequestContext(user_id=user_id, client_ip=ip, credential=credential)


class TestAislamientoPorAlumno:
    def test_dos_alumnos_en_la_misma_ip_no_comparten_cupo(self):
        policy = RateLimitPolicy("answers", limit=60, window_seconds=60, scope=Scope.USER_OR_IP)

        bucket_a = resolve_bucket(policy, ctx(user_id=11))
        bucket_b = resolve_bucket(policy, ctx(user_id=12))

        assert bucket_a != bucket_b

    def test_un_salon_completo_produce_cincuenta_cupos_distintos(self):
        policy = RateLimitPolicy("answers", limit=60, window_seconds=60, scope=Scope.USER_OR_IP)
        aula = [resolve_bucket(policy, ctx(user_id=i)) for i in range(1, 51)]

        assert len(set(aula)) == 50

    def test_el_mismo_alumno_desde_otra_ip_conserva_su_cupo(self):
        policy = RateLimitPolicy("answers", limit=60, window_seconds=60, scope=Scope.USER_OR_IP)

        desde_aula = resolve_bucket(policy, ctx(user_id=7, ip="200.60.1.1"))
        desde_casa = resolve_bucket(policy, ctx(user_id=7, ip="181.65.9.9"))

        assert desde_aula == desde_casa


class TestTraficoAnonimo:
    def test_sin_token_se_cae_a_la_ip(self):
        policy = RateLimitPolicy("register", limit=10, window_seconds=3600, scope=Scope.USER_OR_IP)

        bucket = resolve_bucket(policy, ctx(user_id=None, ip="200.60.1.1"))

        assert bucket.endswith("200.60.1.1")
        assert ":i:" in bucket

    def test_scope_ip_ignora_al_usuario(self):
        policy = RateLimitPolicy("global", limit=1000, window_seconds=60, scope=Scope.IP)

        con_usuario = resolve_bucket(policy, ctx(user_id=9, ip="200.60.1.1"))
        sin_usuario = resolve_bucket(policy, ctx(user_id=None, ip="200.60.1.1"))

        assert con_usuario == sin_usuario


class TestCredencial:
    def test_el_bucket_de_login_separa_por_cuenta_atacada(self):
        policy = RateLimitPolicy("login", limit=5, window_seconds=900, scope=Scope.CREDENTIAL)

        victima = resolve_bucket(policy, ctx(credential="alumno@uni.pe"))
        otra = resolve_bucket(policy, ctx(credential="otro@uni.pe"))

        assert victima != otra

    def test_la_credencial_nunca_viaja_en_claro_a_redis(self):
        policy = RateLimitPolicy("login", limit=5, window_seconds=900, scope=Scope.CREDENTIAL)

        bucket = resolve_bucket(policy, ctx(credential="alumno@uni.pe"))

        assert "alumno@uni.pe" not in bucket

    def test_la_credencial_es_insensible_a_mayusculas_y_espacios(self):
        policy = RateLimitPolicy("login", limit=5, window_seconds=900, scope=Scope.CREDENTIAL)

        normal = resolve_bucket(policy, ctx(credential="alumno@uni.pe"))
        ruidosa = resolve_bucket(policy, ctx(credential="  ALUMNO@UNI.PE  "))

        assert normal == ruidosa

    def test_sin_credencial_cae_a_la_ip(self):
        policy = RateLimitPolicy("login", limit=5, window_seconds=900, scope=Scope.CREDENTIAL)

        bucket = resolve_bucket(policy, ctx(credential=None, ip="200.60.1.1"))

        assert ":i:" in bucket


class TestCatalogoDePoliticas:
    def test_las_rutas_de_juego_se_limitan_por_alumno_no_por_ip(self):
        for nombre in ("answers", "submit_phase", "predict"):
            assert POLICIES[nombre].scope is Scope.USER_OR_IP, nombre

    def test_el_cupo_de_respuestas_cubre_un_cuestionario_completo(self):
        # 10 preguntas de fase 1 + 15 de fase 2 + reintentos y guardado masivo.
        assert POLICIES["answers"].limit >= 40

    def test_el_login_es_estricto_para_frenar_fuerza_bruta(self):
        assert POLICIES["login"].limit <= 10
        assert POLICIES["login"].scope is Scope.CREDENTIAL

    def test_las_rutas_de_juego_no_tumban_la_clase_si_redis_cae(self):
        assert POLICIES["answers"].fail_open is True

    def test_las_rutas_de_administracion_se_cierran_si_redis_cae(self):
        assert POLICIES["admin"].fail_open is False

    def test_toda_politica_declara_una_ventana_positiva(self):
        for nombre, policy in POLICIES.items():
            assert policy.window_seconds > 0, nombre
            assert policy.limit > 0, nombre


class TestValidacion:
    def test_una_politica_sin_cupo_es_un_error_de_programacion(self):
        with pytest.raises(ValueError):
            RateLimitPolicy("rota", limit=0, window_seconds=60, scope=Scope.IP)

    def test_una_politica_sin_ventana_es_un_error_de_programacion(self):
        with pytest.raises(ValueError):
            RateLimitPolicy("rota", limit=10, window_seconds=0, scope=Scope.IP)
