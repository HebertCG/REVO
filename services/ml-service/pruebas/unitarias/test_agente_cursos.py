"""
Pruebas del agente de cursos.

Dos cosas se protegen aqui, y la segunda importa mas que la primera:

  1. Que la puntuacion ordene como dice ordenar.

  2. QUE EL AGENTE NO PUEDA ESCRIBIR EN LO QUE VE EL ALUMNO. Una mala
     recomendacion de curso le cuesta tiempo y dinero a alguien, y un
     proceso automatico no deberia poder incurrir en eso sin revision.
     Esa garantia esta en los permisos de PostgreSQL, y se comprueba en
     las pruebas de integracion.

No se llama a GitHub ni al MIT desde aqui: una prueba que depende de una
red ajena falla por motivos que no tienen que ver con el codigo. La fuente
real se ejerce a mano con `python -m agente_cursos --simular`; lo que se
prueba aqui es la logica, con casos sacados de pasadas reales.
"""
import pytest

from agente_cursos.agente import NOTA_MINIMA, seleccionar
from agente_cursos.fuentes.base import CursoCandidato, Fuente
from agente_cursos.puntuacion import PESOS, puntuar


def curso(**cambios) -> CursoCandidato:
    """Un candidato razonable al que cambiarle lo que interese."""
    base = {
        "titulo": "Introduccion a la ciberseguridad",
        "url": "https://ejemplo.edu/ciber-101",
        "descripcion": "Fundamentos de seguridad informatica y criptografia.",
        "idioma": "es",
        "duracion_horas": 20.0,
        "gratuito": True,
        "certificado": False,
        "vistas": 1000,
        "temas": ("Security",),
    }
    base.update(cambios)
    return CursoCandidato(**base)


class TestFormaDelCandidato:
    def test_un_curso_sin_titulo_no_se_puede_proponer(self):
        with pytest.raises(ValueError, match="titulo"):
            curso(titulo="   ")

    def test_una_url_que_no_es_url_se_rechaza(self):
        # Sin esto, un campo mal mapeado de una API acaba como enlace roto
        # en el roadmap de un alumno.
        with pytest.raises(ValueError, match="URL"):
            curso(url="javascript:alert(1)")

    def test_el_candidato_es_inmutable(self):
        c = curso()
        with pytest.raises(Exception):
            c.titulo = "otro"


class TestPuntuacion:
    def test_los_pesos_suman_uno(self):
        # Si no sumaran 1, la nota no estaria en 0..1 y el umbral minimo
        # dejaria de significar lo que dice.
        assert sum(PESOS.values()) == pytest.approx(1.0)

    def test_la_nota_esta_entre_cero_y_uno(self):
        for nivel in (1, 2, 3):
            nota = puntuar(curso(), 4, nivel)
            assert 0.0 <= nota.total <= 1.0

    def test_un_nivel_fuera_del_roadmap_falla(self):
        with pytest.raises(ValueError, match="roadmap"):
            puntuar(curso(), 4, 7)

    def test_el_desglose_explica_la_nota(self):
        # Una nota sin desglose no se puede discutir, y quien aprueba
        # necesita poder discutirla.
        nota = puntuar(curso(), 4, 1)

        assert set(nota.desglose) == set(PESOS)
        recompuesta = sum(v * PESOS[k] for k, v in nota.desglose.items())
        assert recompuesta == pytest.approx(nota.total)


class TestRelevancia:
    def test_un_curso_de_la_rama_puntua_mas_que_uno_de_otra(self):
        ciber = puntuar(curso(), 4, 1).desglose["relevancia"]
        en_otra_rama = puntuar(curso(), 8, 1).desglose["relevancia"]

        assert ciber > en_otra_rama

    def test_el_termino_en_el_titulo_pesa_mas_que_en_la_descripcion(self):
        # Un termino en el titulo dice mucho mas que el mismo perdido en un
        # parrafo, donde puede aparecer de pasada.
        en_titulo = puntuar(
            curso(titulo="Curso de ciberseguridad", descripcion="Temas varios."),
            4, 1).desglose["relevancia"]
        en_descripcion = puntuar(
            curso(titulo="Curso de temas varios", descripcion="Incluye ciberseguridad."),
            4, 1).desglose["relevancia"]

        assert en_titulo > en_descripcion

    def test_las_tildes_no_rompen_la_coincidencia(self):
        # 'diseño' tiene que casar con 'diseno'.
        con = puntuar(curso(titulo="Diseño de interfaces", temas=()), 8, 1)
        sin = puntuar(curso(titulo="Diseno de interfaces", temas=()), 8, 1)

        assert con.desglose["relevancia"] == sin.desglose["relevancia"] > 0


class TestEncajeDeNivel:
    def test_un_curso_avanzado_no_llena_el_hueco_de_fundamentos(self):
        # No solo no lo llena: lo BLOQUEA, y el alumno se estrella en el
        # primer escalon de su roadmap.
        avanzado = curso(titulo="Advanced cryptography for graduate students")

        assert puntuar(avanzado, 4, 1).desglose["nivel"] < 0.2

    def test_un_curso_basico_encaja_en_fundamentos(self):
        basico = curso(titulo="Introduction to cybersecurity")

        assert puntuar(basico, 4, 1).desglose["nivel"] == 1.0

    def test_un_curso_basico_no_encaja_en_experto(self):
        basico = curso(titulo="Introduction to cybersecurity")

        assert puntuar(basico, 4, 3).desglose["nivel"] < 0.3

    def test_sin_senales_de_nivel_no_se_castiga(self):
        # La mayoria de los cursos no declaran su nivel en el titulo.
        # Castigarlos por eso dejaria fuera material perfectamente valido.
        neutro = curso(titulo="Seguridad de redes", descripcion="Temario amplio.")

        assert puntuar(neutro, 4, 1).desglose["nivel"] == 0.5


