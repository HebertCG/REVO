"""
Pruebas de los conjuntos de prediccion conformales.

La prueba que justifica todo el modulo es `test_la_cobertura_real_cumple_la_
garantia`: la prediccion conformal se vende como "cobertura garantizada", y
si la cobertura empirica no sale, la garantia es una afirmacion sin respaldo.

Se comprueba con datos donde las clases se solapan de verdad, no separables:
sobre datos separables cualquier metodo cubre el 100 % y la prueba no
distinguiria un umbral correcto de uno roto.
"""
import numpy as np
import pytest

from model import conformal


def probabilidades_realistas(n=1200, n_clases=10, semilla=7):
    """
    Genera probabilidades y etiquetas con solapamiento real.

    La etiqueta se muestrea DE la distribucion, asi que el modelo esta bien
    especificado pero es genuinamente incierto: unas veces acierta el top-1 y
    otras la verdadera cae en el puesto 3 o 4. Es el regimen donde los
    conjuntos conformales tienen sentido.
    """
    generador = np.random.default_rng(semilla)
    logits = generador.normal(0, 1.4, size=(n, n_clases))
    exp = np.exp(logits - logits.max(axis=1, keepdims=True))
    probabilidades = exp / exp.sum(axis=1, keepdims=True)

    y = np.array([generador.choice(n_clases, p=fila) for fila in probabilidades])
    return probabilidades, y


class TestUmbral:
    def test_la_cobertura_real_cumple_la_garantia(self):
        # LA PRUEBA QUE IMPORTA. Se ajusta el umbral en una mitad y se mide
        # la cobertura en la otra: si el 90 % nominal no se alcanza, la
        # palabra "garantizada" no se puede usar.
        p, y = probabilidades_realistas()
        mitad = len(y) // 2

        umbral = conformal.ajustar_umbral(p[:mitad], y[:mitad], alpha=0.10)
        evaluacion = conformal.evaluar_cobertura(p[mitad:], y[mitad:], umbral["q"])

        # Margen de 3 puntos por el ruido de muestreo con n=600.
        assert evaluacion["cobertura_real"] >= 0.87

    def test_menos_alpha_produce_mas_cobertura(self):
        # Pedir mas seguridad tiene que dar conjuntos que cubren mas. Si no,
        # el parametro no esta haciendo nada.
        p, y = probabilidades_realistas()
        mitad = len(y) // 2

        exigente = conformal.ajustar_umbral(p[:mitad], y[:mitad], alpha=0.05)
        laxo = conformal.ajustar_umbral(p[:mitad], y[:mitad], alpha=0.30)

        cob_exigente = conformal.evaluar_cobertura(p[mitad:], y[mitad:], exigente["q"])
        cob_laxo = conformal.evaluar_cobertura(p[mitad:], y[mitad:], laxo["q"])

        assert cob_exigente["cobertura_real"] > cob_laxo["cobertura_real"]
        assert cob_exigente["tamano_medio"] > cob_laxo["tamano_medio"]

    def test_aleatorizar_evita_sobrecubrir(self):
        # Sin aleatorizar, APS sobre-cubre: medido en este proyecto, una
        # cobertura objetivo del 90 % daba el 100 % real. No es incorrecto,
        # pero devuelve conjuntos mas grandes de lo que los datos justifican,
        # y en pantalla eso es decirle "encajas en varias ramas" a alumnos
        # cuyo perfil si estaba definido.
        p, y = probabilidades_realistas()
        mitad = len(y) // 2

        sin = conformal.ajustar_umbral(p[:mitad], y[:mitad], aleatorizar=False)
        con = conformal.ajustar_umbral(p[:mitad], y[:mitad], aleatorizar=True)

        ev_sin = conformal.evaluar_cobertura(p[mitad:], y[mitad:], sin["q"])
        ev_con = conformal.evaluar_cobertura(p[mitad:], y[mitad:], con["q"])

        # El conjunto aleatorizado es mas ajustado...
        assert ev_con["tamano_medio"] < ev_sin["tamano_medio"]
        # ...sin perder la garantia.
        assert ev_con["cobertura_real"] >= 0.87

    def test_con_pocas_muestras_avisa_en_vez_de_inventar_una_garantia(self):
        p, y = probabilidades_realistas(n=30)

        umbral = conformal.ajustar_umbral(p, y)

        assert umbral["suficientes_muestras"] is False
        assert umbral["q"] == 1.0
        assert "aviso" in umbral


