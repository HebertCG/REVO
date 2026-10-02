"""
Pruebas de la separacion entre los dos tipos de incertidumbre.

La afirmacion que hay que sostener es que el sistema distingue "encajas en
dos ramas" de "nunca vimos a nadie como tu". Son dos situaciones que piden
respuestas opuestas: en la primera mas preguntas no ayudan, en la segunda el
porcentaje no vale nada.

La prueba central es `test_un_perfil_lejano_produce_mas_desacuerdo`: si el
conjunto bootstrap no discrepa mas fuera del soporte de los datos, la medida
epistemica no esta midiendo nada.
"""
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from model import incertidumbre


@pytest.fixture(scope="module")
def datos_agrupados():
    """Tres grupos bien separados en un rincon del espacio de 10 afinidades."""
    generador = np.random.default_rng(3)
    X, y = [], []
    for clase in (1, 2, 3):
        for _ in range(40):
            vector = generador.uniform(0.0, 0.2, 10)
            vector[clase - 1] = generador.uniform(0.8, 1.0)
            X.append(vector)
            y.append(clase)
    return np.array(X), np.array(y)


class TestIncertidumbreAleatoria:
    def test_la_certeza_total_da_entropia_cero(self):
        assert incertidumbre.entropia_normalizada(
            np.array([1.0, 0.0, 0.0, 0.0])) == pytest.approx(0.0)

    def test_el_reparto_uniforme_da_entropia_uno(self):
        # Normalizada: 1.0 es "ni idea", independientemente del numero de
        # clases. Sin normalizar habria que saber que el maximo son 3.32 bits.
        assert incertidumbre.entropia_normalizada(
            np.full(10, 0.1)) == pytest.approx(1.0)

    def test_el_margen_detecta_un_empate(self):
        assert incertidumbre.margen(np.array([0.5, 0.5, 0.0])) == pytest.approx(0.0)
        assert incertidumbre.margen(np.array([0.9, 0.05, 0.05])) == pytest.approx(0.85)

    def test_el_margen_del_tercero_al_cuarto_es_el_que_mira_el_producto(self):
        # El producto entrega un TOP-3, asi que la frontera que decide lo que
        # el alumno ve es la del puesto 3, no la del 1. Este caso lo ilustra:
        # top-1 clarisimo y empate caotico justo en el corte del top-3.
        p = np.array([0.60, 0.13, 0.09, 0.09, 0.09])

        assert incertidumbre.margen(p) > 0.4          # el 1o esta despejado
        assert incertidumbre.margen_en(p, 3) < 0.01   # el corte del 3o no

    def test_una_sola_clase_no_revienta(self):
        assert incertidumbre.entropia_normalizada(np.array([1.0])) == 0.0
        assert incertidumbre.margen(np.array([1.0])) == 1.0


class TestConjuntoBootstrap:
    def test_entrena_el_numero_de_modelos_pedido(self, datos_agrupados):
        X, y = datos_agrupados

        modelos = incertidumbre.entrenar_conjunto(
            LogisticRegression(max_iter=500), X, y, n_modelos=8)

        assert len(modelos) == 8

    def test_todos_los_modelos_conocen_todas_las_clases(self, datos_agrupados):
        # Un remuestreo que pierde una clase produce un modelo que nunca
        # puede predecirla, y eso sesga el desacuerdo hacia abajo justo en
        # esa clase. Se descartan a proposito.
        X, y = datos_agrupados

        modelos = incertidumbre.entrenar_conjunto(
            LogisticRegression(max_iter=500), X, y, n_modelos=6)

        for modelo in modelos:
            assert set(modelo.classes_) == set(np.unique(y))

    def test_un_perfil_lejano_produce_mas_desacuerdo(self, datos_agrupados):
        # LA PRUEBA QUE IMPORTA. Si el desacuerdo no sube fuera del soporte,
        # la incertidumbre epistemica no esta midiendo nada y la etiqueta
        # "perfil poco visto" seria decorativa.
        X, y = datos_agrupados
        modelos = incertidumbre.entrenar_conjunto(
            LogisticRegression(max_iter=500), X, y, n_modelos=25)

        dentro = X[0]                      # un perfil como los vistos
        fuera = np.full(10, 0.55)          # todo a medias: nunca se vio

        assert (incertidumbre.desacuerdo(modelos, fuera)
                > incertidumbre.desacuerdo(modelos, dentro))

    def test_sin_modelos_el_desacuerdo_es_cero(self):
        assert incertidumbre.desacuerdo([], np.zeros(10)) == 0.0

    def test_la_media_del_conjunto_es_una_distribucion(self, datos_agrupados):
        X, y = datos_agrupados
        modelos = incertidumbre.entrenar_conjunto(
            LogisticRegression(max_iter=500), X, y, n_modelos=5)

        media = incertidumbre.probabilidad_media(modelos, X[0])

        assert media.sum() == pytest.approx(1.0)


