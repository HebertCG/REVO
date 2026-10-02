"""
incertidumbre.py — Que el modelo sepa CUANDO no sabe, y por que.

PROBLEMA QUE RESUELVE

Hoy el sistema siempre devuelve un top-1 con su porcentaje, pase lo que pase.
No distingue dos situaciones que no se parecen en nada:

  * ALEATORIA: el alumno de verdad encaja igual de bien en dos ramas. Aqui no
    hay nada que arreglar; mas preguntas no ayudan, porque la ambiguedad esta
    en la persona. Lo correcto es decir "encajas en estas dos".

  * EPISTEMICA: nunca vimos a nadie con este perfil. Aqui el modelo esta
    extrapolando, y su porcentaje no vale nada. Lo correcto es admitirlo.

Mezclarlas es lo que hace que un sistema parezca seguro justo cuando mas
deberia dudar: un perfil raro cae lejos de todo y la regresion le asigna
alegremente un 90 % a la clase cuyo semiplano le toca.

COMO SE MIDE CADA UNA

  * Aleatoria -> entropia normalizada y margen top1-top2 sobre la posterior
    ya calibrada. Practicamente gratis.

  * Epistemica -> DESACUERDO de un conjunto de modelos entrenados sobre
    remuestreos bootstrap. Si 30 regresiones entrenadas con datos distintos
    dicen lo mismo, la region esta bien cubierta; si discrepan, no lo esta.

POR QUE BOOTSTRAP Y NO OTRA COSA

MC dropout no aplica a scikit-learn. Los procesos gaussianos no escalan ni se
defienden facil. El bootstrap es bagging estandar, se cita sin problema, y
aqui es barato de verdad: una LogisticRegression de 10 features y 10 clases
son 110 coeficientes, asi que 30 modelos ocupan menos que una imagen.

Ademas el conjunto sirve dos veces: para la incertidumbre epistemica y para
los intervalos de confianza del informe de evaluacion.
"""
from __future__ import annotations

import numpy as np
from sklearn.base import clone

#: Tamano del conjunto. Por debajo de ~20 la medida de desacuerdo es ruidosa;
#: por encima de ~50 deja de mejorar y solo cuesta tiempo de entrenamiento.
N_MODELOS = 30

#: Umbrales de lectura. Salen de repartir el rango en tres tramos y hay que
#: recalibrarlos con datos reales: hoy son un punto de partida documentado,
#: no una medida.
ENTROPIA_ALTA = 0.60      # sobre 1.0 (normalizada por log(n_clases))
MARGEN_ESTRECHO = 0.10    # diferencia entre la 1a y la 2a
DESACUERDO_ALTO = 0.25    # desviacion tipica media entre modelos del conjunto


def entropia_normalizada(probabilidades: np.ndarray) -> float:
    """
    Entropia de Shannon dividida por su maximo. 0 = certeza, 1 = ni idea.

    Se normaliza para que el numero sea legible sin saber cuantas clases hay:
    "0.7" se entiende; "2.32 bits" exige saber que el maximo son 3.32.
    """
    p = np.asarray(probabilidades, dtype=float).ravel()
    p = p[p > 0]
    if len(p) <= 1:
        return 0.0
    entropia = float(-np.sum(p * np.log(p)))
    return float(entropia / np.log(len(probabilidades)))


def margen(probabilidades: np.ndarray) -> float:
    """Diferencia entre la primera y la segunda. Margen pequeno = empate."""
    ordenadas = np.sort(np.asarray(probabilidades, dtype=float).ravel())[::-1]
    if len(ordenadas) < 2:
        return 1.0
    return float(ordenadas[0] - ordenadas[1])


def margen_en(probabilidades: np.ndarray, posicion: int) -> float:
    """
    Margen entre la posicion k y la k+1 (1-indexado).

    `margen_en(p, 3)` es el margen entre el 3.o y el 4.o, que es la frontera
    que de verdad importa: el producto entrega un TOP-3, asi que lo que el
    alumno ve depende de si el puesto 3 esta separado del 4, no de si el 1
    esta separado del 2.
    """
    ordenadas = np.sort(np.asarray(probabilidades, dtype=float).ravel())[::-1]
    if posicion < 1 or posicion >= len(ordenadas):
        return 1.0
    return float(ordenadas[posicion - 1] - ordenadas[posicion])


# ── Conjunto bootstrap ───────────────────────────────────────

def entrenar_conjunto(
    estimador, X: np.ndarray, y: np.ndarray,
    n_modelos: int = N_MODELOS, semilla: int = 42,
) -> list:
    """
    Entrena `n_modelos` copias sobre remuestreos con reemplazo.

    Se descartan los remuestreos que pierden alguna clase: una regresion
    entrenada sin la clase 7 no puede predecirla nunca, y meterla en el
    conjunto sesga el desacuerdo hacia abajo justo en esa clase.
    """
    generador = np.random.default_rng(semilla)
    clases_completas = np.unique(y)
    modelos, intentos = [], 0

    while len(modelos) < n_modelos and intentos < n_modelos * 10:
        intentos += 1
        indices = generador.integers(0, len(X), size=len(X))
        if not np.array_equal(np.unique(y[indices]), clases_completas):
            continue
        copia = clone(estimador)
        copia.fit(X[indices], y[indices])
        modelos.append(copia)

    return modelos