class TestAccesoEIdioma:
    def test_lo_gratuito_puntua_mas_que_lo_de_pago(self):
        # El alumno objetivo es un estudiante universitario peruano: un
        # curso de 400 dolares no es una recomendacion.
        assert (puntuar(curso(gratuito=True), 4, 1).desglose["acceso"]
                > puntuar(curso(gratuito=False), 4, 1).desglose["acceso"])

    def test_lo_desconocido_queda_en_medio(self):
        desconocido = puntuar(curso(gratuito=None), 4, 1).desglose["acceso"]

        assert (puntuar(curso(gratuito=False), 4, 1).desglose["acceso"]
                < desconocido
                < puntuar(curso(gratuito=True), 4, 1).desglose["acceso"])

    def test_el_espanol_suma_pero_el_ingles_no_descalifica(self):
        es = puntuar(curso(idioma="es"), 4, 1).desglose["idioma"]
        en = puntuar(curso(idioma="en"), 4, 1).desglose["idioma"]

        assert es > en > 0.4   # el ingles sigue siendo util


class TestDuracion:
    def test_la_duracion_ideal_del_nivel_puntua_maximo(self):
        assert puntuar(curso(duracion_horas=20), 4, 1).desglose["duracion"] == 1.0

    def test_un_video_suelto_no_llena_un_escalon(self):
        assert puntuar(curso(duracion_horas=0.5), 4, 1).desglose["duracion"] < 0.3

    def test_un_master_de_300_horas_tampoco(self):
        assert puntuar(curso(duracion_horas=300), 4, 1).desglose["duracion"] < 0.3

    def test_sin_dato_no_se_castiga(self):
        # No saber cuanto dura no es lo mismo que durar mal, y penalizarlo
        # eliminaria fuentes enteras que no publican duracion.
        assert puntuar(curso(duracion_horas=None), 4, 1).desglose["duracion"] == 0.5


class TestSeleccion:
    def test_descarta_lo_que_no_llega_al_minimo(self):
        malo = curso(titulo="Reposteria creativa", descripcion="Tartas.",
                     temas=(), gratuito=False, idioma="fr", duracion_horas=400)

        assert seleccionar([malo], 4, 1) == []

    def test_devuelve_como_mucho_los_pedidos(self):
        cursos = [curso(url=f"https://ejemplo.edu/{i}") for i in range(10)]

        assert len(seleccionar(cursos, 4, 1, cuantos=3)) == 3

    def test_ordena_de_mejor_a_peor(self):
        cursos = [
            curso(url="https://e.edu/1", titulo="Introduccion a la ciberseguridad"),
            curso(url="https://e.edu/2", titulo="Cocina al vapor", temas=()),
            curso(url="https://e.edu/3", titulo="Fundamentos de seguridad informatica"),
        ]

        notas = [n.total for _, n in seleccionar(cursos, 4, 1, cuantos=5)]

        assert notas == sorted(notas, reverse=True)

    def test_el_orden_es_determinista(self):
        # Dos ejecuciones con los mismos datos tienen que proponer lo mismo,
        # o el administrador revisa una lista distinta cada vez.
        cursos = [curso(url=f"https://ejemplo.edu/{i}") for i in range(6)]

        a = [c.url for c, _ in seleccionar(cursos, 4, 1)]
        b = [c.url for c, _ in seleccionar(cursos, 4, 1)]

        assert a == b

    def test_el_umbral_minimo_se_respeta(self):
        cursos = [curso(url=f"https://ejemplo.edu/{i}") for i in range(6)]

        for _, nota in seleccionar(cursos, 4, 1):
            assert nota.total >= NOTA_MINIMA


class TestContratoDeFuente:
    def test_una_fuente_sin_base_legal_no_se_puede_instanciar(self):
        # Es la garantia de que nadie anade una fuente sin justificar por
        # que se puede usar. El texto viaja ademas a una columna NOT NULL.
        class SinJustificar(Fuente):
            @property
            def nombre(self):
                return "x"
            # falta base_legal a proposito
            def buscar(self, consulta, limite=20):
                return []

        with pytest.raises(TypeError):
            SinJustificar()

    def test_una_fuente_completa_si_se_instancia(self):
        class Correcta(Fuente):
            @property
            def nombre(self):
                return "prueba"

            @property
            def base_legal(self):
                return "Datos de dominio publico, sin restriccion."

            def buscar(self, consulta, limite=20):
                return [curso()]

        fuente = Correcta()

        assert fuente.nombre == "prueba"
        assert fuente.base_legal
        assert len(fuente.buscar("lo que sea")) == 1



# ── La fuente en espanol: GitHub ─────────────────────────────
# Libre, sin clave y sin registro. No se llama a la API de verdad desde
# aqui: lo que se prueba es el filtrado y la conversion, que es lo que se
# rompe al tocar el codigo.

from agente_cursos.agente import (  # noqa: E402
    CONSULTAS_ES, RELEVANCIA_MINIMA, consultas_para, seleccionar as _sel,
)
from agente_cursos.fuentes.github import (  # noqa: E402
    ANTIGUEDAD_MAXIMA_ANOS, ESTRELLAS_MINIMAS, GitHub,
)


def repo(**cambios) -> dict:
    """Un repositorio de GitHub razonable."""
    base = {
        "full_name": "alguien/curso-ciberseguridad",
        "html_url": "https://github.com/alguien/curso-ciberseguridad",
        "name": "curso-ciberseguridad",
        "description": "Curso de ciberseguridad desde cero para principiantes",
        "stargazers_count": 200,
        "topics": ["ciberseguridad", "hacking"],
        "language": "Python",
        "archived": False,
        "fork": False,
        "pushed_at": "2026-06-01T00:00:00Z",
        "size": 18000,
    }
    base.update(cambios)
    return base


