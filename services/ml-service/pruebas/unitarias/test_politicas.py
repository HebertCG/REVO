"""
Pruebas del cupo del ml-service.

La inferencia es la operacion con mas coste de CPU del sistema: cada
prediccion carga el modelo y calcula probabilidades para diez clases. Su
cupo es, a proposito, el mas estrecho de las rutas de alumno.
"""
from politicas import POLITICAS
from revo_comun.limites.politicas import Scope


class TestCupoDeInferencia:
    def test_la_prediccion_cuenta_por_alumno(self):
        # Por IP castigaria al aula entera: cincuenta alumnos terminan el
        # cuestionario casi a la vez y todos piden su prediccion.
        assert POLITICAS["predict"].scope is Scope.USER_OR_IP

    def test_admite_los_reintentos_del_frontend(self):
        # El frontend reintenta hasta 3 veces cuando un servicio despierta.
        assert POLITICAS["predict"].limit >= 10

    def test_no_tumba_al_alumno_si_redis_cae(self):
        assert POLITICAS["predict"].fail_open is True


class TestSeparacionDeResponsabilidades:
    def test_este_servicio_no_declara_cupos_ajenos(self):
        for ajeno in ("login", "register", "answers", "submit_phase"):
            assert ajeno not in POLITICAS, ajeno
