"""
database.py — Modelos del ml-service.

El motor y la fabrica de sesiones los construye ServicioREVO. Las tareas de
fondo (reentrenamiento) usan servicio.sesion_de_servicio(), que abre la
sesion con el contexto RLS del rol 'service': lee el dataset completo sin
tener que hacerse pasar por administrador.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class MLTrainingData(Base):
    __tablename__ = "ml_training_data"
    id     = Column(Integer, primary_key=True)
    aff_1  = Column(Numeric(5, 4));  aff_2  = Column(Numeric(5, 4))
    aff_3  = Column(Numeric(5, 4));  aff_4  = Column(Numeric(5, 4))
    aff_5  = Column(Numeric(5, 4));  aff_6  = Column(Numeric(5, 4))
    aff_7  = Column(Numeric(5, 4));  aff_8  = Column(Numeric(5, 4))
    aff_9  = Column(Numeric(5, 4));  aff_10 = Column(Numeric(5, 4))
    specialization_id = Column(Integer, nullable=False)
    #: 'synthetic' | 'human' | 'human_corrected'. La tercera son las filas
    #: que vienen de un DESACUERDO del alumno con etiqueta corregida: las
    #: unicas que enseñan algo nuevo. Ver database/24_realimentacion_que_corrige.sql
    source = Column(String(50), default="synthetic")

    # ── Perfil de trabajo de la fase 3 (migracion 23) ────────
    # Proporciones de estilo: analitico / pragmatico / colaborativo /
    # perfeccionista. Suman 1. Son la unica senal del cuestionario que la
    # regla argmax(aff) no puede ver.
    psy_a = Column(Numeric(5, 4));  psy_b = Column(Numeric(5, 4))
    psy_c = Column(Numeric(5, 4));  psy_d = Column(Numeric(5, 4))

    #: De que prediccion salio la fila, cuando source empieza por 'human'.
    #: Permite auditarla y retirarla si el alumno revoca el consentimiento.
    prediction_id = Column(Integer, nullable=True)

    #: NO ES UNA FEATURE: es el filtro de calidad. Duracion de la sesion que
    #: produjo la muestra, para poder descartar respuestas contestadas sin
    #: leer antes de entrenar. No incluir en FEATURE_COLS.
    duration_seconds = Column(Integer, nullable=True)


class Specialization(Base):
    __tablename__ = "specializations"
    id        = Column(Integer, primary_key=True)
    name      = Column(String(100))
    slug      = Column(String(80))
    icon      = Column(String(20))
    color_hex = Column(String(7))


class ModelTrainingLog(Base):
    __tablename__ = "model_training_logs"
    id               = Column(Integer, primary_key=True)
    model_version    = Column(String(30))
    algorithm        = Column(String(50), default="LogisticRegression")
    accuracy         = Column(Numeric(6, 4))
    precision_score  = Column(Numeric(6, 4))
    recall_score     = Column(Numeric(6, 4))
    f1_score         = Column(Numeric(6, 4))
    training_samples = Column(Integer)
    test_samples     = Column(Integer)
    n_iterations     = Column(Integer)   # iteraciones hasta converger
    features_used    = Column(JSON)
    hyperparams      = Column(JSON)
    model_path       = Column(String(500))
    trained_by       = Column(Integer, nullable=True)
    trained_at       = Column(DateTime(timezone=True), server_default=func.now())
    notes            = Column(Text)


class Prediction(Base):
    __tablename__ = "predictions"
    id                        = Column(Integer, primary_key=True)
    session_id                = Column(Integer)
    user_id                   = Column(Integer)
    primary_specialization_id = Column(Integer, ForeignKey("specializations.id"))
    confidence_score          = Column(Numeric(5, 4))
    secondary_specializations = Column(JSON, default=list)
    feature_vector            = Column(JSON)
    model_version             = Column(String(30), default="v1.0")
    created_at                = Column(DateTime(timezone=True), server_default=func.now())
    #: El resultado completo tal como se calculo (migracion 38). Sin esto, el
    #: GET que usa la pantalla de resultado perdia la calibracion, la
    #: incertidumbre y el conjunto conformal. NULL en predicciones antiguas.
    detalle                   = Column(JSON, nullable=True)

class PredictionFeedback(Base):
    __tablename__ = "prediction_feedbacks"
    id                  = Column(Integer, primary_key=True)
    prediction_id       = Column(Integer, ForeignKey("predictions.id"), unique=True, nullable=False)
    user_id             = Column(Integer, nullable=False)
    session_id          = Column(Integer)
    diagnostic_affinity = Column(Boolean, nullable=False)
    discovery_level     = Column(String(50), nullable=False)
    #: Rama que el alumno considera correcta cuando discrepa. NULL es valido
    #: y frecuente: se puede saber que un resultado no te representa sin
    #: saber cual si. Ver database/24_realimentacion_que_corrige.sql
    corrected_specialization_id = Column(Integer, nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())


# get_db() ya no vive aqui. Para peticiones se usa servicio.sesion (fija el
# contexto RLS del alumno) y para tareas de fondo servicio.sesion_de_servicio().


# ── Recomendaciones derivadas del resultado ──────────────────
# Cursos vivia en survey-service. Se movio aqui porque no tiene nada que ver
# con ejecutar el cuestionario: es "que hacer con tu resultado", y va
# indexado por especializacion, que es lo que este servicio produce.
#
# Aqui habia tambien un modelo `Job`. Se retiro con la tabla `jobs`
# (migracion 20): la pantalla de resultado dejo de leerla cuando paso a
# consultar la API de Remotive en tiempo real. Una oferta de hace tres meses
# servida como actual es peor que no servir ninguna.


class Course(Base):
    __tablename__ = "courses"
    id                = Column(Integer, primary_key=True)
    specialization_id = Column(Integer, nullable=False)
    platform          = Column(String(50), nullable=False)
    title             = Column(String(255), nullable=False)
    url               = Column(Text, nullable=False)
    level             = Column(String(50), default="Principiante")
    price_model       = Column(String(50), default="Pago")
    thumbnail_url     = Column(Text)
