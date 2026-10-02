"""
calibracion.py — Que el porcentaje que ve el alumno signifique algo.

PROBLEMA QUE RESUELVE

La pantalla de resultado muestra "87 % de confianza" tomado tal cual de
`clf.predict_proba`. Eso NO es una probabilidad honesta, por dos motivos que
se acumulan:

  1. El dataset es sintetico y su etiqueta es casi siempre argmax(aff), asi
     que el modelo aprende a estar segurisimo de todo.

  2. `class_weight="balanced"` (trainer.py) deforma a proposito la superficie
     de decision respecto a las proporciones reales. Es correcto para no
     ignorar las clases raras, pero desplaza las probabilidades.

Un 87 % que acierta el 60 % de las veces es una mentira con formato de dato,
y en una herramienta de orientacion vocacional esa mentira empuja decisiones
de carrera.

QUE ES CALIBRAR

Ajustar las probabilidades para que, entre todas las veces que el sistema
dice 80 %, acierte el 80 %. No cambia QUE clase se predice (la temperatura es
monotona, asi que el argmax no se mueve): cambia CUANTA confianza se declara.

POR QUE TEMPERATURE SCALING Y NO PLATT NI ISOTONICA

Un unico parametro T para las 10 clases:

    p = softmax(logits / T)

  * T > 1 -> aplana: el modelo estaba demasiado seguro (el caso habitual).
  * T < 1 -> afila: estaba demasiado dudoso.
  * T = 1 -> no cambia nada.

Con ~1000 filas y 10 clases, Platt por clase son 20 parametros y la
isotonica es no parametrica y necesita bastante mas por clase. Un solo
parametro es lo unico que no sobreajusta con esta cantidad de datos, y es el
metodo estandar desde Guo et al. (2017), asi que se puede citar.

ADVERTENCIA QUE TIENE QUE CONSTAR EN LA MEMORIA

Calibrar sobre un dataset donde la etiqueta es argmax(aff) por construccion
es CALIBRACION CIRCULAR. El ECE bajo que salga de ahi no dice nada sobre
alumnos reales. `evaluar_calibracion` devuelve el aviso junto a las cifras
para que no se reporten sueltas.
"""
from __future__ import annotations

import numpy as np

#: Rango de busqueda de la temperatura. Por debajo de 0.05 el softmax se
#: satura y la verosimilitud deja de ser informativa; por encima de 20 la
#: distribucion es practicamente uniforme. Fuera de ese rango, el problema no
#: es la calibracion.
T_MINIMA = 0.05
T_MAXIMA = 20.0

#: Numero de particiones del diagrama de fiabilidad.
N_BINS = 10

#: Umbrales de aceptacion (Guo et al. y practica habitual).
ECE_OBJETIVO = 0.05
MCE_OBJETIVO = 0.15

#: Minimo de muestras para que calibrar signifique algo. Por debajo, la
#: temperatura ajusta ruido y es peor que no calibrar.
MINIMO_MUESTRAS = 50


def ajustar_temperatura(logits: np.ndarray, y: np.ndarray) -> float:
    """
    Busca la T que minimiza la log-verosimilitud negativa.

    Busqueda ternaria sobre log(T), no descenso por gradiente ni scipy:
    la NLL en funcion de log(T) es unimodal, el problema es de UNA dimension,
    y asi no se anade una dependencia mas al servicio por diez lineas de
    codigo. Converge en ~60 evaluaciones a 1e-4.

    `logits` es la salida de `clf.decision_function`, no `predict_proba`: la
    temperatura se aplica ANTES del softmax.
    """
    if len(y) < MINIMO_MUESTRAS:
        # No es un error: es la respuesta correcta cuando no hay datos. T=1
        # deja las probabilidades intactas.
        return 1.0

    izquierda, derecha = np.log(T_MINIMA), np.log(T_MAXIMA)
    for _ in range(60):
        tercio = (derecha - izquierda) / 3.0
        a, b = izquierda + tercio, derecha - tercio
        if _nll(logits, y, float(np.exp(a))) < _nll(logits, y, float(np.exp(b))):
            derecha = b
        else:
            izquierda = a

    return float(np.exp((izquierda + derecha) / 2.0))


def _nll(logits: np.ndarray, y_indices: np.ndarray, temperatura: float) -> float:
    """Log-verosimilitud negativa media de las clases verdaderas."""
    log_p = _log_softmax(logits / temperatura)
    return float(-np.mean(log_p[np.arange(len(y_indices)), y_indices]))


def _log_softmax(z: np.ndarray) -> np.ndarray:
    """
    Softmax en log-espacio, restando el maximo por fila.

    Sin restar el maximo, un logit grande desborda el exp y produce inf/nan
    en silencio: las probabilidades salen NaN y el argmax devuelve siempre la
    clase 0 sin que nada falle de forma visible.
    """
    z = z - z.max(axis=1, keepdims=True)
    return z - np.log(np.exp(z).sum(axis=1, keepdims=True))


def aplicar_temperatura(logits: np.ndarray, temperatura: float) -> np.ndarray:
    """Probabilidades calibradas a partir de los logits."""
    if temperatura <= 0:
        raise ValueError(f"La temperatura tiene que ser positiva, no {temperatura}")
    return np.exp(_log_softmax(np.asarray(logits, dtype=float) / temperatura))


# ── Evaluacion de la calibracion ─────────────────────────────

def ece(probabilidades: np.ndarray, y_indices: np.ndarray, n_bins: int = N_BINS) -> float:
    """
    Error de calibracion esperado: |confianza − acierto| medio, ponderado.

    Mide sobre la clase predicha (top-1), que es lo que el alumno ve en
    pantalla.
    """
    return _error_calibracion(probabilidades, y_indices, n_bins, agregado="media")