class TestDiagnostico:
    def test_un_perfil_definido_se_lee_como_definido(self):
        p = np.array([0.90, 0.04, 0.02, 0.02, 0.01, 0.01, 0.0, 0.0, 0.0, 0.0])

        assert incertidumbre.diagnosticar(p)["lectura"] == "definido"

    def test_un_reparto_plano_se_lee_como_varias_ramas(self):
        assert incertidumbre.diagnosticar(np.full(10, 0.1))["lectura"] == "encaja_en_varias"

    def test_el_desacuerdo_alto_manda_sobre_el_resto(self):
        # Un perfil fuera de lo visto describe una extrapolacion: aunque las
        # probabilidades parezcan decididas, esa lectura va primero.
        p = np.array([0.90, 0.04, 0.02, 0.02, 0.01, 0.01, 0.0, 0.0, 0.0, 0.0])

        diagnostico = incertidumbre.diagnosticar(p, desacuerdo_valor=0.40)

        assert diagnostico["lectura"] == "perfil_poco_visto"
        assert diagnostico["incertidumbre_epistemica_alta"] is True

    def test_siempre_trae_las_cifras_que_generaron_la_lectura(self):
        # Una etiqueta sin el numero que la produjo no es auditable, y el
        # panel de administracion necesita los dos.
        diagnostico = incertidumbre.diagnosticar(np.full(10, 0.1), 0.1)

        for clave in ("entropia_normalizada", "margen_top1_top2",
                      "margen_top3_top4", "desacuerdo_conjunto"):
            assert clave in diagnostico

    def test_sin_conjunto_el_desacuerdo_queda_a_nulo_y_no_a_cero(self):
        # Cero significaria "los modelos coinciden del todo", que es una
        # medida. None significa "no se midio". No son lo mismo.
        assert incertidumbre.diagnosticar(np.full(10, 0.1))["desacuerdo_conjunto"] is None


class TestVecindarioEnLaLectura:
    """
    CASO REAL, prediccion 296: 99,9 % de confianza, conjunto conformal de una
    rama, y los 30 modelos bootstrap de acuerdo (desacuerdo 0,005). Pero el
    alumno estaba a 0,79 de sus vecinos con un umbral de 0,60.

    Los 30 modelos son regresiones logisticas: lejos de las fronteras de
    decision todas extrapolan igual y "coinciden" aunque nadie haya visto ese
    perfil. La distancia a los vecinos no tiene ese punto ciego.
    """

    DEFINIDO = {"lectura": "definido", "explicacion": "Tus respuestas apuntan...",
                "incertidumbre_epistemica_alta": False, "incertidumbre_aleatoria_alta": False}

    def test_el_vecindario_convierte_la_lectura_en_perfil_poco_visto(self):
        from model import incertidumbre

        nuevo = incertidumbre.incorporar_vecindario(
            self.DEFINIDO, {"perfil_poco_visto": True})

        assert nuevo["lectura"] == "perfil_poco_visto"
        assert nuevo["incertidumbre_epistemica_alta"] is True
        assert nuevo["fuentes_epistemicas"] == ["vecindario"]
        assert nuevo["explicacion"] == incertidumbre.EXPLICACION_POCO_VISTO

    def test_no_modifica_el_diagnostico_original(self):
        from model import incertidumbre
        original = dict(self.DEFINIDO)

        incertidumbre.incorporar_vecindario(self.DEFINIDO, {"perfil_poco_visto": True})

        assert self.DEFINIDO == original

    def test_un_vecindario_normal_no_cambia_nada(self):
        from model import incertidumbre

        nuevo = incertidumbre.incorporar_vecindario(
            self.DEFINIDO, {"perfil_poco_visto": False})

        assert nuevo["lectura"] == "definido"
        assert nuevo["fuentes_epistemicas"] == []

    def test_un_vecindario_no_disponible_no_se_toma_como_normal_ni_como_raro(self):
        from model import incertidumbre

        nuevo = incertidumbre.incorporar_vecindario(
            self.DEFINIDO, {"disponible": False, "perfil_poco_visto": None})

        assert nuevo["lectura"] == "definido"

    def test_si_las_dos_medidas_lo_detectan_constan_las_dos(self):
        from model import incertidumbre
        ya_raro = {**self.DEFINIDO, "lectura": "perfil_poco_visto",
                   "incertidumbre_epistemica_alta": True}

        nuevo = incertidumbre.incorporar_vecindario(ya_raro, {"perfil_poco_visto": True})

        assert nuevo["fuentes_epistemicas"] == ["conjunto", "vecindario"]
