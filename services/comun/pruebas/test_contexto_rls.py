"""
Pruebas del contexto de seguridad a nivel de fila.

Las politicas RLS de Postgres leen `current_setting('revo.user_id')`. Si ese
valor se construye concatenando texto, un `user_id` manipulado inyecta SQL
directamente en la sentencia que define quien eres: la peor inyeccion posible.
Por eso se fija con `set_config(...)` y parametros ligados.
"""
import pytest

from revo_comun.basedatos.contexto import (
    ContextoSeguridad,
    SENTENCIA_CONTEXTO,
    SENTENCIA_LIMPIEZA,
    parametros_contexto,
)


class TestConstruccionDelContexto:
    def test_acepta_un_alumno_normal(self):
        ctx = ContextoSeguridad(user_id=42, role="student")

        assert parametros_contexto(ctx) == {"user_id": "42", "role": "student"}

    def test_acepta_un_administrador(self):
        ctx = ContextoSeguridad(user_id=1, role="admin")

        assert parametros_contexto(ctx)["role"] == "admin"

    def test_rechaza_un_rol_inventado(self):
        with pytest.raises(ValueError):
            ContextoSeguridad(user_id=1, role="superadmin")

    def test_rechaza_un_identificador_que_no_es_numero(self):
        with pytest.raises(ValueError):
            ContextoSeguridad(user_id="1 OR 1=1", role="student")

    def test_rechaza_un_identificador_negativo(self):
        with pytest.raises(ValueError):
            ContextoSeguridad(user_id=-5, role="student")

    def test_rechaza_un_identificador_ausente(self):
        with pytest.raises(ValueError):
            ContextoSeguridad(user_id=None, role="student")


class TestInmunidadAInyeccion:
    def test_la_sentencia_no_interpola_valores(self):
        # Si el SQL trae el valor pegado, la parametrizacion no sirve de nada.
        texto = str(SENTENCIA_CONTEXTO)

        assert ":user_id" in texto
        assert ":role" in texto
        assert "||" not in texto
        assert "format(" not in texto.lower()

    def test_usa_set_config_y_no_set_local(self):
        # SET LOCAL no admite parametros ligados: obliga a concatenar.
        texto = str(SENTENCIA_CONTEXTO).lower()

        assert "set_config" in texto
        assert "set local" not in texto

    def test_el_contexto_es_local_a_la_transaccion(self):
        # El tercer argumento de set_config en true limita el valor a la
        # transaccion. Sin eso, el valor sobrevive en la conexion y el
        # siguiente alumno que reciba esa conexion del pool hereda la
        # identidad del anterior.
        assert "true" in str(SENTENCIA_CONTEXTO).lower()

    def test_una_carga_hostil_viaja_como_dato_no_como_sql(self):
        # El rol se valida antes; el identificador se fuerza a entero. Lo
        # que llegue raro revienta al construir, no al ejecutar.
        with pytest.raises(ValueError):
            ContextoSeguridad(user_id="42; DROP TABLE users", role="student")


class TestLimpieza:
    def test_existe_una_sentencia_para_soltar_la_identidad(self):
        # Al devolver la conexion al pool hay que dejarla sin identidad, para
        # que una consulta sin contexto no herede la del alumno anterior.
        texto = str(SENTENCIA_LIMPIEZA).lower()

        assert "set_config" in texto
        assert "revo.user_id" in texto


class TestValoresLimite:
    def test_acepta_un_identificador_entero_en_texto(self):
        ctx = ContextoSeguridad(user_id="42", role="student")

        assert parametros_contexto(ctx)["user_id"] == "42"

    def test_rechaza_el_cero(self):
        with pytest.raises(ValueError):
            ContextoSeguridad(user_id=0, role="student")


class TestContextoDeServicio:
    def test_las_tareas_de_fondo_tienen_su_propia_identidad(self):
        # El reentrenamiento del modelo corre sin ningun alumno detras. Sin
        # una identidad propia tendria que correr como admin, y entonces
        # cualquier fallo en esa ruta abriria todas las tablas.
        ctx = ContextoSeguridad.de_servicio()

        assert ctx.role == "service"

    def test_el_rol_de_servicio_no_puede_venir_en_un_token(self):
        # Es la frontera que hace util al rol: existe para RLS, jamas se
        # emite ni se acepta dentro de un JWT.
        from revo_comun.seguridad.tokens import VALID_ROLES

        assert "service" not in VALID_ROLES

    def test_un_alumno_no_puede_declararse_servicio(self):
        with pytest.raises(ValueError):
            ContextoSeguridad(user_id=42, role="service")

    def test_el_rol_de_servicio_no_admite_un_alumno_asociado(self):
        parametros = parametros_contexto(ContextoSeguridad.de_servicio())

        assert parametros["user_id"] == "0"
        assert parametros["role"] == "service"