class TestFiltradoDeRepositorios:
    def test_un_repositorio_valido_se_convierte(self):
        c = GitHub()._convertir(repo())

        assert c is not None
        assert c.url.startswith("https://github.com/")
        assert c.gratuito is True      # un repositorio publico es gratuito
        assert c.vistas == 200         # las estrellas hacen de popularidad

    def test_los_archivados_se_descartan(self):
        # Su autor declaro que ya no lo mantiene. No es un curso peor: es un
        # curso muerto, y eso no es cuestion de grado.
        assert GitHub()._convertir(repo(archived=True)) is None

    def test_las_copias_se_descartan(self):
        # El original es el que tiene la comunidad detras.
        assert GitHub()._convertir(repo(fork=True)) is None

    def test_sin_estrellas_suficientes_se_descarta(self):
        assert GitHub()._convertir(repo(stargazers_count=ESTRELLAS_MINIMAS - 1)) is None

    def test_lo_abandonado_hace_anos_se_descarta(self):
        # Un curso de Angular sin tocar desde 2015 ensena una version que ya
        # no existe.
        assert GitHub()._convertir(repo(pushed_at="2015-01-01T00:00:00Z")) is None

    def test_sin_fecha_se_descarta(self):
        # Sin saber si esta vivo, no entra en el roadmap de nadie.
        assert GitHub()._convertir(repo(pushed_at=None)) is None


class TestDeteccionDeIdioma:
    """
    Casos sacados de una pasada real contra GitHub, con su texto literal.

    La primera version contaba articulos y preposiciones, e incluia "para"
    y "desde" como marcas de espanol. Las dos existen en portugues, asi que
    tres repositorios brasilenos salieron como espanol y un curso en ingles
    salio como portugues.
    """

    @pytest.mark.parametrize("titulo, descripcion", [
        ("Sites, blogs, cursos, redes sociais e projetos de referências "
         "para desenvolvedores .NET", None),
        ("Guia de Redes: trilhas, cursos, livros, canais, ferramentas e "
         "comunidades para você entrar e evoluir na área.", None),
        ("NOVO CURSO - AI (Artificial Intelligence - IA Inteligência "
         "Artificial) para Redes de Computadores (Networking)", None),
        ("Curso de TDD com Rails", None),
        ("Curso GRÁTIS SAMBA 4 Level 2", "Esse repositório não "
         "irá mais receber atualizações."),
        ("NOVO PROJETO - Curso GRATIS de Inventario",
         "Curso completo para voce aprender do zero"),
    ])
    def test_reconoce_el_portugues(self, titulo, descripcion):
        assert GitHub._idioma(titulo, descripcion) == "pt"

    @pytest.mark.parametrize("titulo, descripcion", [
        ("Entornos de Desarrollo - 05 Clean Code y TDD: Pruebas de Software. "
         "1DAM. Curso 2021-2022.", None),
        ("Curso de desarrollo para asegurar la calidad del software", None),
        ("Repositorio del curso de Redes neuronales, en la Facultad de "
         "Ciencias, UNAM.", None),
        ("Curso de programacion desde cero",
         "Aprende a programar con Python para principiantes"),
        ("Diseño de interfaces", None),
    ])
    def test_reconoce_el_espanol(self, titulo, descripcion):
        assert GitHub._idioma(titulo, descripcion) == "es"

    @pytest.mark.parametrize("titulo, descripcion", [
        ("This is the most modern and comprehensive course available for "
         "Spring Framework 5 and Spring Boot 2.", None),
        ("TDD course exercises", None),
    ])
    def test_reconoce_el_ingles(self, titulo, descripcion):
        # Antes salia como portugues. Buscar "curso tdd" tambien devuelve
        # material en ingles, y hay que poder apartarlo.
        assert GitHub._idioma(titulo, descripcion) == "en"

    def test_gratis_con_tilde_es_portugues(self):
        # En espanol se escribe sin tilde. Los cursos de un mismo autor
        # brasileno salian como "no se" y pasaban el filtro.
        assert GitHub._idioma(
            ":large_blue_circle: Curso GRÁTIS de GNU/Linux Ubuntu Server "
            "22.04.x LTS", None) == "pt"

    def test_un_texto_no_latino_es_otro_idioma(self):
        # Caso real: "curso linux" devolvio esto porque GitHub casa "curso"
        # con "Cursor". Sin marcas latinas salia None y pasaba el filtro.
        assert GitHub._idioma(
            "Cursor 中文汉化工具，支持 "
            "Windows、macOS 和 Linux", None) == "otro"

    def test_para_y_desde_no_deciden_nada(self):
        # Existen en las dos lenguas. Contarlas como espanol fue el defecto.
        assert GitHub._idioma("para desde", None) is None

    def test_sin_evidencia_admite_que_no_sabe(self):
        # None puntua 0.5. Admitir la duda es mejor que afirmar de mas: es
        # el mismo criterio que el resto del sistema.
        assert GitHub._idioma("awesome-security", None) is None

    def test_el_portugues_puntua_menos_que_el_espanol(self):
        es = puntuar(curso(idioma="es"), 4, 1).desglose["idioma"]
        pt = puntuar(curso(idioma="pt"), 4, 1).desglose["idioma"]

        assert es > pt


