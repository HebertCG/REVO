"""
Pruebas de lo que ml-service le pregunta a pgvector.

La base es falsa: lo que se prueba es que las consultas se construyen bien y,
sobre todo, que un fallo de pgvector NUNCA tumba una prediccion. La
correccion de las funciones SQL la comprueba la propia migracion 36 contra
PostgreSQL (incluido que el coseno de las formas es Pearson).
"""
import pytest
from sqlalchemy.exc import OperationalError

import consultas_vectoriales as cv
from model import ocupaciones

PERFILES = {
    1: [3.3, 5.4, 2.7, 2.0, 2.3, 5.5],   # Desarrollo de Software
    4: [3.9, 5.1, 1.9, 2.4, 3.0, 5.6],   # Ciberseguridad
    8: [2.4, 4.2, 6.1, 2.9, 3.6, 3.5],   # Diseno UX/UI
}


class Resultado:
    def __init__(self, filas):
        self.filas = filas

    def scalar(self):
        return self.filas[0][0] if self.filas else None

    def all(self):
        return self.filas


class BDFalsa:
    """Responde segun el texto de la consulta, o falla si se le pide."""

    def __init__(self, respuestas=None, falla_con=None):
        self.respuestas = respuestas or {}
        self.falla_con = falla_con
        self.consultas = []
        self.deshechas = 0

    def execute(self, sentencia, parametros=None):
        sql = str(sentencia)
        self.consultas.append((sql, parametros))
        if self.falla_con and self.falla_con in sql:
            raise OperationalError(sql, parametros, Exception("type vector does not exist"))
        for clave, filas in self.respuestas.items():
            if clave in sql:
                return Resultado(filas)
        return Resultado([])

    def rollback(self):
        self.deshechas += 1


@pytest.fixture(autouse=True)
def sin_cache():
    cv.olvidar_perfiles()
    yield
    cv.olvidar_perfiles()


class TestPerfilEsperado:
    def test_es_la_media_ponderada_por_la_probabilidad(self):
        perfil = ocupaciones.perfil_esperado({1: 0.75, 8: 0.25}, PERFILES)

        esperado = [0.75 * a + 0.25 * b for a, b in zip(PERFILES[1], PERFILES[8])]
        assert perfil == pytest.approx(esperado)

    def test_ignora_las_ramas_sin_perfil_y_renormaliza(self):
        # La rama 5 no tiene perfil cargado: su probabilidad no puede tirar
        # del resultado hacia cero.
        perfil = ocupaciones.perfil_esperado({1: 0.5, 5: 0.5}, PERFILES)

        assert perfil == pytest.approx(PERFILES[1])

    def test_sin_perfiles_no_hay_perfil(self):
        assert ocupaciones.perfil_esperado({1: 1.0}, {}) is None


class TestLiteralVector:
    def test_formato_que_entiende_pgvector(self):
        assert cv.literal_vector([0.5, 1, 0.25]) == "[0.5,1,0.25]"


class TestDistancia:
    def test_pregunta_a_la_funcion_con_las_diez_afinidades(self):
        bd = BDFalsa({"revo_distancia_al_entrenamiento": [(0.31,)]})

        distancia = cv.distancia_al_entrenamiento(bd, [0.1] * 10)

        sql, parametros = bd.consultas[0]
        assert distancia == pytest.approx(0.31)
        assert parametros["perfil"].count(",") == 9
        assert parametros["k"] == 10

    def test_si_pgvector_falla_no_rompe_y_deshace_la_transaccion(self):
        # Sin el rollback, la sesion queda en "current transaction is
        # aborted" y cualquier consulta posterior del mismo request falla.
        bd = BDFalsa(falla_con="revo_distancia_al_entrenamiento")

        assert cv.distancia_al_entrenamiento(bd, [0.1] * 10) is None
        assert bd.deshechas == 1


class TestOcupacionesAfines:
    def test_devuelve_codigo_titulo_y_correlacion(self):
        bd = BDFalsa({"revo_ocupaciones_afines": [
            ("15-1252.00", "Software Developers", 0.991),
            ("15-1251.00", "Computer Programmers", 0.985),
        ]})

        afines = cv.ocupaciones_afines(bd, PERFILES[1])

        assert afines[0] == {"codigo_soc": "15-1252.00",
                             "titulo": "Software Developers", "correlacion": 0.991}
        assert len(afines) == 2

    def test_sin_perfil_no_consulta(self):
        bd = BDFalsa()

        assert cv.ocupaciones_afines(bd, None) == []
        assert bd.consultas == []


class TestEnriquecer:
    RESULTADO = {
        "probabilidades_por_id": {1: 0.8, 4: 0.2},
        "vecindario_entrenamiento": {"k": 10, "percentil": 95, "umbral": 0.3},
    }

    def test_anade_vecindario_y_ocupaciones(self):
        bd = BDFalsa({
            "revo_distancia_al_entrenamiento": [(0.9,)],
            "FROM specializations": [(r, *p) for r, p in PERFILES.items()],
            "revo_ocupaciones_afines": [("15-1252.00", "Software Developers", 0.99)],
        })

        extra = cv.enriquecer(bd, {"aff_1": 0.9, "aff_4": 0.6}, self.RESULTADO)

        assert extra["vecindario"]["perfil_poco_visto"] is True
        assert extra["ocupaciones_afines"][0]["codigo_soc"] == "15-1252.00"

    def test_una_afinidad_ausente_vale_cero_como_en_el_modelo(self):
        bd = BDFalsa({"revo_distancia_al_entrenamiento": [(0.1,)]})

        cv.enriquecer(bd, {"aff_1": 0.9}, self.RESULTADO)

        perfil = bd.consultas[0][1]["perfil"]
        assert perfil == "[0.9,0,0,0,0,0,0,0,0,0]"

    def test_sin_pgvector_la_prediccion_sigue_y_lo_dice(self):
        bd = BDFalsa(falla_con="revo_")

        extra = cv.enriquecer(bd, {"aff_1": 0.9}, self.RESULTADO)

        assert extra["vecindario"]["disponible"] is False
        assert extra["ocupaciones_afines"] == []
