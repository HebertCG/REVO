"""
Pruebas del motor adaptativo.

Hay dos niveles y los dos hacen falta:

  1. Las piezas sueltas: que la creencia se actualice bien, que la EIG no
     sea negativa, que la parada mire el puesto correcto.

  2. LA SIMULACION. Se generan alumnos sinteticos de una rama conocida, se
     les hace responder segun el propio modelo, y se comprueba que el motor
     los encuentra. Es lo unico que dice si todo esto sirve para algo: las
     piezas pueden estar bien y el conjunto no converger.

La prueba que mas importa es `test_encuentra_la_rama_del_alumno_simulado`.
Si esa falla, el motor no funciona por mucho que las demas pasen.

Y hay una segunda igual de importante por lo contrario:
`test_aguanta_a_quien_responde_sin_leer`. Un motor validado solo contra su
propio generador no demuestra nada; hay que medir tambien que pasa cuando el
supuesto se rompe.
"""
import random

import pytest

from motor_adaptativo import artefacto as art
from motor_adaptativo import calidad as cal
from motor_adaptativo import creencia as cr
from motor_adaptativo import parada, seleccion

N_RAMAS = 10


@pytest.fixture(scope="module")
def modelo():
    try:
        return art.cargar()
    except art.ArtefactoInvalido as exc:
        pytest.skip(str(exc))


def responder_como(rama: int, clave: str, modelo: dict, rng: random.Random) -> int:
    """
    Simula la respuesta de un alumno de `rama` al item `clave`.

    Se muestrea DE la verosimilitud del propio modelo, asi que el alumno
    esta bien especificado: es el caso optimista. Sirve para comprobar que
    el motor converge cuando el supuesto se cumple; el caso adverso lo mide
    `test_aguanta_a_quien_responde_sin_leer`.
    """
    import math
    tabla = art.tabla_de(modelo, clave)
    probabilidades = [math.exp(x) for x in tabla[rama - 1]]
    return rng.choices(range(len(probabilidades)), weights=probabilidades)[0]


def simular(rama: int, modelo: dict, semilla: int, t_max: int = 15,
            aleatorio: bool = False) -> tuple[cr.Creencia, list]:
    """Ejecuta una sesion entera. `aleatorio=True` para el brazo de control."""
    rng = random.Random(semilla)
    estado = cr.inicial(N_RAMAS)
    historial = [cr.posterior(estado)]

    for _ in range(t_max):
        if aleatorio:
            posibles = seleccion.candidatas(estado, modelo)
            if not posibles:
                break
            clave = rng.choice(posibles)
            decision = seleccion.Decision(clave, "x", 0, 0.0, (), len(posibles))
        else:
            decision = seleccion.elegir(estado, modelo, rng)
            if decision is None:
                break
            clave = decision.clave

        respuesta = responder_como(rama, clave, modelo, rng)
        meta = art.meta_de(modelo, clave)
        estado = cr.actualizar(
            estado, art.tabla_de(modelo, clave), respuesta, clave,
            rama_item=meta.get("rama"), categoria=meta.get("categoria"),
        )
        historial.append(cr.posterior(estado))

    return estado, historial