class TestSoloEspanol:
    """
    El espanol es condicion necesaria, igual que la gratuidad.

    DEFECTO REAL: con el idioma como sumando, un curso brasileno sacaba
    0.766 y quedaba PRIMERO en el hueco de Infraestructura nivel 3. Pesa
    0.15; el portugues vale 0.3 frente a 1.0, y eso resta solo 0.105, que
    el resto de componentes compensa de sobra.
    """

    def test_el_portugues_se_descarta(self):
        assert _sel([curso(idioma="pt")], 4, 1) == []

    def test_el_ingles_se_descarta_fuera_de_experto(self):
        assert _sel([curso(idioma="en")], 4, 1) == []

    def test_lo_desconocido_pasa(self):
        # Mismo criterio que con el precio: un titulo escueto no declara su
        # idioma, y descartarlo eliminaria buen material en espanol.
        assert len(_sel([curso(idioma=None)], 4, 1)) == 1

    def test_la_politica_se_puede_cambiar_por_llamada(self):
        assert len(_sel([curso(idioma="en")], 4, 1, idiomas=frozenset({"es", "en"}))) == 1


class TestSoloGratuitos:
    def test_lo_de_pago_se_descarta_del_todo(self):
        # No es "menos bueno" para quien no puede pagarlo: es inaccesible, y
        # eso no lo compensa ninguna media ponderada.
        de_pago = curso(gratuito=False, titulo="Curso de ciberseguridad")

        assert _sel([de_pago], 4, 1) == []

    def test_lo_desconocido_si_pasa(self):
        # Descartar lo que no declara precio eliminaria fuentes enteras.
        sin_declarar = curso(gratuito=None, titulo="Curso de ciberseguridad")

        assert len(_sel([sin_declarar], 4, 1)) == 1


class TestRelevanciaComoFiltro:
    def test_un_curso_irrelevante_no_se_propone_aunque_saque_buena_nota(self):
        # DEFECTO REAL: "Hello python" sacaba relevancia 0.08 y nota total
        # 0.681, quedando primero. Un curso de reposteria gratis y en espanol
        # sacaria algo parecido. La relevancia tiene que ser condicion
        # necesaria, no un sumando mas.
        irrelevante = curso(
            titulo="Curso de reposteria creativa",
            descripcion="Tartas y postres paso a paso.",
            temas=("cocina",), gratuito=True, idioma="es", duracion_horas=20)

        nota = puntuar(irrelevante, 4, 1)

        assert nota.desglose["relevancia"] < RELEVANCIA_MINIMA
        assert _sel([irrelevante], 4, 1) == []

    def test_los_lenguajes_cuentan_como_desarrollo(self):
        # "Hello Python" sacaba 0.08 porque la lista de terminos solo tenia
        # palabras abstractas. Los cursos reales se llaman por el lenguaje.
        for lenguaje in ("Python", "Java", "JavaScript"):
            nota = puntuar(curso(titulo=f"Curso de {lenguaje} desde cero",
                                 temas=()), 1, 1)
            assert nota.desglose["relevancia"] >= RELEVANCIA_MINIMA, lenguaje


class TestConsultasEnEspanol:
    def test_github_recibe_consultas_en_espanol(self):
        consultas = consultas_para(GitHub(), 4)

        # No se exige "curso": "ciberseguridad" sola dio 19 cursos utiles y
        # "curso ciberseguridad" 2. Lo que asegura que sea material formativo
        # es el filtro del adaptador, no la consulta.
        assert consultas == CONSULTAS_ES[4]

    def test_un_catalogo_universitario_recibe_las_de_ingles(self):
        from agente_cursos.fuentes.mit_learn import MITLearn

        assert "cybersecurity" in consultas_para(MITLearn(), 4)

    def test_todas_las_ramas_tienen_consultas_en_espanol(self):
        for rama in range(1, 11):
            assert len(CONSULTAS_ES[rama]) >= 3, f"rama {rama}"

    def test_la_base_legal_dice_que_es_libre_y_sin_clave(self):
        legal = GitHub().base_legal.lower()

        assert "sin clave" in legal or "sin registro" in legal


class TestConsultasCortas:
    def test_ninguna_consulta_en_espanol_pasa_de_tres_palabras(self):
        # DEFECTO REAL: "curso de linux administracion" solo casaba con
        # repositorios de alumnos, ninguno con 15 estrellas. Las ramas de
        # Infraestructura y QA se quedaban a cero sin que nada fallara.
        for rama, consultas in CONSULTAS_ES.items():
            for consulta in consultas:
                assert len(consulta.split()) <= 3, (rama, consulta)


# ── Linea de comandos ────────────────────────────────────────

from agente_cursos.__main__ import analizar_argumentos, simular  # noqa: E402


class FuenteFalsa(Fuente):
    """Devuelve siempre lo mismo y cuenta cuantas veces se le pregunta."""

    def __init__(self, cursos):
        self.cursos = cursos
        self.consultas = []

    @property
    def nombre(self):
        return "github"   # para que reciba las consultas en espanol

    @property
    def base_legal(self):
        return "fuente de prueba"

    def buscar(self, consulta, limite=20):
        self.consultas.append(consulta)
        return list(self.cursos)


class TestLineaDeComandos:
    def test_por_defecto_escribe_en_la_base_de_datos(self):
        assert analizar_argumentos([]).simular is False

    def test_se_puede_limitar_a_algunas_ramas(self):
        assert analizar_argumentos(["--ramas", "3", "6"]).ramas == [3, 6]

    def test_una_rama_inexistente_se_rechaza(self):
        with pytest.raises(SystemExit):
            analizar_argumentos(["--ramas", "11"])

    def test_simular_no_toca_la_base_de_datos_y_cubre_los_tres_niveles(self, capsys):
        fuente = FuenteFalsa([curso(titulo="Curso de ciberseguridad desde cero")])

        propuestas = simular(fuente, [4])

        assert set(propuestas) == {(4, 1), (4, 2), (4, 3)}
        assert fuente.consultas == list(CONSULTAS_ES[4])
        assert "ciberseguridad" in capsys.readouterr().out

    def test_simular_senala_los_huecos_vacios(self, capsys):
        # Un hueco vacio no es un error del agente, pero quien lo lanza
        # tiene que verlo: es justo lo que paso con las ramas 3 y 6.
        simular(FuenteFalsa([]), [6])

        assert "sin candidatos" in capsys.readouterr().out


