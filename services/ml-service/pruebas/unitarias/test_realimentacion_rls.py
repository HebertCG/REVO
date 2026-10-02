"""
La realimentacion del alumno tiene que poder guardarse bajo RLS.

DEFECTO REAL, encontrado en la prueba de carga (2026-09-21): cada
"¿la IA te leyo bien?" devolvia 503. El ORM insertaba la muestra con
INSERT ... RETURNING id, y RETURNING exige poder LEER la fila nueva. La
politica de ml_training_data no deja a ningun alumno leer el dataset (con
razon: 10_rls.sql), asi que PostgreSQL rechazaba la fila. El bucle de
realimentacion -las etiquetas 'human' y 'human_corrected'- nunca recibio un
dato real.
"""
from sqlalchemy.dialects import postgresql

from database import MLTrainingData
from routers.predict import sentencia_de_aportacion


def muestra() -> MLTrainingData:
    return MLTrainingData(
        **{f"aff_{i}": 0.1 * i for i in range(1, 11)},
        specialization_id=4, source="human_corrected", prediction_id=7,
    )


def compilar(sentencia) -> str:
    return str(sentencia.compile(dialect=postgresql.dialect()))


def test_la_insercion_no_pide_leer_la_fila():
    assert "RETURNING" not in compilar(sentencia_de_aportacion(muestra())).upper()


def test_guarda_las_columnas_de_la_muestra():
    sql = compilar(sentencia_de_aportacion(muestra()))

    for columna in ("aff_1", "aff_10", "specialization_id", "source", "prediction_id"):
        assert columna in sql


def test_no_intenta_escribir_el_id_ni_las_columnas_vacias():
    # El id lo pone la secuencia; psy_a..psy_d van vacias en esta muestra.
    sql = compilar(sentencia_de_aportacion(muestra()))

    assert "psy_a" not in sql
    assert "(id," not in sql
