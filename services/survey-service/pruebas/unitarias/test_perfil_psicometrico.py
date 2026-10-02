"""
Pruebas de la puntuacion RIASEC / Big Five y del encaje con las ramas.

Lo que se protege aqui es la FIDELIDAD A LOS MANUALES. Estos instrumentos
solo aportan algo sobre inventarse las preguntas si se puntuan como dicen
sus autores; una formula distinta rompe la comparabilidad con la literatura
publicada, que es lo unico que los justifica.

La prueba que mas importa es `test_un_perfil_artistico_encaja_con_ux_ui`: si
un perfil claramente artistico no acaba en Diseno UX/UI, el anclaje externo
no esta funcionando y toda la Fase 2 no sirve de nada.
"""
import json
import os

import pytest

from perfil_psicometrico import (
    BIG_FIVE,
    RIASEC,
    RespuestaInvalida,
    codigo_holland,
    correlacion,
    encaje_con_ramas,
    puntuar_bigfive,
    puntuar_riasec,
)

RUTA_PERFILES = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..", "database", "onet", "perfiles_ramas.json",
)


@pytest.fixture(scope="module")
def perfiles_ramas():
    if not os.path.exists(RUTA_PERFILES):
        pytest.skip("Falta database/onet/perfiles_ramas.json (generalo con mapeo_ramas_onet.py)")
    with open(RUTA_PERFILES, encoding="utf-8") as f:
        return json.load(f)


#: Los 30 items del Mini-IP: 5 por dimension, en el orden del manual.
ITEMS_RIASEC = {
    **{i: "R" for i in (1, 7, 13, 19, 25)},
    **{i: "I" for i in (2, 8, 14, 20, 26)},
    **{i: "A" for i in (3, 9, 15, 21, 27)},
    **{i: "S" for i in (4, 10, 16, 22, 28)},
    **{i: "E" for i in (5, 11, 17, 23, 29)},
    **{i: "C" for i in (6, 12, 18, 24, 30)},
}

#: Los 20 del Mini-IPIP: (factor, keyed).
ITEMS_BIGFIVE = {
    1: ("E", 1), 2: ("E", 1), 3: ("E", -1), 4: ("E", -1),
    5: ("A", 1), 6: ("A", 1), 7: ("A", -1), 8: ("A", -1),
    9: ("C", 1), 10: ("C", 1), 11: ("C", -1), 12: ("C", -1),
    13: ("N", 1), 14: ("N", 1), 15: ("N", -1), 16: ("N", -1),
    17: ("O", 1), 18: ("O", -1), 19: ("O", -1), 20: ("O", -1),
}


def respuestas_riasec(altas: str, valor_alto: int = 4, valor_bajo: int = 0) -> dict:
    """Responde alto en las dimensiones de `altas` y bajo en el resto."""
    return {
        item: (valor_alto if dim in altas else valor_bajo)
        for item, dim in ITEMS_RIASEC.items()
    }


class TestPuntuacionRIASEC:
    def test_la_puntuacion_de_cada_tipo_es_la_suma_de_sus_cinco_items(self):
        # Del manual: "Scores are computed by summing responses for each of
        # the six Holland types", rango 0..20 para el Mini.
        resultado = puntuar_riasec(respuestas_riasec("I"), ITEMS_RIASEC)

        assert resultado["perfil"]["I"] == 20   # 5 items x 4
        assert resultado["perfil"]["R"] == 0

    def test_el_rango_maximo_es_veinte(self):
        resultado = puntuar_riasec(respuestas_riasec("RIASEC"), ITEMS_RIASEC)

        assert all(v == 20 for v in resultado["perfil"].values())

    def test_responder_las_treinta_marca_el_perfil_como_completo(self):
        assert puntuar_riasec(respuestas_riasec("I"), ITEMS_RIASEC)["completo"] is True

    def test_responder_a_medias_lo_marca_como_incompleto(self):
        # Una dimension con 2 de 5 items no es comparable con otra que tiene
        # los 5, y sin esta marca nadie lo sabria despues.
        parciales = {i: 3 for i in list(ITEMS_RIASEC)[:12]}

        resultado = puntuar_riasec(parciales, ITEMS_RIASEC)

        assert resultado["completo"] is False
        assert resultado["n_respuestas"] == 12

    def test_un_valor_fuera_de_la_escala_falla_en_vez_de_recortarse(self):
        # Recortarlo en silencio esconde un error de quien llama hasta que
        # alguien analice los datos meses despues.
        with pytest.raises(RespuestaInvalida, match="Mini-IP usa"):
            puntuar_riasec({1: 7}, ITEMS_RIASEC)

    def test_un_item_que_no_es_del_instrumento_falla(self):
        with pytest.raises(RespuestaInvalida, match="no pertenece"):
            puntuar_riasec({999: 3}, ITEMS_RIASEC)


