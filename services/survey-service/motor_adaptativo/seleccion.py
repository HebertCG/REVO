"""
seleccion.py — Elige la siguiente pregunta: la que mas reduce la duda.

EL CRITERIO

Ganancia de informacion esperada (EIG), en bits:

    EIG(q) = H(creencia_actual) - SUMA_k  P(respuesta=k) * H(creencia si sale k)

Es decir: por cada respuesta posible se calcula como quedaria la creencia, se
mide su entropia, y se promedia ponderando por lo probable que es esa
respuesta. La pregunta que deja la entropia esperada mas baja es la que mas
ensena.

Un item que casi seguro se responde igual desde todas las ramas tiene
EIG ~ 0: no distingue nada, y el motor no lo hace. Eso es lo que sustituye
al `ORDER BY random()` del cuestionario anterior.

COSTE

Por candidata: 10 ramas x 5 niveles de lecturas de tabla, mas 5 entropias de
10 terminos. Unas 150 operaciones. Con 121 candidatas, ~18 000. En Python
puro son 5-15 ms; un viaje a PostgreSQL son 10-30. NO hay que optimizarlo, y
por eso no se optimiza.

POR QUE NO SE ELIGE EL MEJOR

Se elige al azar entre los TRES mejores (randomesque, Kingsbury y Zara 1989).
Tres motivos, y el tercero es el que mas importa:

  1. Sin esto, los 121 items se reducen a los mismos 6 para todo el mundo.
  2. El banco se sobreexpone: quien haga el test dos veces ve lo mismo.
  3. CRITICO PARA LA TESIS: un motor puramente voraz produce un dataset
     degenerado. Si 115 items no se preguntan nunca, no hay datos con los
     que recalibrar sus parametros, y el modelo se queda congelado en el
     prior experto para siempre.

Y UN TOPE POR RAMA

Sin el, el motor puede gastar las 15 preguntas confirmando la rama que ya
lidera. Eso sube la confianza declarada sin comprobar las alternativas, que
es justo lo contrario de lo que el alumno necesita.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from motor_adaptativo import creencia as cr

#: Cuantas preguntas como mucho de una misma rama.
MAX_POR_RAMA = 4

#: Entre cuantas de las mejores se sortea.
TOP_SORTEO = 3

#: Por debajo de esta ganancia, la pregunta no aporta y se descarta.
EIG_MINIMA = 0.005


@dataclass(frozen=True)
class Decision:
    """La pregunta elegida y por que. Se persiste para poder auditarla."""

    clave: str                 # "q:1001" o "f:4"
    tipo: str                  # "likert" | "eleccion"
    item_id: int
    eig: float
    #: Las cinco mejores con su EIG. Es lo que permite responder en una
    #: sustentacion a "por que le hizo ESA pregunta a ESE alumno".
    top_candidatas: tuple[tuple[str, float], ...]
    n_factibles: int


def _entropia_esperada(
    probabilidades: tuple[float, ...],
    log_verosimilitud: list[list[float]],
    peso: float,
) -> float:
    """Entropia media de la creencia tras responder este item."""
    n_respuestas = len(log_verosimilitud[0])
    total = 0.0

    for k in range(n_respuestas):
        # Posterior hipotetica si la respuesta fuera k.
        sin_normalizar = [
            p * math.exp(peso * log_verosimilitud[c][k])
            for c, p in enumerate(probabilidades)
        ]
        masa = sum(sin_normalizar)
        if masa <= 0:
            continue

        hipotetica = [x / masa for x in sin_normalizar]
        total += masa * (-sum(q * math.log2(q) for q in hipotetica if q > 0))

    return total


def eig(estado: cr.Creencia, artefacto: dict, clave: str) -> float:
    """Ganancia de informacion esperada de un item, en bits."""
    probabilidades = cr.posterior(estado)
    actual = cr.entropia(probabilidades)

    tabla, meta = _buscar(artefacto, clave)
    if tabla is None:
        return 0.0

    peso = 1.0
    if "rama" in meta:
        peso = cr.LAMBDA_DESCUENTO ** estado.por_rama[meta["rama"] - 1]

    return max(0.0, actual - _entropia_esperada(probabilidades, tabla, peso))


def _buscar(artefacto: dict, clave: str) -> tuple[list[list[float]] | None, dict]:
    """Localiza la tabla de verosimilitudes y los metadatos de un item."""
    tipo, _, ident = clave.partition(":")
    bloque = artefacto["likert"] if tipo == "q" else artefacto["eleccion_forzada"]
    posicion = bloque["indice"].get(ident)
    if posicion is None:
        return None, {}
    return bloque["log_verosimilitud"][posicion], bloque["meta"][posicion]


def candidatas(estado: cr.Creencia, artefacto: dict) -> list[str]:
    """
    Items que el motor puede preguntar ahora.

    Cuatro filtros, en orden:
      1. Sin repetir.
      2. Tope por rama.
      3. Cobertura de categorias si queda poco presupuesto.
      4. Los de eleccion forzada solo cuando sus DOS ramas siguen vivas: un
         item que separa Infraestructura de Ciberseguridad no aporta nada si
         ninguna de las dos esta en juego.
    """
    hechas = set(estado.hechas)
    probabilidades = cr.posterior(estado)
    # Una rama esta "viva" si su probabilidad supera la mitad de la uniforme.
    umbral_vivo = 0.5 / len(probabilidades)

    resultado = []

    for ident, posicion in artefacto["likert"]["indice"].items():
        clave = f"q:{ident}"
        if clave in hechas:
            continue
        meta = artefacto["likert"]["meta"][posicion]
        if estado.por_rama[meta["rama"] - 1] >= MAX_POR_RAMA:
            continue
        resultado.append(clave)

    for ident, posicion in artefacto["eleccion_forzada"]["indice"].items():
        clave = f"f:{ident}"
        if clave in hechas:
            continue
        meta = artefacto["eleccion_forzada"]["meta"][posicion]
        if (probabilidades[meta["spec_a"] - 1] < umbral_vivo
                and probabilidades[meta["spec_b"] - 1] < umbral_vivo):
            continue
        resultado.append(clave)

    # Orden estable por clave: sin esto, el recorrido de un diccionario
    # podria variar entre procesos y el replay dejaria de ser reproducible.
    return sorted(resultado)


def elegir(
    estado: cr.Creencia,
    artefacto: dict,
    rng: random.Random,
) -> Decision | None:
    """
    La siguiente pregunta, o None si ya no queda nada que aporte.

    El desempate final es por clave ascendente, no por orden de aparicion:
    es lo que hace que el replay con la misma semilla reproduzca exactamente
    la misma sesion.
    """
    factibles = candidatas(estado, artefacto)
    if not factibles:
        return None

    puntuadas = [(clave, eig(estado, artefacto, clave)) for clave in factibles]
    puntuadas = [(c, g) for c, g in puntuadas if g >= EIG_MINIMA]
    if not puntuadas:
        return None

    puntuadas.sort(key=lambda par: (-par[1], par[0]))
    mejores = puntuadas[:TOP_SORTEO]
    clave, ganancia = mejores[rng.randrange(len(mejores))]

    tipo, _, ident = clave.partition(":")
    return Decision(
        clave=clave,
        tipo="likert" if tipo == "q" else "eleccion",
        item_id=int(ident),
        eig=round(ganancia, 6),
        top_candidatas=tuple((c, round(g, 6)) for c, g in puntuadas[:5]),
        n_factibles=len(factibles),
    )
