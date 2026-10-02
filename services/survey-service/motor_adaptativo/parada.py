"""
parada.py — Cuando el motor tiene suficiente.

EL CRITERIO CORRECTO MIRA EL PUESTO 3, NO EL 1

Es el punto que mas facil se pasa por alto. REVO entrega un TOP-3, asi que
la frontera que decide lo que el alumno ve no es la que separa la 1.a rama
de la 2.a, sino la que separa la 3.a de la 4.a.

Puede haber un top-1 clarisimo y un empate caotico justo en el corte:

    0.60  0.13  0.09  0.09  0.09  ...

Ahi el margen 1-2 es 0.47 (parece resuelto) pero el margen 3-4 es 0.00: las
posiciones 3, 4 y 5 son intercambiables, y el alumno va a ver un top-3 cuyo
tercer puesto es arbitrario. Parar ahi seria presentar como resultado algo
que salio de un desempate.

EL PREDICADO

    parar = [ t >= T_MIN  Y  top3_estable  Y  (entropia baja O margen ancho) ]
            O  [ ninguna pregunta aporta ya ]
            O  [ t >= T_MAX ]

`top3_estable` exige que el conjunto de las tres primeras no haya cambiado
en las ultimas preguntas. Sin esa condicion, una fluctuacion puntual puede
cruzar el umbral y cortar el test justo antes de que la creencia se asiente.

SOBRE T_MAX = 15

No es un numero redondo: es EXACTAMENTE el numero de preguntas de la fase 2
actual. Eso permite comparar adaptativo-15 contra aleatorio-15 sobre el
mismo presupuesto, que es la unica comparacion limpia. Si el adaptativo
usara 10 y el aleatorio 15, no se sabria si gana por el metodo o por haber
preguntado distinto.
"""
from __future__ import annotations

from dataclasses import dataclass

from motor_adaptativo import creencia as cr

#: Minimo de preguntas. Por debajo, el alumno percibe que "no le han
#: preguntado nada" aunque el sistema ya lo tenga claro. Es validez aparente,
#: no estadistica, y aun asi importa: un test que termina en cuatro
#: preguntas no se cree.
T_MIN = 6

#: Tope. Paridad exacta con la fase 2 actual, para poder comparar.
T_MAX = 15

#: Entropia por debajo de la cual se considera resuelto, en bits. 1.0 bit
#: equivale a una perplejidad de 2: como si quedaran dos ramas en juego.
H_PARADA = 1.0

#: Margen minimo entre la 3.a y la 4.a para dar el top-3 por firme.
MARGEN_34 = 0.08

#: Cuantas preguntas seguidas tiene que mantenerse el mismo top-3.
ESTABILIDAD = 3


@dataclass(frozen=True)
class Veredicto:
    parar: bool
    motivo: str
    entropia: float
    margen_34: float


def top3_estable(historial: list[tuple[float, ...]]) -> bool:
    """
    ¿El conjunto de las tres primeras se repite en las ultimas rondas?

    Se compara el CONJUNTO, no el orden: que la 2.a y la 3.a se intercambien
    no significa que la creencia siga moviendose de forma relevante, porque
    las tres se van a mostrar igual.
    """
    if len(historial) < ESTABILIDAD:
        return False

    conjuntos = [
        frozenset(rama for rama, _ in cr.top(p, 3))
        for p in historial[-ESTABILIDAD:]
    ]
    return len(set(conjuntos)) == 1


def debe_parar(
    estado: cr.Creencia,
    historial: list[tuple[float, ...]],
    hay_candidatas: bool,
    t_max: int = T_MAX,
) -> Veredicto:
    """Decide si el cuestionario termina, y deja dicho por que."""
    probabilidades = cr.posterior(estado)
    h = cr.entropia(probabilidades)
    m34 = cr.margen_en(probabilidades, 3)
    t = estado.n_preguntas

    if t >= t_max:
        return Veredicto(True, "presupuesto", h, m34)

    if not hay_candidatas:
        # El banco ya no tiene nada que aporte. Parar aqui es mas honesto que
        # seguir preguntando cosas que no cambian la creencia.
        return Veredicto(True, "banco_agotado", h, m34)

    if t < T_MIN:
        return Veredicto(False, "minimo_no_alcanzado", h, m34)

    if not top3_estable(historial):
        return Veredicto(False, "top3_todavia_se_mueve", h, m34)

    if h <= H_PARADA:
        return Veredicto(True, "entropia", h, m34)

    if m34 >= MARGEN_34:
        return Veredicto(True, "margen_top3", h, m34)

    return Veredicto(False, "sigue_indeciso", h, m34)
