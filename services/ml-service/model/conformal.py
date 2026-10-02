"""
conformal.py — Conjuntos de prediccion con cobertura garantizada.

PROBLEMA QUE RESUELVE

El sistema siempre devuelve exactamente tres ramas, pase lo que pase. Ese
numero es una decision de diseno de pantalla, no una consecuencia de los
datos: para un alumno con un perfil clarisimo sobran dos, y para uno
ambiguo tres se quedan cortas.

La prediccion conformal invierte la pregunta. En vez de "dame las 3 mejores",
pregunta: "¿cuantas ramas hacen falta para estar razonablemente seguros de
que la correcta esta dentro?". El tamano del conjunto pasa a ser la SALIDA, y
con ello una medida de incertidumbre que el alumno entiende sin explicacion.

EL METODO: SPLIT CONFORMAL CON APS

APS (Adaptive Prediction Sets, Romano et al. 2020):

  1. Sobre una particion de calibracion que el modelo NO vio, para cada
     muestra se ordenan las clases por probabilidad y se acumula hasta llegar
     a la clase verdadera. Esa suma es la "puntuacion de no conformidad": si
     la clase correcta estaba la primera, es baja; si estaba la ultima, alta.

  2. El umbral q es el cuantil (1-alpha) corregido de esas puntuaciones.

  3. Para un alumno nuevo se acumulan probabilidades de mayor a menor y se
     corta al superar q.

Se aplica DESPUES de calibrar: APS trabaja sobre probabilidades, y si estan
infladas el conjunto sale sistematicamente pequeno.

LO QUE GARANTIZA, SIN ADORNOS

Cobertura MARGINAL: entre muchos alumnos, la rama correcta cae dentro del
conjunto el (1-alpha) de las veces. NO garantiza nada sobre un alumno
concreto, ni por subgrupos.

Y sobre datos sinteticos la garantia es sobre el PROCESO GENERADOR, no sobre
personas. Decirlo es parte del rigor.
"""
from __future__ import annotations

import numpy as np

#: 1 - alpha es la cobertura objetivo. 0.10 -> la rama correcta cae dentro
#: del conjunto el 90 % de las veces.
ALPHA = 0.10

#: Minimo de muestras para que el cuantil signifique algo. Con n pequeno el
#: cuantil corregido se va a 1.0 y el conjunto pasa a ser las 10 clases:
#: tecnicamente correcto e inutil en pantalla.
MINIMO_CALIBRACION = 100

#: Tamanos que cambian el mensaje al alumno.
MAXIMO_PARA_MOSTRAR = 3


def puntuaciones_aps(
    probabilidades: np.ndarray,
    y_indices: np.ndarray,
    aleatorizar: bool = True,
    semilla: int = 42,
) -> np.ndarray:
    """
    Masa de probabilidad acumulada hasta la clase verdadera, inclusive.

    Es la puntuacion de no conformidad: cuanto mayor, peor colocada estaba la
    clase correcta segun el modelo.

    POR QUE SE ALEATORIZA

    Sin aleatorizar, APS SOBRE-CUBRE. Medido en este proyecto: con una
    cobertura objetivo del 90 % la real salia del 100 %, y el conjunto medio
    de 3,06 ramas sobre 10.

    El motivo es que la puntuacion incluye ENTERA la probabilidad de la clase
    verdadera. Al ser una variable discreta, el cuantil se queda siempre por
    encima de lo necesario. Sobre-cubrir no es incorrecto (la garantia se
    cumple de sobra), pero devuelve conjuntos mas grandes de lo que los datos
    justifican, y eso en pantalla significa decirle "encajas en varias ramas"
    a alumnos cuyo perfil si estaba definido.

    La correccion estandar (Romano et al. 2020) resta una fraccion aleatoria
    de esa ultima probabilidad, lo que suaviza la discretizacion y ajusta la
    cobertura a la nominal.
    """
    orden = np.argsort(-probabilidades, axis=1)
    ordenadas = np.take_along_axis(probabilidades, orden, axis=1)
    acumuladas = np.cumsum(ordenadas, axis=1)

    # Posicion en la que quedo la clase verdadera de cada fila.
    posicion = np.argmax(orden == y_indices[:, None], axis=1)
    filas = np.arange(len(y_indices))
    puntuaciones = acumuladas[filas, posicion]

    if aleatorizar:
        generador = np.random.default_rng(semilla)
        u = generador.random(len(y_indices))
        puntuaciones = puntuaciones - u * ordenadas[filas, posicion]

    return puntuaciones