class TestRelevanciaPorPalabras:
    """
    Los terminos se buscan como PRINCIPIO de palabra, no como subcadena.

    Con subcadenas, "ux" (Diseno UX/UI) esta dentro de "linux" y "api"
    dentro de "capitulo". Un curso de Linux sumaba relevancia para UX/UI.
    """

    def test_linux_no_cuenta_como_ux(self):
        linux = curso(titulo="Curso de Linux", descripcion=None, temas=())

        assert puntuar(linux, 8, 1).desglose["relevancia"] == 0

    def test_capitulo_no_cuenta_como_api(self):
        capitulos = curso(titulo="Capitulo uno", descripcion=None, temas=())

        assert puntuar(capitulos, 1, 1).desglose["relevancia"] == 0

    def test_los_plurales_y_derivados_siguen_contando(self):
        # Se ancla el principio, no el final: "networking" y "apis" casan.
        redes = curso(titulo="Networking basico", descripcion=None, temas=())

        assert puntuar(redes, 3, 1).desglose["relevancia"] > 0


class TestPlataformasDePago:
    """
    DEFECTO REAL: "Contenido del Curso de React Avanzado para Platzi".

    El repositorio es gratis, pero es solo el codigo final: las clases son
    de pago. Para el alumno no es un curso gratuito, es un anuncio.
    """

    @pytest.mark.parametrize("descripcion", [
        "Contenido del Curso de React Avanzado para Platzi",
        "Codigo del curso de Udemy sobre Docker",
        "Proyecto del curso de Domestika",
    ])
    def test_el_codigo_de_un_curso_de_pago_no_es_gratuito(self, descripcion):
        c = GitHub()._convertir(repo(description=descripcion))

        assert c is not None
        assert c.gratuito is False
        assert _sel([c], 1, 1) == []

    def test_un_curso_libre_sigue_siendo_gratuito(self):
        assert GitHub()._convertir(repo()).gratuito is True


class TestSoloMaterialFormativo:
    """
    Un repositorio tiene que ser MATERIAL FORMATIVO, no software.

    DEFECTO REAL: buscando "odoo" salieron 17 candidatos y los 17 eran
    modulos ("Odoo Warehouse Management Addons"). Buscando "ciberseguridad"
    se colo un "Pentesting toolkit". Mientras la consulta llevaba "curso"
    esto se cumplia de rebote; al quitarla para ganar cobertura, dejo de
    cumplirse.
    """

    @pytest.mark.parametrize("descripcion", [
        "Odoo Warehouse Management Addons",
        "Pentesting toolkit",
        "Cursor \u4e2d\u6587\u6c49\u5316\u5de5\u5177",   # "curso" no es "Cursor"
    ])
    def test_el_software_no_es_un_curso(self, descripcion):
        assert GitHub()._convertir(repo(
            name="herramienta", description=descripcion, topics=[])) is None

    @pytest.mark.parametrize("descripcion", [
        "Apuntes de sistemas operativos",
        "Recursos del Taller de Seguridad Ofensiva",
        "Ejercicios de C para el TP de Sistemas Operativos",
        "Introducci\u00f3n a Docker para principiantes",
        "Clases de Implantaci\u00f3n de Sistemas Operativos",
    ])
    def test_el_material_formativo_pasa_aunque_no_diga_curso(self, descripcion):
        assert GitHub()._convertir(repo(
            name="material", description=descripcion, topics=[])) is not None

    def test_la_etiqueta_del_repositorio_tambien_cuenta(self):
        # Muchos autores lo dicen en los temas y no en la descripcion.
        assert GitHub()._convertir(repo(
            name="docker", description="Docker en la practica",
            topics=["tutorial"])) is not None


class TestRepartoEntreNiveles:
    """
    Cada curso va a UN nivel del roadmap, no a los tres.

    DEFECTO REAL, primera pasada completa: cada nivel se elegia por
    separado y la nota de nivel solo pesa 0.20, asi que los mismos cursos
    ganaban en los tres. "Python web" era a la vez Fundamentos, Construccion
    y Experto; Gestion tenia un unico curso repetido en los tres huecos.
    """

    def _urls(self, reparto):
        return [c.url for lista in reparto.values() for c, _ in lista]

    def test_un_curso_no_se_repite_entre_niveles(self):
        from agente_cursos.agente import repartir
        cursos = [curso(url=f"https://ejemplo.edu/{i}",
                        titulo=f"Curso de ciberseguridad {i}") for i in range(4)]

        urls = self._urls(repartir(cursos, 4))

        assert len(urls) == len(set(urls)) == 4

    def test_cada_curso_va_donde_mejor_encaja(self):
        from agente_cursos.agente import repartir
        basico = curso(url="https://ejemplo.edu/b",
                       titulo="Introduccion a la ciberseguridad")
        avanzado = curso(url="https://ejemplo.edu/a",
                         titulo="Ciberseguridad avanzada", descripcion=None)

        reparto = repartir([basico, avanzado], 4)

        assert [c.url for c, _ in reparto[1]] == [basico.url]
        assert [c.url for c, _ in reparto[3]] == [avanzado.url]

    def test_con_un_solo_curso_quedan_huecos_vacios(self):
        # Es la verdad: no hay tres cursos distintos para esa rama. Rellenar
        # los huecos repitiendolo esconderia justo lo que el administrador
        # necesita ver.
        from agente_cursos.agente import repartir

        reparto = repartir([curso()], 4)

        assert sum(len(lista) for lista in reparto.values()) == 1

    def test_respeta_el_cupo_por_hueco(self):
        from agente_cursos.agente import POR_HUECO, repartir
        cursos = [curso(url=f"https://ejemplo.edu/{i}") for i in range(12)]

        reparto = repartir(cursos, 4)

        assert all(len(lista) <= POR_HUECO for lista in reparto.values())

    def test_la_pasada_completa_no_repite_dentro_de_una_rama(self):
        cursos = [curso(url=f"https://ejemplo.edu/{i}",
                        titulo=f"Curso de ciberseguridad {i}") for i in range(3)]

        propuestas = simular(FuenteFalsa(cursos), [4])

        urls = [c.url for lista in propuestas.values() for c, _ in lista]
        assert len(urls) == len(set(urls))


