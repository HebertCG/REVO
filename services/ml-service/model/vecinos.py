"""
vecinos.py — ¿Se parece este alumno a alguien que el modelo haya visto?

PROBLEMA QUE RESUELVE

Una regresion logistica parte el espacio en regiones y asigna una clase a
cada punto, este donde este. Un alumno con un perfil que nadie tuvo nunca
cae igualmente en alguna region, y el modelo le da su porcentaje con la misma
seguridad que a uno tipico. Ese porcentaje no vale nada: es extrapolacion.

incertidumbre.py ya mide esto de una forma (el desacuerdo entre 30 modelos
bootstrap). Esta es la otra, mas directa y mas facil de explicar: mirar a
cuanta distancia estan los alumnos mas parecidos del dataset.

COMO

  Al entrenar   para cada alumno del dataset se mide la distancia media a
                sus k vecinos mas cercanos (sin contarse a si mismo). El
                percentil 95 de esas distancias es el UMBRAL: el 95 % de los
                alumnos que el modelo vio estan al menos asi de acompanados.

  Al predecir   pgvector busca los k vecinos del alumno nuevo en la base
                (indice HNSW, ver 36_vectores.sql) y devuelve la distancia
                media. Si supera el umbral, es un "perfil poco visto".

POR QUE EL UMBRAL SE CALCULA AQUI Y LA BUSQUEDA EN POSTGRESQL

Al entrenar el dataset ya esta en memoria, y hacerlo con numpy es lo mas
directo. Al predecir, el servicio NO tiene el dataset: esta en la base,
protegido por RLS. Traerlo entero para cada alumno seria absurdo; pedirle a
PostgreSQL los 10 vecinos con un indice es exactamente para lo que existe
pgvector.

Distancia euclidea (L2) en los dos sitios, sobre las 10 afinidades en 0..1:
es la geometria en la que trabaja el modelo.
"""
from __future__ import annotations

import numpy as np

#: Cuantos vecinos se promedian. Uno solo es ruidoso (un gemelo casual hace
#: parecer tipico a cualquiera); demasiados diluyen la senal.
K_VECINOS = 10

#: Por encima de este percentil de lo visto, el perfil es "poco visto".
PERCENTIL_UMBRAL = 95

#: La matriz de distancias es n x n. Con 2000 filas son 32 MB; sin tope, un
#: dataset de 50 000 filas pediria 20 GB. Por encima se submuestrea, con
#: semilla fija para que dos entrenamientos iguales den el mismo umbral.
MUESTRA_MAXIMA = 2000
SEMILLA = 42


def distancias_medias_a_vecinos(X: np.ndarray, k: int) -> np.ndarray:
    """
    Distancia media de cada fila a sus k vecinos, sin contarse a si misma.

    Usa ||a - b||^2 = ||a||^2 + ||b||^2 - 2 a.b para no construir el tensor
    n x n x d, que con 10 columnas ocuparia diez veces mas.
    """
    cuadrados = np.einsum("ij,ij->i", X, X)
    d2 = cuadrados[:, None] + cuadrados[None, :] - 2.0 * X @ X.T
    # Errores de redondeo pueden dar -1e-16 donde deberia haber 0.
    distancias = np.sqrt(np.maximum(d2, 0.0))
    # Un punto no es su propio vecino: si lo fuera, la minima seria siempre 0
    # y el umbral saldria artificialmente bajo.
    np.fill_diagonal(distancias, np.inf)
    mas_cercanas = np.partition(distancias, k - 1, axis=1)[:, :k]
    return mas_cercanas.mean(axis=1)


def calcular_umbral(
    X: np.ndarray, k: int = K_VECINOS, percentil: int = PERCENTIL_UMBRAL,
) -> dict | None:
    """
    Informe del vecindario para guardarlo junto al modelo, o None.

    None si no hay mas filas que vecinos: "los 10 mas parecidos" no existe
    con 10 alumnos, y un umbral inventado seria peor que ninguno.
    """
    if len(X) <= k:
        return None

    if len(X) > MUESTRA_MAXIMA:
        indices = np.random.default_rng(SEMILLA).choice(
            len(X), size=MUESTRA_MAXIMA, replace=False)
        X = X[np.sort(indices)]

    distancias = distancias_medias_a_vecinos(np.asarray(X, dtype=float), k)
    return {
        "k": k,
        "percentil": percentil,
        "umbral": round(float(np.percentile(distancias, percentil)), 6),
        "mediana": round(float(np.median(distancias)), 6),
        "muestras": int(len(X)),
    }


def evaluar(distancia: float | None, informe: dict | None) -> dict:
    """
    Lectura de la distancia de un alumno nuevo.

    Tres respuestas posibles, y la tercera importa: si no se pudo medir, se
    dice "no disponible", no "perfil normal". Callar la duda es justo lo que
    este modulo existe para evitar.
    """
    if distancia is None:
        return {"disponible": False, "distancia_media": None,
                "umbral": (informe or {}).get("umbral"), "perfil_poco_visto": None}

    umbral = (informe or {}).get("umbral")
    return {
        "disponible": True,
        "distancia_media": round(float(distancia), 4),
        "umbral": umbral,
        # Un modelo entrenado antes de que existiera el umbral da la
        # distancia, pero no un veredicto que no puede sostener.
        "perfil_poco_visto": None if umbral is None else bool(distancia > umbral),
    }