def ajustar_umbral(
    probabilidades: np.ndarray,
    y_indices: np.ndarray,
    alpha: float = ALPHA,
    aleatorizar: bool = True,
) -> dict:
    """
    Calcula el umbral q sobre la particion de calibracion.

    El cuantil lleva la correccion de muestra finita ceil((n+1)(1-alpha))/n,
    que es lo que convierte esto en una garantia y no en una aproximacion.
    Sin ella, la cobertura real queda por debajo de la nominal.
    """
    n = len(y_indices)
    if n < MINIMO_CALIBRACION:
        return {
            "q": 1.0,
            "alpha": alpha,
            "n_calibracion": n,
            "suficientes_muestras": False,
            "aviso": (
                f"Solo {n} muestras de calibracion (minimo {MINIMO_CALIBRACION}). "
                "El umbral se fija en 1.0, que devuelve todas las clases: es "
                "correcto pero no informativo. No presentarlo como cobertura."
            ),
        }

    puntuaciones = puntuaciones_aps(probabilidades, y_indices, aleatorizar=aleatorizar)
    nivel = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return {
        "q": float(np.quantile(puntuaciones, nivel, method="higher")),
        "alpha": alpha,
        "n_calibracion": n,
        "suficientes_muestras": True,
        "cobertura_objetivo": round(1 - alpha, 4),
        "aleatorizado": aleatorizar,
    }


def conjunto_prediccion(probabilidades: np.ndarray, q: float) -> list[int]:
    """
    Indices de clase del conjunto, de mayor a menor probabilidad.

    Siempre devuelve al menos una: un conjunto vacio no es una respuesta que
    se pueda poner en pantalla.
    """
    p = np.asarray(probabilidades, dtype=float).ravel()
    orden = np.argsort(-p)
    acumulada = 0.0
    elegidas = []
    for indice in orden:
        elegidas.append(int(indice))
        acumulada += p[indice]
        if acumulada >= q:
            break
    return elegidas


def evaluar_cobertura(
    probabilidades: np.ndarray, y_indices: np.ndarray, q: float
) -> dict:
    """
    Comprueba sobre un conjunto de prueba que la cobertura real cuadra.

    Es la verificacion que cierra el circulo: un umbral sin medir la
    cobertura que produce es una promesa sin comprobar.
    """
    dentro, tamanos = [], []
    for fila, verdadera in zip(probabilidades, y_indices):
        conjunto = conjunto_prediccion(fila, q)
        dentro.append(int(verdadera) in conjunto)
        tamanos.append(len(conjunto))

    return {
        "cobertura_real": round(float(np.mean(dentro)), 4),
        "tamano_medio": round(float(np.mean(tamanos)), 3),
        "tamano_mediano": int(np.median(tamanos)),
        "pct_conjunto_unitario": round(float(np.mean(np.array(tamanos) == 1)), 4),
        "n_evaluacion": int(len(y_indices)),
    }


def decidir_presentacion(conjunto: list[int]) -> dict:
    """
    Traduce el tamano del conjunto a lo que hace la pantalla.

    Es la regla de producto, y vive aqui y no en el router para que sea una
    sola y este junto al metodo que la sostiene.
    """
    tamano = len(conjunto)

    if tamano == 1:
        return {
            "modo": "resultado_unico",
            "mostrar_n": 1,
            "mensaje": "Tus respuestas apuntan claramente a una rama.",
        }
    if tamano <= MAXIMO_PARA_MOSTRAR:
        return {
            "modo": "varias_compatibles",
            "mostrar_n": tamano,
            "mensaje": (
                f"Tu perfil encaja de forma parecida en {tamano} ramas. "
                "Merece la pena mirarlas todas antes de decidir."
            ),
        }
    return {
        "modo": "insuficiente",
        "mostrar_n": MAXIMO_PARA_MOSTRAR,
        "mensaje": (
            "Con estas respuestas todavía no podemos distinguir tu rama con "
            "confianza. Te mostramos las mas probables, pero conviene repetir "
            "la evaluación o responder más preguntas."
        ),
    }


def ajustar_por_lectura(presentacion: dict, diagnostico: dict) -> dict:
    """
    Si el perfil es poco visto, la pantalla pide cautela.

    El conjunto conformal puede tener UNA rama y el perfil ser raro a la vez:
    la cobertura se garantiza en promedio, sobre alumnos como los del
    dataset, y un perfil poco visto es justo el que no se parece a ellos.
    Decir entonces "tus respuestas apuntan claramente a una rama" seria
    afirmar una certeza que el propio sistema acaba de poner en duda.

    La rama mostrada no cambia: cambia cuanta seguridad se declara.
    Devuelve un diccionario NUEVO.
    """
    if diagnostico.get("lectura") != "perfil_poco_visto":
        return {**presentacion, "cautela": False}

    return {
        **presentacion,
        "cautela": True,
        "mensaje": (
            "Tus respuestas apuntan a esta rama, pero tu perfil se parece poco "
            "a los que el sistema conoce. Tómalo como orientación, no como "
            "veredicto, y contrástalo con las demás ramas."
        ),
    }
