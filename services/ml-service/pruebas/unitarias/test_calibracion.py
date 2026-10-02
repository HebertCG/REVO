"""
Pruebas de la calibracion de probabilidades.

Lo que se comprueba aqui no es que el codigo corra: es que la temperatura
HACE lo que dice hacer. Una calibracion que se ejecuta sin fallar pero no
mejora nada es peor que no tenerla, porque da una falsa sensacion de rigor.

La prueba central es `test_calibrar_un_modelo_sobreseguro_baja_el_ece`: si
esa falla, todo lo que el sistema diga sobre su confianza es mentira.
"""
import numpy as np
import pytest

from model import calibracion


def logits_sobreseguros(n=400, n_clases=10, semilla=0):
    """
    Logits de un modelo que acierta el ~60 % pero declara casi el 100 %.

    Es el caso real del proyecto: entrenado sobre datos sinteticos separables
    y con class_weight='balanced', el modelo sale convencidisimo de todo.
    """
    generador = np.random.default_rng(semilla)
    y = generador.integers(0, n_clases, size=n)
    logits = generador.normal(0, 1, size=(n, n_clases))

    for i, verdadera in enumerate(y):
        # El 60 % de las veces el pico enorme va a la clase correcta; el
        # resto, a otra. Asi el modelo esta siempre seguro y acierta el 60 %.
        destino = verdadera if generador.random() < 0.6 else (verdadera + 1) % n_clases
        logits[i, destino] += 12.0

    return logits, y


class TestAjusteDeTemperatura:
    def test_un_modelo_sobreseguro_pide_temperatura_mayor_que_uno(self):
        # T > 1 aplana la distribucion. Es la direccion correcta cuando el
        # modelo declara mas confianza de la que merece.
        logits, y = logits_sobreseguros()

        t = calibracion.ajustar_temperatura(logits, y)

        assert t > 1.0

    def test_con_pocas_muestras_no_calibra(self):
        # Con pocos datos la temperatura ajusta ruido. Devolver 1.0 (no tocar
        # nada) es la respuesta correcta, no un fallo.
        logits, y = logits_sobreseguros(n=20)

        assert calibracion.ajustar_temperatura(logits, y) == 1.0

    def test_la_temperatura_se_queda_dentro_del_rango(self):
        logits, y = logits_sobreseguros()

        t = calibracion.ajustar_temperatura(logits, y)

        assert calibracion.T_MINIMA <= t <= calibracion.T_MAXIMA


class TestEfectoDeCalibrar:
    def test_calibrar_un_modelo_sobreseguro_baja_el_ece(self):
        # LA PRUEBA QUE IMPORTA. Si esto no se cumple, el porcentaje que ve
        # el alumno sigue siendo una mentira con formato de dato.
        logits, y = logits_sobreseguros()
        t = calibracion.ajustar_temperatura(logits, y)

        antes = calibracion.ece(calibracion.aplicar_temperatura(logits, 1.0), y)
        despues = calibracion.ece(calibracion.aplicar_temperatura(logits, t), y)

        assert despues < antes

    def test_calibrar_no_cambia_que_clase_se_predice(self):
        # La temperatura es monotona: divide todos los logits por lo mismo.
        # Si cambiara el argmax, estaria cambiando el diagnostico del alumno
        # y no solo su confianza, que seria un efecto inaceptable.
        logits, y = logits_sobreseguros()
        t = calibracion.ajustar_temperatura(logits, y)

        sin_calibrar = calibracion.aplicar_temperatura(logits, 1.0).argmax(axis=1)
        calibrado = calibracion.aplicar_temperatura(logits, t).argmax(axis=1)

        assert np.array_equal(sin_calibrar, calibrado)

    def test_la_confianza_media_se_acerca_al_acierto_real(self):
        logits, y = logits_sobreseguros()
        t = calibracion.ajustar_temperatura(logits, y)
        probabilidades = calibracion.aplicar_temperatura(logits, t)

        confianza = probabilidades.max(axis=1).mean()
        acierto = (probabilidades.argmax(axis=1) == y).mean()

        assert abs(confianza - acierto) < 0.15


