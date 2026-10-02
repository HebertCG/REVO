"""
Pruebas del vecindario: cuanto se parece un alumno a lo que el modelo vio.

Se prueba la parte que no necesita base de datos: el calculo del umbral al
entrenar y la lectura de una distancia. La consulta a pgvector se prueba en
test_consultas_vectoriales.py con una base falsa, y contra PostgreSQL real
con la verificacion de la migracion 36.
"""
import numpy as np
import pytest

from model import vecinos


def nube(n: int, centro: float = 0.5, dispersion: float = 0.05, semilla: int = 0) -> np.ndarray:
    """n alumnos con afinidades parecidas entre si."""
    generador = np.random.default_rng(semilla)
    return np.clip(generador.normal(centro, dispersion, size=(n, 10)), 0, 1)


class TestDistanciasAVecinos:
    def test_un_punto_no_cuenta_como_su_propio_vecino(self):
        # Si se contara, la distancia minima seria siempre 0 y el umbral
        # quedaria artificialmente bajo: todo alumno nuevo pareceria raro.
        X = np.array([[0.0] * 10, [1.0] * 10])

        distancias = vecinos.distancias_medias_a_vecinos(X, k=1)

        assert distancias == pytest.approx([np.sqrt(10), np.sqrt(10)])

    def test_coincide_con_el_calculo_por_fuerza_bruta(self):
        X = nube(40, semilla=3)

        rapido = vecinos.distancias_medias_a_vecinos(X, k=5)

        lento = []
        for i, fila in enumerate(X):
            d = sorted(np.linalg.norm(X[j] - fila) for j in range(len(X)) if j != i)
            lento.append(np.mean(d[:5]))
        assert rapido == pytest.approx(lento, abs=1e-9)


class TestUmbral:
    def test_describe_el_percentil_de_las_distancias(self):
        X = nube(200)

        informe = vecinos.calcular_umbral(X)

        esperado = np.percentile(
            vecinos.distancias_medias_a_vecinos(X, vecinos.K_VECINOS),
            vecinos.PERCENTIL_UMBRAL)
        assert informe["umbral"] == pytest.approx(esperado, abs=1e-6)
        assert informe["k"] == vecinos.K_VECINOS
        assert informe["muestras"] == 200

    def test_sin_datos_suficientes_no_inventa_un_umbral(self):
        # Con menos filas que vecinos, "los 10 mas parecidos" no existe.
        assert vecinos.calcular_umbral(nube(vecinos.K_VECINOS)) is None

    def test_con_muchos_datos_submuestrea_de_forma_reproducible(self):
        # La matriz de distancias es n x n: sin tope, 50 000 filas serian
        # 20 GB de memoria.
        X = nube(vecinos.MUESTRA_MAXIMA + 300, semilla=7)

        a = vecinos.calcular_umbral(X)
        b = vecinos.calcular_umbral(X)

        assert a["muestras"] == vecinos.MUESTRA_MAXIMA
        assert a["umbral"] == b["umbral"]


class TestEvaluar:
    INFORME = {"k": 10, "percentil": 95, "umbral": 0.30, "muestras": 900}

    def test_un_alumno_lejos_de_todos_es_un_perfil_poco_visto(self):
        resultado = vecinos.evaluar(0.80, self.INFORME)

        assert resultado["perfil_poco_visto"] is True
        assert resultado["disponible"] is True

    def test_un_alumno_como_los_demas_no_lo_es(self):
        assert vecinos.evaluar(0.12, self.INFORME)["perfil_poco_visto"] is False

    def test_sin_distancia_lo_dice_en_vez_de_inventar(self):
        # pgvector no disponible, o la consulta fallo: no es "perfil normal",
        # es "no se sabe".
        resultado = vecinos.evaluar(None, self.INFORME)

        assert resultado["disponible"] is False
        assert resultado["perfil_poco_visto"] is None

    def test_un_modelo_antiguo_sin_umbral_da_la_distancia_sin_veredicto(self):
        resultado = vecinos.evaluar(0.5, None)

        assert resultado["distancia_media"] == 0.5
        assert resultado["perfil_poco_visto"] is None