class TestCreencia:
    def test_la_creencia_inicial_es_uniforme(self):
        probabilidades = cr.posterior(cr.inicial(N_RAMAS))

        assert all(abs(p - 0.1) < 1e-9 for p in probabilidades)
        assert cr.entropia(probabilidades) == pytest.approx(3.3219, abs=1e-3)

    def test_la_creencia_es_inmutable(self, modelo):
        # Cada actualizacion devuelve una creencia NUEVA. Es lo que deja la
        # secuencia entera disponible para auditar.
        inicial = cr.inicial(N_RAMAS)
        clave = "q:1001"

        nueva = cr.actualizar(inicial, art.tabla_de(modelo, clave), 4, clave, rama_item=1)

        assert inicial.n_preguntas == 0
        assert nueva.n_preguntas == 1
        assert nueva is not inicial

    def test_responder_alto_a_un_item_sube_su_rama(self, modelo):
        clave = "q:1001"  # Desarrollo de Software
        estado = cr.actualizar(
            cr.inicial(N_RAMAS), art.tabla_de(modelo, clave), 4, clave, rama_item=1)

        probabilidades = cr.posterior(estado)

        assert probabilidades[0] > 0.1   # subio sobre el uniforme

    def test_una_respuesta_repetida_no_cuenta_dos_veces(self, modelo):
        # Pasa de verdad con una conexion movil inestable. Sin esta guarda,
        # la evidencia se duplica y la posterior se corrompe en silencio.
        clave = "q:1001"
        tabla = art.tabla_de(modelo, clave)

        una = cr.actualizar(cr.inicial(N_RAMAS), tabla, 4, clave, rama_item=1)
        dos = cr.actualizar(una, tabla, 4, clave, rama_item=1)

        assert dos.n_preguntas == 1
        assert cr.posterior(dos) == cr.posterior(una)

    def test_ninguna_rama_puede_morir_del_todo(self, modelo):
        # El suelo impide que un error temprano sea irrecuperable.
        estado = cr.inicial(N_RAMAS)
        for ident in range(1001, 1011):      # diez items de la rama 1
            clave = f"q:{ident}"
            estado = cr.actualizar(estado, art.tabla_de(modelo, clave), 4, clave, rama_item=1)

        assert all(p > 0 for p in cr.posterior(estado))
        assert min(cr.posterior(estado)) >= cr.EPSILON_SUELO / N_RAMAS * 0.9

    def test_el_margen_del_tercero_es_el_que_mira_el_producto(self):
        # Top-1 clarisimo y empate en el corte del top-3: parar aqui daria
        # un tercer puesto salido de un desempate.
        p = (0.60, 0.13, 0.09, 0.09, 0.09, 0.0, 0.0, 0.0, 0.0, 0.0)

        assert cr.margen_en(p, 1) > 0.4
        assert cr.margen_en(p, 3) < 0.01


class TestSeleccion:
    def test_la_ganancia_nunca_es_negativa(self, modelo):
        # Una pregunta no puede aumentar la incertidumbre en promedio. Si
        # saliera negativa, la formula estaria mal.
        estado = cr.inicial(N_RAMAS)

        for clave in seleccion.candidatas(estado, modelo)[:30]:
            assert seleccion.eig(estado, modelo, clave) >= 0.0

    def test_la_eleccion_forzada_informa_mas_que_el_likert(self, modelo):
        # Es la razon de ser de la migracion 29: separan 0.60 frente a 0.21.
        estado = cr.inicial(N_RAMAS)
        likert = [seleccion.eig(estado, modelo, c)
                  for c in seleccion.candidatas(estado, modelo) if c.startswith("q:")]
        forzada = [seleccion.eig(estado, modelo, c)
                   for c in seleccion.candidatas(estado, modelo) if c.startswith("f:")]

        assert max(forzada) > max(likert)

    def test_no_repite_preguntas(self, modelo):
        estado, _ = simular(4, modelo, semilla=1)

        assert len(set(estado.hechas)) == len(estado.hechas)

    def test_respeta_el_tope_por_rama(self, modelo):
        # Sin tope, el motor gasta el presupuesto confirmando la rama que ya
        # lidera, que es lo contrario de lo que el alumno necesita.
        estado, _ = simular(4, modelo, semilla=7)

        assert max(estado.por_rama) <= seleccion.MAX_POR_RAMA

    def test_no_siempre_elige_la_mejor(self, modelo):
        # El sorteo entre las tres mejores evita que los 121 items se
        # reduzcan a los mismos 6 para todo el mundo. Sin eso, 115 items no
        # se preguntarian nunca y no habria datos para recalibrarlos.
        primeras = {
            seleccion.elegir(cr.inicial(N_RAMAS), modelo, random.Random(s)).clave
            for s in range(20)
        }

        assert len(primeras) > 1

    def test_la_decision_guarda_por_que(self, modelo):
        # "¿Por que le hizo esa pregunta a ese alumno?" es la pregunta de la
        # sustentacion. Esto es la respuesta.
        decision = seleccion.elegir(cr.inicial(N_RAMAS), modelo, random.Random(3))

        assert decision.eig > 0
        assert len(decision.top_candidatas) == 5
        assert decision.n_factibles > 100