class TestCodigoHolland:
    def test_son_las_tres_dimensiones_mas_altas_en_orden(self):
        perfil = {"R": 5, "I": 20, "A": 2, "S": 1, "E": 3, "C": 15}

        assert codigo_holland(perfil) == "ICR"

    def test_los_empates_se_rompen_siempre_igual(self):
        # Un codigo que cambia entre dos ejecuciones con los mismos datos no
        # es un diagnostico. El desempate es el orden canonico R-I-A-S-E-C.
        perfil = dict.fromkeys(RIASEC, 10)

        assert codigo_holland(perfil) == codigo_holland(perfil) == "RIA"


class TestPuntuacionBigFive:
    def test_cada_factor_es_la_media_de_sus_cuatro_items(self):
        resultado = puntuar_bigfive({1: 5, 2: 5, 3: 1, 4: 1}, ITEMS_BIGFIVE)

        # Items 3 y 4 son inversos: 1 -> 5. Media de (5,5,5,5) = 5.0
        assert resultado["perfil"]["E"] == 5.0

    def test_los_items_inversos_se_invierten_sobre_seis(self):
        # 6 - valor, no 5 - valor: la escala es 1..5, asi que el espejo de 1
        # es 5. Con 5 - valor el espejo de 1 seria 4 y todo el factor se
        # desplazaria sin que nada fallara.
        directo = puntuar_bigfive({1: 5, 2: 5, 3: 5, 4: 5}, ITEMS_BIGFIVE)

        # (5 + 5 + 1 + 1) / 4 = 3.0
        assert directo["perfil"]["E"] == 3.0

    def test_alguien_que_contesta_lo_mismo_a_todo_sale_en_el_centro(self):
        # Es el efecto de los items invertidos y la razon de que existan: sin
        # ellos, marcar 5 a todo produciria un perfil de extremos.
        resultado = puntuar_bigfive({i: 5 for i in ITEMS_BIGFIVE}, ITEMS_BIGFIVE)

        # E, A, C y N tienen 2 items directos y 2 invertidos, asi que se
        # cancelan exactamente.
        for factor in ("E", "A", "C", "N"):
            assert resultado["perfil"][factor] == 3.0

    def test_apertura_no_esta_equilibrada_y_eso_no_es_un_error_nuestro(self):
        # HALLAZGO, no fallo. El Mini-IPIP publicado tiene Apertura con UN
        # item directo (17) y TRES invertidos (18, 19, 20), mientras los
        # otros cuatro factores van 2 y 2.
        #
        # Consecuencia medible: quien marca lo mismo a todo sale centrado en
        # E, A, C y N pero DESPLAZADO en Apertura. O sea que Apertura arrastra
        # sesgo de aquiescencia que los demas factores no tienen.
        #
        # Se fija en una prueba para que nadie lo "corrija" anadiendo un item
        # que el instrumento no tiene: cambiarlo romperia la comparabilidad
        # con la literatura, que es lo unico que justifica usarlo. Hay que
        # declararlo como limitacion, no arreglarlo.
        directos = sum(1 for f, k in ITEMS_BIGFIVE.values() if f == "O" and k == 1)
        invertidos = sum(1 for f, k in ITEMS_BIGFIVE.values() if f == "O" and k == -1)
        assert (directos, invertidos) == (1, 3)

        resultado = puntuar_bigfive({i: 5 for i in ITEMS_BIGFIVE}, ITEMS_BIGFIVE)

        assert resultado["perfil"]["O"] == 2.0  # (5 + 1 + 1 + 1) / 4

    def test_el_rango_va_de_uno_a_cinco(self):
        resultado = puntuar_bigfive({i: 3 for i in ITEMS_BIGFIVE}, ITEMS_BIGFIVE)

        assert all(1.0 <= v <= 5.0 for v in resultado["perfil"].values())

    def test_un_valor_fuera_de_la_escala_falla(self):
        with pytest.raises(RespuestaInvalida, match="Mini-IPIP usa"):
            puntuar_bigfive({1: 0}, ITEMS_BIGFIVE)