class TestDesdeCeroEsBasico:
    def test_desde_cero_cuenta_como_fundamentos(self):
        # "Aprende React Native desde cero" acababa en el nivel Experto.
        c = curso(titulo="Aprende React Native desde cero", descripcion=None)

        assert puntuar(c, 1, 1).desglose["nivel"] == 1.0


# ── Fallar en voz alta ───────────────────────────────────────

import requests  # noqa: E402

from agente_cursos.fuentes.base import FuenteNoDisponible  # noqa: E402


class FuenteCaida(FuenteFalsa):
    """Nunca responde: sin red, DNS roto, API caida."""

    def __init__(self, fallos_antes_de_responder=None, cursos=()):
        super().__init__(list(cursos))
        self.fallos = fallos_antes_de_responder

    def buscar(self, consulta, limite=20):
        self.consultas.append(consulta)
        if self.fallos is None or len(self.consultas) <= self.fallos:
            raise FuenteNoDisponible("sin red")
        return list(self.cursos)


class SesionSinRed(requests.Session):
    def get(self, *args, **kwargs):
        raise requests.ConnectionError("Failed to resolve 'api.github.com'")


class SesionConLimite(requests.Session):
    def get(self, *args, **kwargs):
        respuesta = requests.Response()
        respuesta.status_code = 403
        return respuesta


class TestFallarEnVozAlta:
    """
    DEFECTO REAL: sin salida a internet, cada busqueda devolvia lista vacia
    y la pasada terminaba "bien", con 0 propuestas y sin error registrado.
    En la tabla de ejecuciones quedo una fila asi de una sesion anterior.
    El roadmap se habria quedado sin actualizar sin que nadie se enterara, y
    cron no habria avisado.

    "No hay cursos" y "no se pudo preguntar" son cosas distintas.
    """

    def test_github_sin_red_lo_dice(self):
        with pytest.raises(FuenteNoDisponible):
            GitHub(SesionSinRed()).buscar("curso python")

    def test_github_con_el_limite_agotado_lo_dice(self):
        with pytest.raises(FuenteNoDisponible, match="minuto"):
            GitHub(SesionConLimite()).buscar("curso python")

    def test_si_ninguna_consulta_llega_la_pasada_falla(self):
        from agente_cursos.agente import recorrer_huecos

        with pytest.raises(FuenteNoDisponible, match="Ninguna"):
            recorrer_huecos(FuenteCaida(), [4])

    def test_un_fallo_suelto_no_tumba_la_pasada(self):
        # Un 403 puntual no deberia costar la ejecucion entera.
        from agente_cursos.agente import recorrer_huecos
        fuente = FuenteCaida(fallos_antes_de_responder=1,
                             cursos=[curso(titulo="Curso de ciberseguridad")])

        propuestas = recorrer_huecos(fuente, [4])

        assert sum(len(v) for v in propuestas.values()) == 1

    def test_la_linea_de_comandos_devuelve_error_para_que_cron_avise(self, capsys):
        from agente_cursos.__main__ import main

        codigo = main(["--simular", "--ramas", "4"], fuentes=[FuenteCaida()])

        assert codigo == 1
        assert "ERROR" in capsys.readouterr().out


class TestNivelContradictorio:
    """
    DEFECTO REAL, primera pasada con reparto: "Curso de Introduccion al
    Hacking" acabo en el nivel Experto. El reparto llena la ultima plaza con
    lo que sobra, y un curso que se DECLARA introductorio seguia superando la
    nota minima (0.523) con un encaje de nivel de 0.2.
    """

    def test_un_curso_introductorio_no_va_al_nivel_experto(self):
        intro = curso(titulo="Curso de Introduccion al Hacking", descripcion=None)

        assert _sel([intro], 4, 3) == []
        assert len(_sel([intro], 4, 1)) == 1

    def test_un_curso_avanzado_no_va_a_fundamentos(self):
        avanzado = curso(titulo="Hacking avanzado", descripcion=None)

        assert _sel([avanzado], 4, 1) == []
        assert len(_sel([avanzado], 4, 3)) == 1

    def test_lo_que_no_declara_nivel_puede_ir_a_cualquiera(self):
        # La mayoria de los cursos no dicen su nivel. Excluirlos vaciaria el
        # roadmap.
        neutro = curso(titulo="Curso de hacking", descripcion=None)

        assert all(len(_sel([neutro], 4, n)) == 1 for n in (1, 2, 3))


# ── Robustez: limite de GitHub y ejecuciones abandonadas ─────

import json as _json  # noqa: E402
import time as _time  # noqa: E402


def respuesta_github(estado, items=(), cabeceras=None):
    r = requests.Response()
    r.status_code = estado
    r._content = _json.dumps({"items": list(items)}).encode()
    r.headers.update(cabeceras or {})
    return r


