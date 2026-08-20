"""
Pruebas del motor de base de datos y de la propagacion del contexto.

Lo que se prueba aqui es el cableado: que el contexto de seguridad se vuelva
a aplicar en CADA transaccion, no solo en la primera. Un commit a mitad de
peticion abre una transaccion nueva, y si el contexto no se reaplica, RLS
deja de ver quien eres y las consultas siguientes no devuelven nada (o, con
una politica mal escrita, lo devuelven todo).

La verificacion de las politicas contra un Postgres real vive en
pruebas/test_rls_integracion.py, que se salta si no hay base de datos.
"""
import pytest

from revo_comun.basedatos.contexto import ContextoSeguridad, SENTENCIA_CONTEXTO
from revo_comun.basedatos.motor import (
    CLAVE_CONTEXTO,
    aplicar_contexto_en_sesion,
    opciones_de_conexion,
)


class SesionFalsa:
    def __init__(self, info=None):
        self.info = info or {}
        self.ejecutadas = []

    def execute(self, sentencia, parametros=None):
        self.ejecutadas.append((str(sentencia), parametros))


class TestPropagacionDelContexto:
    def test_aplica_la_identidad_al_empezar_la_transaccion(self):
        sesion = SesionFalsa({CLAVE_CONTEXTO: ContextoSeguridad(user_id=42, role="student")})

        aplicar_contexto_en_sesion(sesion)

        sentencia, parametros = sesion.ejecutadas[0]
        assert "set_config" in sentencia
        assert parametros == {"user_id": "42", "role": "student"}

    def test_se_reaplica_en_cada_transaccion(self):
        sesion = SesionFalsa({CLAVE_CONTEXTO: ContextoSeguridad(user_id=42, role="student")})

        aplicar_contexto_en_sesion(sesion)
        aplicar_contexto_en_sesion(sesion)

        assert len(sesion.ejecutadas) == 2

    def test_una_sesion_sin_contexto_no_ejecuta_nada(self):
        # Tareas de fondo y arranque consultan sin usuario. Deben quedarse
        # sin identidad, no heredar una.
        sesion = SesionFalsa()

        aplicar_contexto_en_sesion(sesion)

        assert sesion.ejecutadas == []

    def test_la_sentencia_es_la_parametrizada_del_modulo_de_contexto(self):
        sesion = SesionFalsa({CLAVE_CONTEXTO: ContextoSeguridad(user_id=7, role="admin")})

        aplicar_contexto_en_sesion(sesion)

        assert sesion.ejecutadas[0][0] == str(SENTENCIA_CONTEXTO)


class TestOpcionesDeConexion:
    def test_corta_las_consultas_que_se_eternizan(self):
        # Sin statement_timeout una consulta atascada retiene su conexion
        # del pool para siempre; con el pool agotado, el aula entera espera.
        opciones = opciones_de_conexion(statement_timeout_ms=5000)

        assert "statement_timeout=5000" in opciones["options"]

    def test_corta_las_transacciones_ociosas(self):
        # Una transaccion abierta y olvidada bloquea VACUUM y mantiene
        # cerrojos sobre filas que otros necesitan.
        opciones = opciones_de_conexion(idle_timeout_ms=10000)

        assert "idle_in_transaction_session_timeout=10000" in opciones["options"]

    def test_identifica_al_servicio_en_pg_stat_activity(self):
        # Con tres servicios sobre la misma base, sin application_name no
        # se sabe cual de ellos abrio la consulta que esta dando guerra.
        opciones = opciones_de_conexion(application_name="revo-survey")

        assert "revo-survey" in opciones["application_name"]

    def test_exige_cifrado_cuando_se_pide(self):
        opciones = opciones_de_conexion(require_ssl=True)

        assert opciones["sslmode"] == "require"

    def test_no_exige_cifrado_en_local(self):
        opciones = opciones_de_conexion(require_ssl=False)

        assert "sslmode" not in opciones


class TestConfiguracionDelPool:
    def test_rechaza_una_url_vacia(self):
        from revo_comun.basedatos.motor import crear_motor

        with pytest.raises(ValueError):
            crear_motor("")

    def test_rechaza_una_url_que_no_es_de_postgres(self):
        from revo_comun.basedatos.motor import crear_motor

        with pytest.raises(ValueError):
            crear_motor("mysql://usuario:clave@host/base")