class TestParada:
    def test_no_para_antes_del_minimo(self, modelo):
        estado, historial = simular(2, modelo, semilla=5, t_max=3)

        veredicto = parada.debe_parar(estado, historial, hay_candidatas=True)

        assert veredicto.parar is False
        assert veredicto.motivo == "minimo_no_alcanzado"

    def test_para_al_agotar_el_presupuesto(self, modelo):
        estado, historial = simular(2, modelo, semilla=5, t_max=parada.T_MAX)

        veredicto = parada.debe_parar(estado, historial, hay_candidatas=True)

        assert veredicto.parar is True
        assert veredicto.motivo == "presupuesto"

    def test_para_si_el_banco_no_tiene_nada_que_aporte(self, modelo):
        estado, historial = simular(2, modelo, semilla=5, t_max=8)

        veredicto = parada.debe_parar(estado, historial, hay_candidatas=False)

        assert veredicto.parar is True
        assert veredicto.motivo == "banco_agotado"

    def test_exige_que_el_top3_se_haya_asentado(self):
        # Sin esta condicion, una fluctuacion puntual cruza el umbral y corta
        # el test justo antes de que la creencia se estabilice.
        moviendose = [
            (0.4, 0.3, 0.2, 0.1, 0, 0, 0, 0, 0, 0),
            (0.3, 0.2, 0.1, 0.4, 0, 0, 0, 0, 0, 0),
            (0.2, 0.1, 0.4, 0.3, 0, 0, 0, 0, 0, 0),
        ]

        assert parada.top3_estable(moviendose) is False

    def test_reconoce_un_top3_estable(self):
        quieto = [(0.5, 0.2, 0.15, 0.05, 0.03, 0.02, 0.02, 0.01, 0.01, 0.01)] * 3

        assert parada.top3_estable(quieto) is True