def limite_agotado(dentro_de_s):
    return respuesta_github(403, cabeceras={
        "x-ratelimit-remaining": "0",
        "x-ratelimit-reset": str(int(_time.time() + dentro_de_s)),
    })


class SesionGuionada(requests.Session):
    """Devuelve las respuestas en el orden en que se le dan."""

    def __init__(self, respuestas):
        super().__init__()
        self.respuestas = list(respuestas)

    def get(self, *args, **kwargs):
        return self.respuestas.pop(0)


class TestLimiteDeGitHub:
    """
    DEFECTO REAL: se relanzo una pasada justo despues de parar otra y las
    dos compartieron la ventana de 10 busquedas por minuto. "curso docker"
    devolvio 403 y la rama 3 perdio una consulta. GitHub dice en las
    cabeceras cuando reabre el cupo: basta con esperar y reintentar.
    """

    def test_con_el_cupo_agotado_espera_y_reintenta(self):
        esperas = []
        sesion = SesionGuionada([limite_agotado(5), respuesta_github(200)])

        resultado = GitHub(sesion, dormir=esperas.append).buscar("curso docker")

        assert resultado == []
        assert sesion.respuestas == []                 # hubo segunda peticion
        assert any(4 <= e <= 8 for e in esperas)       # y antes espero al cupo

    def test_si_el_cupo_tarda_demasiado_no_se_queda_colgado(self):
        esperas = []
        sesion = SesionGuionada([limite_agotado(600)])

        with pytest.raises(FuenteNoDisponible):
            GitHub(sesion, dormir=esperas.append).buscar("curso docker")
        assert esperas == []

    def test_reintenta_una_sola_vez(self):
        sesion = SesionGuionada([
            limite_agotado(5), limite_agotado(5), respuesta_github(200)])

        with pytest.raises(FuenteNoDisponible):
            GitHub(sesion, dormir=lambda s: None).buscar("curso docker")
        assert len(sesion.respuestas) == 1             # la tercera no se pidio


class BDFalsa:
    """Registra lo que se ejecuta. Basta para probar el orden y el error."""

    class _Resultado:
        rowcount = 0

        def __init__(self, filas=()):
            self.filas = list(filas)

        def scalar(self):
            return 1

        def scalars(self):
            return self

        def all(self):
            return self.filas

    def __init__(self, decididas=()):
        self.sentencias = []
        self.decididas = list(decididas)

    def execute(self, sentencia, parametros=None):
        self.sentencias.append((str(sentencia), parametros))
        if "SELECT url" in str(sentencia):
            return self._Resultado(self.decididas)
        return self._Resultado()

    def commit(self):
        pass


class TestEjecucionRegistrada:
    def test_una_pasada_sin_fuente_queda_registrada_como_fallida(self):
        from agente_cursos.agente import ejecutar
        bd = BDFalsa()

        resultado = ejecutar(bd, FuenteCaida(), [4])

        assert "Ninguna" in resultado.error
        cierre = bd.sentencias[-1]
        assert "UPDATE agente_cursos_ejecuciones" in cierre[0]
        assert "Ninguna" in cierre[1]["e"]

    def test_antes_de_empezar_cierra_las_ejecuciones_abandonadas(self):
        # Docker se detuvo a mitad de una pasada y su fila quedo abierta,
        # aparentando estar en curso. Paso tres veces en un mismo dia.
        from agente_cursos.agente import ejecutar
        bd = BDFalsa()

        ejecutar(bd, FuenteFalsa([]), [4])

        primera = bd.sentencias[0][0]
        assert "terminado_en IS NULL" in primera
        assert "INTERVAL" in primera


class TestPagoPorElDueno:
    """
    DEFECTO REAL, pasada completa: `platzi/curso-kubernetes` entro como
    gratuito. La descripcion ("Curso de Kubernetes profesor Marcos Nils") no
    nombra la plataforma; el DUENO del repositorio si. Y Cod3r, academia
    brasilena de pago, no estaba en la lista.
    """

    def test_un_repositorio_de_la_cuenta_de_platzi_no_es_gratuito(self):
        c = GitHub()._convertir(repo(
            full_name="platzi/curso-kubernetes",
            html_url="https://github.com/platzi/curso-kubernetes",
            description="Curso de Kubernetes profesor Marcos Nils"))

        assert c is not None and c.gratuito is False

    def test_cod3r_es_de_pago(self):
        c = GitHub()._convertir(repo(
            full_name="cod3rcursos/curso-react-native",
            description="Curso React Native"))

        assert c is not None and c.gratuito is False