class TestCorrelacion:
    def test_dos_perfiles_identicos_correlacionan_uno(self):
        assert correlacion([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]) == pytest.approx(1.0)

    def test_dos_perfiles_opuestos_correlacionan_menos_uno(self):
        assert correlacion([1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1]) == pytest.approx(-1.0)

    def test_es_invariante_a_la_escala(self):
        # Es la propiedad que permite comparar un perfil 0..20 con uno 1..7,
        # y la que neutraliza a quien marca "me gusta" a todo.
        a = [1, 2, 3, 4, 5, 6]

        assert correlacion(a, [x * 3 + 10 for x in a]) == pytest.approx(1.0)

    def test_un_perfil_plano_da_cero_y_no_revienta(self):
        # Sin forma que correlacionar, 0 es lo honesto: no se parece ni se
        # deja de parecer a nada. Una division por cero seria un 500.
        assert correlacion([3, 3, 3, 3, 3, 3], [1, 2, 3, 4, 5, 6]) == 0.0


class TestEncajeConRamas:
    def test_un_perfil_artistico_encaja_con_ux_ui(self, perfiles_ramas):
        # LA PRUEBA QUE IMPORTA. Diseno UX/UI es la unica rama con Artistic
        # dominante (5.43 en O*NET). Si un perfil claramente artistico no
        # llega ahi, el anclaje externo no esta funcionando.
        alumno = puntuar_riasec(respuestas_riasec("A"), ITEMS_RIASEC)["perfil"]

        ranking = encaje_con_ramas(alumno, perfiles_ramas)

        assert ranking[0]["nombre"] == "Diseño UX/UI"

    def test_un_perfil_emprendedor_encaja_con_gestion(self, perfiles_ramas):
        # Gestion y Producto es la unica con Enterprising dominante (5.50).
        alumno = puntuar_riasec(respuestas_riasec("E"), ITEMS_RIASEC)["perfil"]

        ranking = encaje_con_ramas(alumno, perfiles_ramas)

        assert ranking[0]["nombre"] == "Gestión y Producto"

    def test_un_perfil_social_pone_soporte_por_delante_de_investigacion(self, perfiles_ramas):
        # Soporte Tecnico es la de Social mas alto (2.79); Investigacion la
        # que menos trato con personas tiene.
        alumno = puntuar_riasec(respuestas_riasec("S"), ITEMS_RIASEC)["perfil"]

        ranking = encaje_con_ramas(alumno, perfiles_ramas)
        posicion = {r["nombre"]: i for i, r in enumerate(ranking)}

        assert posicion["Soporte Técnico & IT Ops"] < posicion["Investigación e Innovación"]

    def test_devuelve_las_diez_ramas_ordenadas(self, perfiles_ramas):
        alumno = puntuar_riasec(respuestas_riasec("IC"), ITEMS_RIASEC)["perfil"]

        ranking = encaje_con_ramas(alumno, perfiles_ramas)

        assert len(ranking) == 10
        correlaciones = [r["correlacion"] for r in ranking]
        assert correlaciones == sorted(correlaciones, reverse=True)

    def test_el_orden_es_determinista(self, perfiles_ramas):
        # Dos ejecuciones con el mismo perfil tienen que dar el mismo orden,
        # incluso con empates. Un ranking que baila no es un diagnostico.
        alumno = puntuar_riasec(respuestas_riasec("RIASEC"), ITEMS_RIASEC)["perfil"]

        a = [r["specialization_id"] for r in encaje_con_ramas(alumno, perfiles_ramas)]
        b = [r["specialization_id"] for r in encaje_con_ramas(alumno, perfiles_ramas)]

        assert a == b

    def test_cada_rama_trae_su_codigo_holland_y_las_letras_compartidas(self, perfiles_ramas):
        # Las letras compartidas son la medida clasica de congruencia, y la
        # unica que se le puede explicar al alumno sin hablar de Pearson.
        alumno = puntuar_riasec(respuestas_riasec("A"), ITEMS_RIASEC)["perfil"]

        primero = encaje_con_ramas(alumno, perfiles_ramas)[0]

        assert len(primero["codigo_holland"]) == 3
        assert 0 <= primero["letras_compartidas"] <= 3
