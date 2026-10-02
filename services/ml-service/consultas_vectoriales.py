"""
consultas_vectoriales.py — Lo que ml-service le pregunta a pgvector.

Dos preguntas, las dos despues de haber guardado la prediccion:

  vecindario            ¿a cuanta distancia estan los alumnos mas parecidos
                        del dataset? (revo_distancia_al_entrenamiento)
  ocupaciones afines    ¿que ocupaciones reales de O*NET tienen un perfil
                        de intereses parecido? (revo_ocupaciones_afines)

Las funciones SQL estan en database/36_vectores.sql.

NINGUN FALLO DE AQUI TUMBA UNA PREDICCION

La recomendacion es lo principal; esto la complementa. Si pgvector no esta
instalado o una consulta falla, se registra un aviso, se deshace la
transaccion (sin eso la sesion queda en "current transaction is aborted") y
el resultado sale con `disponible: False`. No en silencio: dicho.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from model import ocupaciones, vecinos

logger = logging.getLogger("revo.ml.vectores")

#: Cuantas ocupaciones afines se devuelven. Mas de cinco en una pantalla de
#: resultado ya no se leen.
K_OCUPACIONES = 5

#: Los perfiles de las ramas solo cambian con una migracion. Se cachean como
#: el catalogo de especializaciones (ver catalogo.py).
VIGENCIA_SEGUNDOS = 300

N_AFINIDADES = 10

SENTENCIA_DISTANCIA = text(
    "SELECT revo_distancia_al_entrenamiento(CAST(:perfil AS vector), :k)"
)
SENTENCIA_PERFILES = text("""
    SELECT id, riasec_r, riasec_i, riasec_a, riasec_s, riasec_e, riasec_c
      FROM specializations
     WHERE riasec_r IS NOT NULL
""")
SENTENCIA_AFINES = text("""
    SELECT codigo_soc, titulo, correlacion
      FROM revo_ocupaciones_afines(:r, :i, :a, :s, :e, :c, :k)
""")

_perfiles: dict[int, list[float]] | None = None
_perfiles_leidos_en = 0.0


def olvidar_perfiles() -> None:
    """Vacia la cache. Para las pruebas y tras cargar perfiles nuevos."""
    global _perfiles, _perfiles_leidos_en
    _perfiles, _perfiles_leidos_en = None, 0.0


def literal_vector(valores) -> str:
    """'[0.5,1,0.25]': el formato de texto que pgvector acepta."""
    return "[" + ",".join(f"{float(v):.6g}" for v in valores) + "]"


def _consultar(db: Session, sentencia, parametros: dict | None = None):
    """Ejecuta, o registra el fallo, deshace y devuelve None."""
    try:
        return db.execute(sentencia, parametros or {})
    except SQLAlchemyError as exc:
        logger.warning("Consulta vectorial fallida (%s): %s",
                       str(sentencia).split("(")[0].strip()[:60], exc)
        db.rollback()
        return None


def distancia_al_entrenamiento(
    db: Session, afinidades: list[float], k: int = vecinos.K_VECINOS,
) -> float | None:
    """Distancia media a los k alumnos mas parecidos del dataset, o None."""
    resultado = _consultar(db, SENTENCIA_DISTANCIA,
                           {"perfil": literal_vector(afinidades), "k": k})
    if resultado is None:
        return None
    valor = resultado.scalar()
    return None if valor is None else float(valor)


def perfiles_de_ramas(db: Session) -> dict[int, list[float]]:
    """Perfil RIASEC de cada rama, de `specializations` (cacheado)."""
    global _perfiles, _perfiles_leidos_en
    if _perfiles is not None and time.monotonic() - _perfiles_leidos_en < VIGENCIA_SEGUNDOS:
        return _perfiles

    resultado = _consultar(db, SENTENCIA_PERFILES)
    if resultado is None:
        return _perfiles or {}

    _perfiles = {int(fila[0]): [float(v) for v in fila[1:]] for fila in resultado.all()}
    _perfiles_leidos_en = time.monotonic()
    return _perfiles


def ocupaciones_afines(
    db: Session, perfil: list[float] | None, k: int = K_OCUPACIONES,
) -> list[dict]:
    """Las k ocupaciones de O*NET con el perfil de intereses mas parecido."""
    if perfil is None:
        return []

    r, i, a, s, e, c = perfil
    resultado = _consultar(db, SENTENCIA_AFINES,
                           {"r": r, "i": i, "a": a, "s": s, "e": e, "c": c, "k": k})
    if resultado is None:
        return []

    return [
        {"codigo_soc": codigo, "titulo": titulo, "correlacion": round(float(r_), 3)}
        for codigo, titulo, r_ in resultado.all()
    ]


def enriquecer(db: Session, feature_vector: dict, resultado: dict) -> dict:
    """
    Vecindario y ocupaciones afines para una prediccion ya guardada.

    Las afinidades se leen igual que build_feature_vector: una ausente vale
    0.0 ("rama no explorada"). Si se leyeran distinto, el vecindario mediria
    la distancia de un alumno que no es el que el modelo evaluo.
    """
    afinidades = [float(feature_vector.get(f"aff_{i}", 0.0))
                  for i in range(1, N_AFINIDADES + 1)]

    distancia = distancia_al_entrenamiento(db, afinidades)
    perfil = ocupaciones.perfil_esperado(
        resultado.get("probabilidades_por_id", {}), perfiles_de_ramas(db))

    return {
        "vecindario": vecinos.evaluar(distancia, resultado.get("vecindario_entrenamiento")),
        "ocupaciones_afines": ocupaciones_afines(db, perfil),
    }