class TestEntrePasadas:
    """
    El agente corre cada dia; la tabla acumula pasadas. El reparto evita
    repetidos DENTRO de una pasada, pero si manana un curso cae en otro
    nivel, quedaria propuesto en dos a la vez. Y lo que un humano rechazo
    no deberia volver a aparecer.
    """

    def test_antes_de_guardar_una_rama_retira_lo_que_propuso_antes(self):
        from agente_cursos.agente import guardar
        bd = BDFalsa()
        propuestas = {(4, 1): [(curso(), puntuar(curso(), 4, 1))], (4, 2): [], (4, 3): []}

        guardar(bd, FuenteFalsa([]), propuestas)

        sentencias = [s for s, _ in bd.sentencias]
        retirar = next(i for i, s in enumerate(sentencias) if "'retirado'" in s)
        insertar = next(i for i, s in enumerate(sentencias) if "INSERT" in s)
        assert retirar < insertar
        # Solo lo de ESTA fuente y ESTA rama: otra fuente no tiene por que
        # perder sus propuestas porque esta haya cambiado de opinion.
        assert bd.sentencias[retirar][1] == {"rama": 4, "fuente": "github"}

    def test_no_repropone_lo_que_un_humano_ya_decidio(self):
        from agente_cursos.agente import guardar
        rechazado = curso()
        bd = BDFalsa(decididas=[rechazado.url])

        guardados = guardar(bd, FuenteFalsa([]), {
            (4, 1): [], (4, 2): [(rechazado, puntuar(rechazado, 4, 2))], (4, 3): []})

        assert guardados == 0
        assert not any("INSERT" in s for s, _ in bd.sentencias)

    def test_una_rama_sin_respuesta_no_se_toca(self):
        # Si sus tres consultas fallaron, no es que no haya cursos: es que no
        # se pudo preguntar. Retirar lo que habia seria borrar trabajo bueno
        # por un 403.
        from agente_cursos.agente import recorrer_huecos
        fuente = FuenteCaida(fallos_antes_de_responder=3,
                             cursos=[curso(titulo="Curso de ciberseguridad")])

        propuestas = recorrer_huecos(fuente, [3, 4])

        assert {rama for rama, _ in propuestas} == {4}


class TestInglesSoloEnExperto:
    """
    Decision del autor (2026-09-21): ingles admitido SOLO en el nivel
    Experto. Cinco ramas se quedaban sin nada en ese nivel porque el material
    avanzado gratuito esta casi todo en ingles. En Fundamentos no: quien
    empieza necesita entender sin traducir.
    """

    @staticmethod
    def neutro(**cambios):
        # Sin senal de nivel: "Introduccion..." no podria ir a Experto por el
        # filtro de nivel contradictorio, y no es eso lo que se prueba aqui.
        return curso(**{"titulo": "Curso de ciberseguridad", "descripcion": None, **cambios})

    def test_el_ingles_entra_en_experto(self):
        assert len(_sel([self.neutro(idioma="en")], 4, 3)) == 1

    def test_el_ingles_no_entra_en_fundamentos_ni_construccion(self):
        assert _sel([curso(idioma="en")], 4, 1) == []
        assert _sel([curso(idioma="en")], 4, 2) == []

    def test_el_portugues_no_entra_en_ningun_nivel(self):
        for nivel in (1, 2, 3):
            assert _sel([curso(idioma="pt")], 4, nivel) == [], nivel

    def test_a_igualdad_gana_el_espanol(self):
        # El ingles rellena donde no hay; no desplaza al espanol.
        es = self.neutro(url="https://ejemplo.edu/es", idioma="es")
        en = self.neutro(url="https://ejemplo.edu/en", idioma="en")

        ordenados = [c.idioma for c, _ in _sel([en, es], 4, 3)]

        assert ordenados == ["es", "en"]

    def test_el_reparto_manda_el_ingles_a_experto(self):
        from agente_cursos.agente import repartir
        en = self.neutro(url="https://ejemplo.edu/en", idioma="en")

        reparto = repartir([en], 4)

        assert [c.url for c, _ in reparto[3]] == [en.url]
        assert reparto[1] == [] and reparto[2] == []


class TestNivelesPorFuente:
    def test_una_fuente_en_ingles_solo_alimenta_experto(self):
        from agente_cursos.agente import niveles_para
        from agente_cursos.fuentes.mit_learn import MITLearn

        assert niveles_para(MITLearn()) == (3,)

    def test_una_fuente_mixta_alimenta_los_tres(self):
        from agente_cursos.agente import niveles_para

        assert niveles_para(GitHub()) == (1, 2, 3)

    def test_la_pasada_de_una_fuente_en_ingles_solo_rellena_experto(self):
        from agente_cursos.agente import recorrer_huecos

        class FuenteInglesa(FuenteFalsa):
            idioma_catalogo = "en"

            @property
            def nombre(self):
                return "mit_learn"

        propuestas = recorrer_huecos(FuenteInglesa([curso(idioma="en")]), [4])

        assert set(propuestas) == {(4, 3)}

    def test_la_linea_de_comandos_recorre_todas_las_fuentes(self, capsys):
        from agente_cursos.__main__ import main
        a, b = FuenteFalsa([]), FuenteFalsa([])

        main(["--simular", "--ramas", "4"], fuentes=[a, b])

        assert a.consultas and b.consultas


class TestMismoCursoOtraEdicion:
    """
    DEFECTO REAL, MIT en Ciberseguridad: "Advanced Topics in Cryptography"
    salia dos veces. Son dos ediciones del mismo curso en OpenCourseWare, con
    URL distinta, y la deduplicacion por URL no las junta. Para el alumno es
    el mismo curso.
    """

    def test_dos_ediciones_del_mismo_curso_ocupan_una_sola_plaza(self):
        from agente_cursos.agente import repartir
        a = curso(url="https://ocw.mit.edu/2014", titulo="Advanced Topics in Cryptography",
                  descripcion=None, idioma="en", vistas=10)
        b = curso(url="https://ocw.mit.edu/2020", titulo="Advanced topics in cryptography ",
                  descripcion=None, idioma="en", vistas=5000)

        colocados = [c for lista in repartir([a, b], 4).values() for c, _ in lista]

        assert len(colocados) == 1

    def test_se_queda_con_la_de_mejor_nota(self):
        from agente_cursos.agente import repartir
        peor = curso(url="https://ocw.mit.edu/2014", titulo="Curso de hacking",
                     descripcion=None, vistas=1)
        mejor = curso(url="https://ocw.mit.edu/2020", titulo="Curso de hacking",
                      descripcion=None, vistas=100000)

        colocados = [c.url for lista in repartir([peor, mejor], 4).values() for c, _ in lista]

        assert colocados == [mejor.url]