def mce(probabilidades: np.ndarray, y_indices: np.ndarray, n_bins: int = N_BINS) -> float:
    """Error maximo entre particiones. Detecta el tramo donde mas miente."""
    return _error_calibracion(probabilidades, y_indices, n_bins, agregado="maximo")


def _error_calibracion(
    probabilidades: np.ndarray, y_indices: np.ndarray, n_bins: int, agregado: str
) -> float:
    confianza = probabilidades.max(axis=1)
    predicha = probabilidades.argmax(axis=1)
    acierto = (predicha == y_indices).astype(float)

    # Particiones por cuantiles y no de ancho fijo: con un modelo sobreseguro
    # casi toda la masa cae en el ultimo bin de ancho fijo y el ECE se calcula
    # sobre una sola particion, lo que lo vuelve ciego.
    bordes = np.unique(np.quantile(confianza, np.linspace(0, 1, n_bins + 1)))
    if len(bordes) < 2:
        return float(abs(confianza.mean() - acierto.mean()))

    errores, pesos = [], []
    for inicio, fin in zip(bordes[:-1], bordes[1:]):
        # El ultimo intervalo incluye su borde superior; el resto no, para no
        # contar dos veces las muestras que caen justo en un borde.
        dentro = (confianza >= inicio) & (
            (confianza < fin) if fin != bordes[-1] else (confianza <= fin)
        )
        if not dentro.any():
            continue
        errores.append(abs(confianza[dentro].mean() - acierto[dentro].mean()))
        pesos.append(dentro.sum())

    if not errores:
        return 0.0
    if agregado == "maximo":
        return float(max(errores))
    return float(np.average(errores, weights=pesos))


def brier_multiclase(probabilidades: np.ndarray, y_indices: np.ndarray) -> float:
    """
    Brier multiclase: error cuadratico medio contra el vector one-hot.

    A diferencia del ECE, penaliza a la vez el acierto y la confianza, asi
    que un modelo que siempre dice "10 % a cada clase" saca un ECE perfecto
    pero un Brier malo. Por eso se reportan los dos.
    """
    onehot = np.zeros_like(probabilidades)
    onehot[np.arange(len(y_indices)), y_indices] = 1.0
    return float(np.mean(np.sum((probabilidades - onehot) ** 2, axis=1)))


def diagrama_fiabilidad(
    probabilidades: np.ndarray, y_indices: np.ndarray, n_bins: int = N_BINS
) -> list[dict]:
    """
    Datos del diagrama de fiabilidad, listos para pintar en el panel.

    Cada punto responde: "de las veces que dije en torno a X % de confianza,
    ¿cuantas acerte?". Si los puntos caen sobre la diagonal, el modelo esta
    calibrado.
    """
    confianza = probabilidades.max(axis=1)
    acierto = (probabilidades.argmax(axis=1) == y_indices).astype(float)
    bordes = np.unique(np.quantile(confianza, np.linspace(0, 1, n_bins + 1)))

    puntos = []
    for inicio, fin in zip(bordes[:-1], bordes[1:]):
        dentro = (confianza >= inicio) & (
            (confianza < fin) if fin != bordes[-1] else (confianza <= fin)
        )
        if not dentro.any():
            continue
        puntos.append({
            "confianza_media": round(float(confianza[dentro].mean()), 4),
            "acierto_real": round(float(acierto[dentro].mean()), 4),
            "n": int(dentro.sum()),
        })
    return puntos


def evaluar_calibracion(
    logits: np.ndarray,
    y_indices: np.ndarray,
    temperatura: float,
    datos_sinteticos: bool = True,
) -> dict:
    """
    Compara el antes y el despues de calibrar, con su advertencia al lado.

    `datos_sinteticos` no es decorativo: es lo que impide que estas cifras se
    citen como si dijeran algo sobre alumnos reales.
    """
    antes = aplicar_temperatura(logits, 1.0)
    despues = aplicar_temperatura(logits, temperatura)

    informe = {
        "temperatura": round(float(temperatura), 4),
        "n_muestras": int(len(y_indices)),
        "ece_antes": round(ece(antes, y_indices), 4),
        "ece_despues": round(ece(despues, y_indices), 4),
        "mce_antes": round(mce(antes, y_indices), 4),
        "mce_despues": round(mce(despues, y_indices), 4),
        "brier_antes": round(brier_multiclase(antes, y_indices), 4),
        "brier_despues": round(brier_multiclase(despues, y_indices), 4),
        "diagrama_fiabilidad": diagrama_fiabilidad(despues, y_indices),
        "cumple_objetivo": bool(ece(despues, y_indices) <= ECE_OBJETIVO),
        "suficientes_muestras": bool(len(y_indices) >= MINIMO_MUESTRAS),
    }

    avisos = []
    if not informe["suficientes_muestras"]:
        avisos.append(
            f"Solo {len(y_indices)} muestras de calibracion (minimo {MINIMO_MUESTRAS}): "
            "la temperatura ajusta ruido. Se dejo en 1.0."
        )
    if datos_sinteticos:
        avisos.append(
            "CALIBRACION CIRCULAR: calculada sobre datos sinteticos cuya etiqueta "
            "es argmax(aff) por construccion. Estas cifras NO dicen nada sobre "
            "alumnos reales y no deben reportarse sin esta advertencia."
        )
    if informe["ece_despues"] > informe["ece_antes"]:
        avisos.append(
            "Calibrar empeoro el ECE. Suele indicar que la particion de "
            "calibracion es demasiado pequena o no es representativa."
        )
    informe["avisos"] = avisos

    return informe