class TestEstabilidadNumerica:
    def test_logits_enormes_no_producen_nan(self):
        # Sin restar el maximo antes del exp, esto desborda y devuelve NaN en
        # silencio: las probabilidades salen NaN y el argmax cae siempre en
        # la clase 0 sin que nada falle de forma visible.
        logits = np.array([[1000.0, 999.0, 998.0]])

        p = calibracion.aplicar_temperatura(logits, 1.0)

        assert np.isfinite(p).all()
        assert p.sum() == pytest.approx(1.0)

    def test_las_probabilidades_suman_uno(self):
        logits, _ = logits_sobreseguros(n=50)

        p = calibracion.aplicar_temperatura(logits, 2.5)

        assert np.allclose(p.sum(axis=1), 1.0)

    def test_una_temperatura_no_positiva_falla_con_un_mensaje_util(self):
        with pytest.raises(ValueError, match="positiva"):
            calibracion.aplicar_temperatura(np.zeros((1, 3)), 0.0)


class TestMetricas:
    def test_un_modelo_perfecto_y_seguro_tiene_ece_cero(self):
        # Acierta siempre y dice estar seguro siempre: esta calibrado.
        probabilidades = np.zeros((100, 5))
        probabilidades[:, 0] = 1.0
        y = np.zeros(100, dtype=int)

        assert calibracion.ece(probabilidades, y) == pytest.approx(0.0, abs=1e-9)

    def test_un_modelo_seguro_que_siempre_falla_tiene_ece_maximo(self):
        probabilidades = np.zeros((100, 5))
        probabilidades[:, 0] = 1.0
        y = np.ones(100, dtype=int)

        assert calibracion.ece(probabilidades, y) == pytest.approx(1.0, abs=1e-9)

    def test_el_brier_penaliza_al_que_siempre_duda(self):
        # El ECE de un modelo que reparte por igual puede salir bueno. El
        # Brier no: por eso se reportan los dos.
        n, k = 100, 5
        y = np.zeros(n, dtype=int)
        seguro_y_correcto = np.zeros((n, k)); seguro_y_correcto[:, 0] = 1.0
        siempre_dudando = np.full((n, k), 1 / k)

        assert (calibracion.brier_multiclase(siempre_dudando, y)
                > calibracion.brier_multiclase(seguro_y_correcto, y))

    def test_el_mce_es_mayor_o_igual_que_el_ece(self):
        # El maximo por particion no puede ser menor que la media ponderada.
        logits, y = logits_sobreseguros()
        p = calibracion.aplicar_temperatura(logits, 1.0)

        assert calibracion.mce(p, y) >= calibracion.ece(p, y) - 1e-9


class TestInforme:
    def test_avisa_de_la_circularidad_con_datos_sinteticos(self):
        # Es la advertencia que impide citar el ECE como si dijera algo sobre
        # alumnos reales. Que viaje pegada a las cifras es el punto.
        logits, y = logits_sobreseguros()

        informe = calibracion.evaluar_calibracion(logits, y, 2.0, datos_sinteticos=True)

        assert any("CIRCULAR" in aviso for aviso in informe["avisos"])

    def test_sin_datos_sinteticos_no_mete_ese_aviso(self):
        logits, y = logits_sobreseguros()

        informe = calibracion.evaluar_calibracion(logits, y, 2.0, datos_sinteticos=False)

        assert not any("CIRCULAR" in aviso for aviso in informe["avisos"])

    def test_avisa_cuando_faltan_muestras(self):
        logits, y = logits_sobreseguros(n=20)

        informe = calibracion.evaluar_calibracion(logits, y, 1.0)

        assert informe["suficientes_muestras"] is False
        assert any("muestras" in aviso for aviso in informe["avisos"])

    def test_el_diagrama_de_fiabilidad_cubre_todas_las_muestras(self):
        logits, y = logits_sobreseguros(n=200)
        p = calibracion.aplicar_temperatura(logits, 1.5)

        puntos = calibracion.diagrama_fiabilidad(p, y)

        assert sum(punto["n"] for punto in puntos) == 200