def desacuerdo(modelos: list, x: np.ndarray) -> float:
    """
    Cuanto discrepan los modelos del conjunto sobre UNA muestra.

    Se mide como la desviacion tipica de la probabilidad predicha por clase,
    promediada sobre las clases. Alto = region poco cubierta por los datos =
    incertidumbre epistemica.
    """
    if not modelos:
        return 0.0
    x = np.asarray(x, dtype=float).reshape(1, -1)
    predicciones = np.vstack([modelo.predict_proba(x)[0] for modelo in modelos])
    return float(np.mean(np.std(predicciones, axis=0)))


def probabilidad_media(modelos: list, x: np.ndarray) -> np.ndarray:
    """Media del conjunto. Mas estable que la de un solo modelo."""
    x = np.asarray(x, dtype=float).reshape(1, -1)
    return np.mean([modelo.predict_proba(x)[0] for modelo in modelos], axis=0)


# ── Lectura conjunta ─────────────────────────────────────────

#: Texto para el alumno cuando su perfil se parece poco a lo visto. Uno solo,
#: lo detecte el conjunto bootstrap o el vecindario: al alumno le da igual
#: que medida fue, y dos redacciones distintas de lo mismo confunden.
#:
#: Los textos de cara al alumno llevan tildes aunque el codigo no: se leen en
#: la pantalla de resultado desde que el GET devuelve el resultado completo.
EXPLICACION_POCO_VISTO = (
    "Tu combinación de respuestas se parece poco a la de los perfiles "
    "con los que se entrenó el sistema. El resultado es menos fiable "
    "de lo habitual."
)


def diagnosticar(probabilidades: np.ndarray, desacuerdo_valor: float | None = None) -> dict:
    """
    Traduce los numeros a una lectura que se pueda poner en pantalla.

    Devuelve tambien las cifras crudas: el panel de administracion las
    necesita, y una etiqueta sin el numero que la genero no es auditable.
    """
    h = entropia_normalizada(probabilidades)
    m = margen(probabilidades)
    m34 = margen_en(probabilidades, 3)

    ambiguo = h >= ENTROPIA_ALTA or m <= MARGEN_ESTRECHO
    fuera_de_soporte = desacuerdo_valor is not None and desacuerdo_valor >= DESACUERDO_ALTO

    if fuera_de_soporte:
        # Este caso va primero a proposito: si el perfil esta fuera de lo
        # visto, el resto de numeros describen una extrapolacion y no
        # merecen protagonismo.
        lectura = "perfil_poco_visto"
        explicacion = EXPLICACION_POCO_VISTO
    elif ambiguo:
        lectura = "encaja_en_varias"
        explicacion = (
            "Tus respuestas encajan de forma parecida en más de una rama. "
            "Eso no es un fallo del test: es información sobre ti."
        )
    else:
        lectura = "definido"
        explicacion = "Tus respuestas apuntan de forma consistente a una rama."

    return {
        "lectura": lectura,
        "explicacion": explicacion,
        "entropia_normalizada": round(h, 4),
        "margen_top1_top2": round(m, 4),
        "margen_top3_top4": round(m34, 4),
        "desacuerdo_conjunto": (
            round(float(desacuerdo_valor), 4) if desacuerdo_valor is not None else None
        ),
        "incertidumbre_aleatoria_alta": bool(ambiguo),
        "incertidumbre_epistemica_alta": bool(fuera_de_soporte),
    }


def incorporar_vecindario(diagnostico: dict, vecindario: dict) -> dict:
    """
    Suma a la lectura la segunda medida epistemica: la distancia a los vecinos.

    POR QUE HACE FALTA LA SEGUNDA

    Caso real (prediccion 296): 99,9 % de confianza, conjunto conformal de una
    sola rama, y los 30 modelos bootstrap de acuerdo (desacuerdo 0,005). Pero
    el alumno estaba a 0,79 de sus vecinos, con un umbral de 0,60.

    Los 30 modelos son regresiones logisticas. Lejos de las fronteras de
    decision, todas extrapolan en la misma direccion y "coinciden" aunque
    nadie haya visto nunca ese perfil: es un punto ciego conocido de medir
    la incertidumbre por desacuerdo entre modelos lineales. La distancia a
    los vecinos (model/vecinos.py) no lo tiene.

    Devuelve un diccionario NUEVO y deja constancia de que medida lo detecto:
    una etiqueta sin su origen no se puede auditar.
    """
    fuentes = []
    if diagnostico.get("incertidumbre_epistemica_alta"):
        fuentes.append("conjunto")
    # `is True` a proposito: None significa "no se pudo medir", que no es ni
    # normal ni raro (ver vecinos.evaluar).
    if vecindario.get("perfil_poco_visto") is True:
        fuentes.append("vecindario")

    nuevo = {**diagnostico, "fuentes_epistemicas": fuentes}
    if fuentes:
        nuevo.update(
            lectura="perfil_poco_visto",
            explicacion=EXPLICACION_POCO_VISTO,
            incertidumbre_epistemica_alta=True,
        )
    return nuevo