class TestConvergencia:
    """La prueba de fuego: ¿encuentra al alumno?"""

    @pytest.mark.parametrize("rama", range(1, 11))
    def test_encuentra_la_rama_del_alumno_simulado(self, modelo, rama):
        # LA PRUEBA QUE IMPORTA. Si esta falla, el motor no sirve por muy
        # bien que esten las piezas sueltas.
        #
        # 30 semillas y umbral de 20 (67 %), no 12 y 10 (83 %). El agregado
        # medido sobre 200 sesiones es 90 % de top-3, pero una rama concreta
        # con 12 semillas fluctua entre 9 y 12: un umbral de 83 % sobre 12
        # muestras falla por ruido de muestreo, no por un defecto del motor.
        # Un margen amplio sobre mas muestras detecta una regresion real sin
        # saltar sola.
        aciertos = sum(
            1 for semilla in range(30)
            if rama in {r for r, _ in cr.top(cr.posterior(simular(rama, modelo, semilla)[0]), 3)}
        )

        assert aciertos >= 20, f"rama {rama}: solo {aciertos}/30 en el top-3"

    def test_reduce_la_incertidumbre(self, modelo):
        # Sobre la media de TODAS las ramas, no sobre una sesion ni sobre una
        # rama. Dos motivos:
        #
        #   - Una sesion suelta puede caer solo 0.86 bits segun el alumno que
        #     toque simular.
        #   - Y hay ramas mas dificiles que otras. Ciberseguridad tiene cinco
        #     vecinas por encima de 0.34 de similitud, asi que baja de media
        #     1.36 bits; Soporte, que solo tiene una, baja mucho mas.
        #
        # Medir la media global (~2.0 bits) es lo que dice si el motor reduce
        # incertidumbre; exigirsela a la rama mas dificil seria una prueba
        # que falla por el problema, no por un defecto.
        caidas = []
        for rama in range(1, 11):
            for semilla in range(4):
                _, historial = simular(rama, modelo, semilla=semilla)
                caidas.append(cr.entropia(historial[0]) - cr.entropia(historial[-1]))

        assert sum(caidas) / len(caidas) > 1.5

    def test_es_mejor_que_preguntar_al_azar(self, modelo):
        # La comparacion honesta: mismo presupuesto de 15 preguntas, mismo
        # alumno simulado, y solo cambia COMO se eligen. Si el adaptativo no
        # gana aqui, no justifica su complejidad.
        adaptativo = aleatorio = 0
        for rama in range(1, 11):
            for semilla in range(6):
                e_a, _ = simular(rama, modelo, semilla, aleatorio=False)
                e_r, _ = simular(rama, modelo, semilla, aleatorio=True)
                if cr.top(cr.posterior(e_a), 1)[0][0] == rama:
                    adaptativo += 1
                if cr.top(cr.posterior(e_r), 1)[0][0] == rama:
                    aleatorio += 1

        assert adaptativo > aleatorio, f"adaptativo {adaptativo} vs azar {aleatorio}"

    def test_aguanta_a_quien_responde_sin_leer(self, modelo):
        # Un motor bayesiano validado SOLO contra su propio generador no
        # demuestra nada. Aqui el alumno marca siempre lo mismo, rompiendo
        # el supuesto del modelo.
        #
        # No se exige que acierte: se exige que NO finja certeza. Un sistema
        # que da 95 % de confianza a quien contesto sin leer es peor que uno
        # que se equivoca admitiendolo.
        estado = cr.inicial(N_RAMAS)
        respuestas_dadas = []
        rng = random.Random(11)
        for _ in range(15):
            decision = seleccion.elegir(estado, modelo, rng)
            if decision is None:
                break
            tabla = art.tabla_de(modelo, decision.clave)
            # Siempre la misma posicion. En un Likert de cinco niveles es el
            # 4; en un item de eleccion forzada, que solo tiene dos, es la
            # opcion B. Pasar un 3 a un item binario seria un indice fuera
            # de rango: el alumno descuidado existe, pero no puede marcar
            # una casilla que no esta en pantalla.
            respuesta = min(3, len(tabla[0]) - 1)
            respuestas_dadas.append(respuesta)
            meta = art.meta_de(modelo, decision.clave)
            estado = cr.actualizar(
                estado, tabla, respuesta, decision.clave,
                rama_item=meta.get("rama"), categoria=meta.get("categoria"))

        respuestas = [r for r in respuestas_dadas]
        lectura = cal.evaluar(respuestas)

        # 1. Se detecta.
        assert lectura.veredicto == "sospechosa", f"no lo detecto: {lectura}"

        # 2. Sin atenuar, el motor declaraba 97 % de confianza a quien no
        #    leyo. Eso es peor que equivocarse: es equivocarse con seguridad.
        cruda = max(cr.posterior(estado))
        assert cruda > 0.80, "el escenario ya no reproduce el problema"

        # 3. Con la atenuacion, deja de afirmar lo que no puede saber.
        atenuada = max(cal.atenuar(cr.posterior(estado), lectura.atenuacion))
        assert atenuada < 0.80, f"sigue declarando {atenuada:.2f}"


class TestReproducibilidad:
    def test_la_misma_semilla_da_la_misma_sesion(self, modelo):
        # "¿Por que le hizo esa pregunta a ese alumno?" solo se puede
        # responder si la sesion se puede reconstruir exactamente.
        a, _ = simular(6, modelo, semilla=42)
        b, _ = simular(6, modelo, semilla=42)

        assert a.hechas == b.hechas
        assert cr.posterior(a) == cr.posterior(b)

    def test_semillas_distintas_dan_sesiones_distintas(self, modelo):
        a, _ = simular(6, modelo, semilla=1)
        b, _ = simular(6, modelo, semilla=2)

        assert a.hechas != b.hechas
