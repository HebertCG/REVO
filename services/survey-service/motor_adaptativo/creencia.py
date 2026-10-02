"""
creencia.py — El estado del motor adaptativo: que rama encaja, y cuanto.

QUE ES UNA CREENCIA

Una distribucion de probabilidad sobre las diez ramas, que empieza uniforme
y se actualiza con cada respuesta. Es lo que sustituye al "sumar puntos por
rama" del cuestionario anterior.

La diferencia no es cosmetica. Sumando puntos, la respuesta a una pregunta
de Ciberseguridad solo informa de Ciberseguridad. Con una creencia y la
matriz de similitud, esa misma respuesta mueve a la vez Infraestructura
(0.61), QA (0.57) e Investigacion (0.41). Una pregunta informa sobre un
GRUPO de ramas, que es exactamente como Akinator descarta veinte personajes
de una vez.

TODO EN LOG-ESPACIO

Las probabilidades se multiplican al acumular evidencia. Con 15 respuestas y
verosimilitudes de ~0.2, el producto baja de 1e-10 y en coma flotante se
convierte en cero: todas las ramas empatan a cero y la creencia se pierde.
En log-espacio los productos son sumas y eso no pasa.

LA CREENCIA ES INMUTABLE

`frozen=True` a proposito, por la regla de inmutabilidad del proyecto y
porque aqui tiene una consecuencia concreta: cada actualizacion devuelve una
creencia NUEVA, asi que la secuencia entera queda disponible para auditar
por que se hizo cada pregunta. Con un objeto mutable solo quedaria el estado
final.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

#: Descuento por repetir rama. Las diez preguntas de una misma rama estan
#: correlacionadas entre si: quien dijo que le gusta programar dira que le
#: gusta depurar. Tratarlas como independientes multiplica evidencia que en
#: realidad es la misma, y produce posteriores de 0.999 que son FALSAS.
#:
#: Con lambda = 0.75, la segunda pregunta de una rama pesa 0.75, la tercera
#: 0.56, la cuarta 0.42. Efecto secundario deseable: empuja al selector a
#: diversificar en vez de insistir.
LAMBDA_DESCUENTO = 0.75

#: Suelo de probabilidad tras normalizar. Sin el, una rama que recibe varias
#: respuestas malas cae a 1e-12 y ya no puede recuperarse aunque las
#: siguientes respuestas la favorezcan: un error temprano seria definitivo.
EPSILON_SUELO = 0.01


@dataclass(frozen=True)
class Creencia:
    """Estado del motor. Serializa a ~600 bytes."""

    #: Log-posterior sin normalizar, una entrada por rama.
    log_post: tuple[float, ...]
    #: Claves de los items ya usados: "q:1001" (Likert) o "f:4" (eleccion).
    hechas: tuple[str, ...] = ()
    #: Cuantas preguntas se han hecho ya de cada rama. Alimenta el descuento
    #: y el tope por rama del selector.
    por_rama: tuple[int, ...] = ()
    #: Cuantas de cada categoria, para la cobertura del selector.
    por_categoria: tuple[tuple[str, int], ...] = ()

    @property
    def n_ramas(self) -> int:
        return len(self.log_post)

    @property
    def n_preguntas(self) -> int:
        return len(self.hechas)


def inicial(n_ramas: int = 10) -> Creencia:
    """
    Creencia de partida: uniforme.

    Uniforme y no la distribucion historica de matriculas de la facultad,
    aunque se tenga. Un prior basado en lo que la gente elige hoy empuja a
    cada alumno hacia lo que ya es mayoritario, y eso en una herramienta de
    orientacion vocacional es un sesgo de statu quo dificil de defender.
    """
    return Creencia(
        log_post=tuple([0.0] * n_ramas),
        por_rama=tuple([0] * n_ramas),
    )


def actualizar(
    creencia: Creencia,
    log_verosimilitud: list[list[float]],
    respuesta: int,
    clave: str,
    rama_item: int | None = None,
    categoria: str | None = None,
) -> Creencia:
    """
    Incorpora una respuesta y devuelve una creencia nueva.

    `log_verosimilitud[c][k]` es log P(respuesta = k | rama = c), del
    artefacto. `respuesta` es el indice de la respuesta dada (0..4 en Likert,
    0 o 1 en eleccion forzada).

    `rama_item` es la rama a la que apunta el item, y solo la tienen los
    Likert: un item de eleccion forzada apunta a dos, asi que no descuenta
    por rama.
    """
    if clave in creencia.hechas:
        # Idempotencia: reenviar la misma respuesta no debe contar dos veces.
        # Pasa de verdad con una conexion movil inestable, y sin esta guarda
        # la evidencia se duplica y la posterior se corrompe en silencio.
        return creencia

    peso = 1.0
    por_rama = list(creencia.por_rama)
    if rama_item is not None:
        vistas = por_rama[rama_item - 1]
        peso = LAMBDA_DESCUENTO ** vistas
        por_rama[rama_item - 1] = vistas + 1

    nuevo_log = tuple(
        actual + peso * log_verosimilitud[c][respuesta]
        for c, actual in enumerate(creencia.log_post)
    )

    categorias = dict(creencia.por_categoria)
    if categoria:
        categorias[categoria] = categorias.get(categoria, 0) + 1

    return replace(
        creencia,
        log_post=nuevo_log,
        hechas=creencia.hechas + (clave,),
        por_rama=tuple(por_rama),
        por_categoria=tuple(sorted(categorias.items())),
    )


def posterior(creencia: Creencia) -> tuple[float, ...]:
    """
    Probabilidad normalizada por rama, con suelo.

    El suelo se aplica DESPUES de normalizar y se renormaliza: mezcla la
    distribucion con una uniforme al 1 %. Es lo que impide que una rama
    descartada temprano sea irrecuperable.
    """
    maximo = max(creencia.log_post)
    exponenciales = [math.exp(x - maximo) for x in creencia.log_post]
    total = sum(exponenciales)
    n = len(exponenciales)

    return tuple(
        (1 - EPSILON_SUELO) * (x / total) + EPSILON_SUELO / n
        for x in exponenciales
    )


def entropia(probabilidades: tuple[float, ...]) -> float:
    """
    Entropia de Shannon en bits. 0 = certeza, log2(10) = 3.32 = ni idea.

    Es la medida que el selector quiere reducir: cada pregunta se elige para
    bajarla lo mas posible.
    """
    return -sum(p * math.log2(p) for p in probabilidades if p > 0)


def margen_en(probabilidades: tuple[float, ...], posicion: int) -> float:
    """
    Diferencia entre la rama en la posicion k y la k+1 (1-indexado).

    `margen_en(p, 3)` es el margen entre la 3.a y la 4.a, y es el que decide
    cuando parar: el producto entrega un TOP-3, asi que lo que el alumno ve
    depende de si el puesto 3 esta separado del 4, no de si el 1 esta
    separado del 2. Puede haber un top-1 clarisimo y un empate caotico justo
    en el corte.
    """
    ordenadas = sorted(probabilidades, reverse=True)
    if posicion < 1 or posicion >= len(ordenadas):
        return 1.0
    return ordenadas[posicion - 1] - ordenadas[posicion]


def top(probabilidades: tuple[float, ...], cuantas: int = 3) -> list[tuple[int, float]]:
    """
    Las `cuantas` ramas mas probables como (rama_id, probabilidad).

    Los empates se rompen por id ascendente, no por orden de diccionario:
    un ranking que cambia entre dos ejecuciones con los mismos datos no es
    un diagnostico.
    """
    indexadas = [(i + 1, p) for i, p in enumerate(probabilidades)]
    return sorted(indexadas, key=lambda par: (-par[1], par[0]))[:cuantas]
