"""
El requisito que motiva estas pruebas: un salon de 50 alumnos comparte
una sola IP publica. Si el rate limit se aplica por IP, el alumno 11
recibe HTTP 429 y el examen se cae para toda la clase.
"""
import pytest

from revo_comun.limites.politicas import (
    POLITICAS_COMUNES,
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


class TestCatalogoComun:
    """
    Aqui solo se comprueba lo COMUN. Los cupos de dominio (responder el
    cuestionario, pedir una prediccion) los declara y los prueba su propio
    servicio: si vivieran aqui, cambiar el limite del cuestionario obligaria
    a reconstruir tambien auth y ml.
    """

    def test_solo_contiene_lo_que_usan_todos(self):
        assert set(POLITICAS_COMUNES) == {"read", "admin", "global"}

    def test_no_conoce_el_dominio_de_ningun_servicio(self):
        # Si alguno de estos nombres vuelve aqui, la libreria ha vuelto a
        # saber cosas que no le corresponden.
        for nombre in ("answers", "submit_phase", "predict", "login", "register"):
            assert nombre not in POLITICAS_COMUNES, nombre

    def test_las_rutas_de_administracion_se_cierran_si_redis_cae(self):
        assert POLITICAS_COMUNES["admin"].fail_open is False

    def test_toda_politica_declara_una_ventana_positiva(self):
        for nombre, policy in POLITICAS_COMUNES.items():
            assert policy.window_seconds > 0, nombre
            assert policy.limit > 0, nombre


class TestCombinarPoliticas:
    def test_une_las_comunes_con_las_del_servicio(self):
        from revo_comun.limites.politicas import combinar_politicas

        propia = RateLimitPolicy("answers", limit=120, window_seconds=60, scope=Scope.USER_OR_IP)
        catalogo = combinar_politicas({"answers": propia})

        assert catalogo["answers"] is propia
        assert "read" in catalogo

    def test_sin_politicas_propias_devuelve_solo_las_comunes(self):
        from revo_comun.limites.politicas import combinar_politicas

        assert set(combinar_politicas()) == set(POLITICAS_COMUNES)

    def test_el_servicio_puede_endurecer_un_cupo_comun(self):
        # Su decision manda: la libreria no le impone un limite que no encaja.
        from revo_comun.limites.politicas import combinar_politicas

        estricta = RateLimitPolicy("read", limit=10, window_seconds=60, scope=Scope.USER_OR_IP)
        assert combinar_politicas({"read": estricta})["read"].limit == 10

    def test_combinar_no_modifica_el_catalogo_comun(self):
        # Un servicio que ajusta un cupo no puede alterarselo a los demas.
        from revo_comun.limites.politicas import combinar_politicas

        combinar_politicas({"read": RateLimitPolicy("read", 1, 60, Scope.IP)})

        assert POLITICAS_COMUNES["read"].limit == 240


class TestValidacion:
    def test_una_politica_sin_cupo_es_un_error_de_programacion(self):
        with pytest.raises(ValueError):
            RateLimitPolicy("rota", limit=0, window_seconds=60, scope=Scope.IP)

    def test_una_politica_sin_ventana_es_un_error_de_programacion(self):
        with pytest.raises(ValueError):
            RateLimitPolicy("rota", limit=10, window_seconds=0, scope=Scope.IP)
