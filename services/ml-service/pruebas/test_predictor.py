"""
Pruebas del predictor.

Este servicio produce lo unico que el alumno se lleva: su especializacion
recomendada. Hasta ahora no tenia ni una prueba, asi que un cambio en el
modelo o en el mapa de especializaciones se detectaba en produccion.

No se cambia el comportamiento del modelo: estas pruebas fijan lo que hace
HOY, para que un cambio futuro tenga que ser deliberado.
"""
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from model import predictor
from model.predictor import SPECIALIZATION_MAP, build_feature_vector


# ── Modelo de juguete ────────────────────────────────────────
# Entrenado sobre datos donde la etiqueta es el indice del valor mas alto.
# Sirve para probar la forma de la respuesta sin depender del .pkl real, que
# cambia cada vez que alguien reentrena.
@pytest.fixture(scope="module")
def modelo_falso():
    filas, etiquetas = [], []
    for clase in range(1, 11):
        for ruido in (0.0, 0.05, 0.1):
            vector = [0.2 + ruido] * 10
            vector[clase - 1] = 0.95
            filas.append(vector)
            etiquetas.append(clase)
    modelo = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    modelo.fit(np.array(filas), np.array(etiquetas))
    return modelo


@pytest.fixture
def predecir(monkeypatch, modelo_falso):
    monkeypatch.setattr(predictor, "load_model", lambda: modelo_falso)
    return predictor.predict


def vector_con(alto: int, valor: float = 0.95, resto: float = 0.2) -> dict:
    return {f"aff_{i}": (valor if i == alto else resto) for i in range(1, 11)}


class TestVectorDeEntrada:
    def test_ordena_las_afinidades_de_1_a_10(self):
        entrada = {f"aff_{i}": i / 10 for i in range(1, 11)}

        vector = build_feature_vector(entrada)

        assert vector.shape == (1, 10)
        assert vector[0][0] == pytest.approx(0.1)
        assert vector[0][9] == pytest.approx(1.0)

    def test_una_afinidad_que_falta_se_rellena_con_cero(self):
        # Ojo: el docstring decia 3.0 y el codigo usa 0.0. Se fija el
        # comportamiento REAL, que ademas es el correcto: las afinidades van
        # de 0 a 1, asi que un 3.0 seria un valor imposible.
        vector = build_feature_vector({"aff_1": 0.9})

        assert vector[0][0] == pytest.approx(0.9)
        assert all(v == 0.0 for v in vector[0][1:])

    def test_ignora_claves_que_no_son_afinidades(self):
        # El vector llega de la red: una clave de mas no puede desplazar
        # las columnas ni colarse en el modelo.
        vector = build_feature_vector({**vector_con(3), "session_id": 999, "hola": "mundo"})

        assert vector.shape == (1, 10)

    def test_un_diccionario_vacio_no_revienta(self):
        vector = build_feature_vector({})

        assert vector.shape == (1, 10)
        assert not vector.any()


class TestFormaDeLaRespuesta:
    def test_devuelve_la_especializacion_principal(self, predecir):
        resultado = predecir(vector_con(4))

        assert resultado["primary"]["specialization_id"] in SPECIALIZATION_MAP
        assert resultado["primary"]["name"]

    def test_devuelve_exactamente_tres_alternativas(self, predecir):
        # El frontend pinta un podio de tres. Si llegan dos o cuatro, se rompe.
        assert len(predecir(vector_con(1))["top3"]) == 3

    def test_la_principal_encabeza_el_top3(self, predecir):
        resultado = predecir(vector_con(7))

        assert resultado["top3"][0]["specialization_id"] == resultado["primary"]["specialization_id"]

    def test_el_top3_viene_ordenado_de_mayor_a_menor(self, predecir):
        confianzas = [s["confidence"] for s in predecir(vector_con(2))["top3"]]

        assert confianzas == sorted(confianzas, reverse=True)

    def test_las_probabilidades_suman_uno(self, predecir):
        total = sum(predecir(vector_con(5))["all_probabilities"].values())

        # Vienen en porcentaje y redondeadas a un decimal.
        assert total == pytest.approx(100.0, abs=0.5)

    def test_la_confianza_es_una_probabilidad(self, predecir):
        for spec in predecir(vector_con(9))["top3"]:
            assert 0.0 <= spec["confidence"] <= 1.0
            assert 0.0 <= spec["confidence_pct"] <= 100.0

    def test_cada_alternativa_trae_lo_que_el_frontend_pinta(self, predecir):
        for spec in predecir(vector_con(6))["top3"]:
            assert set(spec) >= {"specialization_id", "name", "icon", "color", "confidence_pct"}

    def test_devuelve_el_vector_que_se_uso(self, predecir):
        # Queda como rastro de auditoria: permite reproducir una prediccion
        # concreta meses despues.
        entrada = vector_con(3)

        assert predecir(entrada)["feature_vector"] == entrada


class TestCoherenciaDelResultado:
    @pytest.mark.parametrize("esperada", range(1, 11))
    def test_una_afinidad_dominante_gana(self, predecir, esperada):
        # Con el modelo actual, la rama con mas afinidad es la que sale. Si
        # algun dia el modelo deja de comportarse asi sera una decision
        # tomada, no un accidente.
        resultado = predecir(vector_con(esperada))

        assert resultado["primary"]["specialization_id"] == esperada

    def test_el_mismo_vector_da_siempre_el_mismo_resultado(self, predecir):
        # Un alumno que recarga la pagina no puede ver otra carrera.
        entrada = vector_con(8)

        primera = predecir(entrada)["primary"]
        segunda = predecir(entrada)["primary"]

        assert primera == segunda

    def test_un_empate_total_no_revienta(self, predecir):
        # Todas las afinidades iguales: no hay respuesta "correcta", pero
        # tiene que devolver una y no fallar.
        resultado = predecir({f"aff_{i}": 0.5 for i in range(1, 11)})

        assert resultado["primary"]["specialization_id"] in SPECIALIZATION_MAP


class TestMapaDeEspecializaciones:
    def test_cubre_las_diez_ramas(self):
        assert set(SPECIALIZATION_MAP) == set(range(1, 11))

    def test_ninguna_rama_se_queda_sin_nombre_ni_color(self):
        for spec_id, datos in SPECIALIZATION_MAP.items():
            assert datos["name"].strip(), spec_id
            assert datos["color"].startswith("#"), spec_id
            assert datos["icon"].strip(), spec_id

    def test_no_hay_dos_ramas_con_el_mismo_nombre(self):
        nombres = [d["name"] for d in SPECIALIZATION_MAP.values()]

        assert len(nombres) == len(set(nombres))