class TestConjunto:
    def test_nunca_devuelve_un_conjunto_vacio(self):
        # Un conjunto vacio no es una respuesta que se pueda poner en
        # pantalla. Incluso con q=0 tiene que salir al menos una rama.
        p = np.array([0.5, 0.3, 0.2])

        assert len(conformal.conjunto_prediccion(p, 0.0)) >= 1

    def test_viene_ordenado_de_mayor_a_menor_probabilidad(self):
        p = np.array([0.1, 0.5, 0.2, 0.2])

        conjunto = conformal.conjunto_prediccion(p, 0.9)

        assert conjunto[0] == 1  # el indice de 0.5

    def test_un_umbral_de_uno_devuelve_todas_las_clases(self):
        p = np.array([0.4, 0.3, 0.2, 0.1])

        assert len(conformal.conjunto_prediccion(p, 1.0)) == 4

    def test_un_perfil_claro_produce_un_conjunto_pequeno(self):
        seguro = np.array([0.97, 0.01, 0.01, 0.005, 0.005])
        repartido = np.array([0.25, 0.25, 0.2, 0.15, 0.15])

        assert (len(conformal.conjunto_prediccion(seguro, 0.9))
                < len(conformal.conjunto_prediccion(repartido, 0.9)))


class TestPuntuaciones:
    def test_la_clase_bien_colocada_puntua_bajo(self):
        # La puntuacion es la masa acumulada hasta la verdadera: si estaba la
        # primera, es su propia probabilidad; si la ultima, casi 1.
        p = np.array([[0.8, 0.1, 0.1], [0.1, 0.1, 0.8]])
        y = np.array([0, 0])  # acertada en la 1a fila, mal colocada en la 2a

        puntuaciones = conformal.puntuaciones_aps(p, y)

        assert puntuaciones[0] < puntuaciones[1]

    def test_la_puntuacion_es_una_probabilidad_acumulada(self):
        p, y = probabilidades_realistas(n=100)

        puntuaciones = conformal.puntuaciones_aps(p, y)

        assert ((puntuaciones > 0) & (puntuaciones <= 1.0 + 1e-9)).all()


class TestPresentacion:
    def test_una_sola_rama_se_presenta_como_resultado_claro(self):
        assert conformal.decidir_presentacion([3])["modo"] == "resultado_unico"

    def test_dos_o_tres_ramas_se_presentan_como_compatibles(self):
        assert conformal.decidir_presentacion([3, 1])["modo"] == "varias_compatibles"
        assert conformal.decidir_presentacion([3, 1, 7])["modo"] == "varias_compatibles"

    def test_mas_de_tres_admite_que_no_hay_informacion_suficiente(self):
        # Es el caso que antes no existia: el sistema devolvia tres ramas
        # inventando una precision que no tenia.
        decision = conformal.decidir_presentacion([3, 1, 7, 2, 9])

        assert decision["modo"] == "insuficiente"
        assert decision["mostrar_n"] == conformal.MAXIMO_PARA_MOSTRAR

    def test_toda_presentacion_trae_un_mensaje_para_el_alumno(self):
        for conjunto in ([1], [1, 2], [1, 2, 3], [1, 2, 3, 4, 5]):
            decision = conformal.decidir_presentacion(conjunto)
            assert decision["mensaje"]
            assert decision["mostrar_n"] >= 1


class TestPresentacionConCautela:
    """
    Con un perfil poco visto, la pantalla no puede decir "tus respuestas
    apuntan claramente a una rama": seria afirmar una certeza que el propio
    sistema acaba de poner en duda. Pasaba tambien antes del vecindario,
    cuando quien lo detectaba era el conjunto bootstrap.
    """

    def test_un_resultado_unico_poco_visto_pide_cautela(self):
        from model import conformal
        presentacion = conformal.decidir_presentacion([4])

        ajustada = conformal.ajustar_por_lectura(
            presentacion, {"lectura": "perfil_poco_visto"})

        assert ajustada["cautela"] is True
        assert "claramente" not in ajustada["mensaje"]
        assert ajustada["mostrar_n"] == 1          # la rama no cambia

    def test_una_lectura_normal_no_se_toca(self):
        from model import conformal
        presentacion = conformal.decidir_presentacion([4])

        ajustada = conformal.ajustar_por_lectura(presentacion, {"lectura": "definido"})

        assert ajustada == {**presentacion, "cautela": False}
