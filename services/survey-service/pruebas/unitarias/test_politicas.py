"""
Pruebas de los cupos del survey-service.

La regla que sostiene el diseno: TODO cupo de este servicio cuenta por
alumno, nunca por IP. Cincuenta alumnos tras el mismo router salen con
cincuenta cupos independientes y ninguno puede agotar el de otro.
"""
from politicas import POLITICAS
from revo_comun.limites.politicas import Scope


class TestElAulaNoSeEstorba:
    def test_todos_los_cupos_cuentan_por_alumno(self):
        for nombre, politica in POLITICAS.items():
            assert politica.scope is Scope.USER_OR_IP, (
                f"{nombre} cuenta por IP: un alumno podria agotar el cupo de toda la clase"
            )

    def test_el_cupo_de_respuestas_cubre_un_cuestionario_entero(self):
        # 10 preguntas de fase 1 + 15 de fase 2, mas el guardado masivo y los
        # reintentos del frontend.
        assert POLITICAS["answers"].limit >= 40

    def test_cerrar_fase_admite_los_reintentos_del_frontend(self):
        # El frontend reintenta hasta 3 veces cuando un servicio despierta.
        assert POLITICAS["submit_phase"].limit >= 10

    def test_ningun_cupo_tumba_la_clase_si_redis_cae(self):
        for nombre, politica in POLITICAS.items():
            assert politica.fail_open is True, nombre


class TestSeparacionDeResponsabilidades:
    def test_este_servicio_no_declara_cupos_ajenos(self):
        for ajeno in ("login", "register", "predict"):
            assert ajeno not in POLITICAS, ajeno
