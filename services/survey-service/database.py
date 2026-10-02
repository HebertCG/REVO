"""
database.py — Modelos del survey-service.

El motor y la fabrica de sesiones los construye ServicioREVO, con los limites
de pool, los timeouts de sentencia y el contexto RLS ya cableados. Aqui solo
quedan las tablas.
"""
from sqlalchemy import (
    CHAR, Column, DateTime, ForeignKey, Integer, JSON,
    Numeric, SmallInteger, String, Boolean, Text
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Question(Base):
    __tablename__ = "questions"
    id                = Column(Integer, primary_key=True)
    text              = Column(Text, nullable=False)
    category          = Column(String(30), nullable=False)
    specialization_id = Column(Integer, nullable=False, default=1) # 1..10
    order_index       = Column(SmallInteger, default=0)
    is_active         = Column(Boolean, default=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    # Aqui habia cinco columnas mas: question_type, options, min_label,
    # max_label y weight. Las retira database/21_retirar_columnas_muertas.sql
    # porque ninguna contenia nada: las 100 preguntas del banco son de tipo
    # 'scale' con options a NULL, las etiquetas las pone el frontend con su
    # propia escala de cinco puntos, y `weight` valia 1.00 en todas mientras
    # el calculo de afinidad sumaba los valores en crudo sin mirarla.


class QuestionnaireSession(Base):
    __tablename__ = "questionnaire_sessions"
    id               = Column(Integer, primary_key=True)
    user_id          = Column(Integer, nullable=False) # Eliminamos constraint FK físico para evitar crasheos cruzados
    status           = Column(String(20), default="in_progress")
    phase            = Column(SmallInteger, default=1)
    phase_data       = Column(JSON) # {"top3_specs": [1,4,7], "phase_1_score": ...}
    started_at       = Column(DateTime(timezone=True), server_default=func.now())
    completed_at     = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    answers          = relationship("Answer", back_populates="session", cascade="all, delete")


class Answer(Base):
    __tablename__ = "answers"
    id          = Column(Integer, primary_key=True)
    session_id  = Column(Integer, ForeignKey("questionnaire_sessions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    value       = Column(Numeric(4, 2), nullable=False)
    answered_at = Column(DateTime(timezone=True), server_default=func.now())
    session     = relationship("QuestionnaireSession", back_populates="answers")


# Aqui habia un modelo `User`. Se ha retirado a proposito: este servicio no
# leia ni escribia esa tabla en ninguna ruta, y tenerla declarada sugeria que
# el cuestionario es dueno de los datos de usuario cuando no lo es. La
# identidad del alumno llega ya verificada en el token, asi que no hace falta
# consultar `users` desde aqui.
#
# Cada tabla la escribe un solo servicio:
#   auth-service   -> users, user_consents, legal_documents
#   survey-service -> questionnaire_sessions, answers, psychometric_answers
#   ml-service     -> predictions, prediction_feedbacks, ml_training_data
#
# Esa regla es lo que mantiene bajo el acoplamiento pese a compartir base de
# datos. Antes de anadir un modelo de otro servicio aqui, considera si lo que
# hace falta es una llamada al servicio dueno.


# Cursos y empleos ya no viven aqui: se movieron a ml-service, que es quien
# produce la especializacion contra la que se indexan. Este servicio ejecuta
# el cuestionario y nada mas.


class PsychometricQuestion(Base):
    __tablename__ = "psychometric_questions"
    id                = Column(Integer, primary_key=True)
    specialization_id = Column(Integer, nullable=False)
    question_text     = Column(Text, nullable=False)
    option_a          = Column(Text, nullable=False)
    option_b          = Column(Text, nullable=False)
    option_c          = Column(Text, nullable=False)
    option_d          = Column(Text, nullable=False)
    order_index       = Column(SmallInteger, default=0)
    is_active         = Column(Boolean, default=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())


class PsychometricAnswer(Base):
    """
    Respuestas de la fase 3 (ver database/22_fase3_persistida.sql).

    Antes de esta tabla, la fase 3 se calculaba en el navegador y moria en
    sessionStorage: ni el alumno podia volver a verla en su historial, ni el
    modelo llegaba a olerla. Son las cuatro respuestas del test que preguntan
    como trabaja la persona en vez de que rama dice que le gusta.

    Una fila por respuesta, colgando de la sesion, igual que Answer. El
    arquetipo NO se guarda: se deriva de estas filas cada vez que se
    necesita, que es lo que lo hace reproducible.
    """

    __tablename__ = "psychometric_answers"
    id                = Column(Integer, primary_key=True)
    session_id        = Column(Integer, ForeignKey("questionnaire_sessions.id"), nullable=False)
    specialization_id = Column(Integer, nullable=False)
    # Una de las dos, nunca ambas: la pregunta vino del banco de la base de
    # datos (question_id) o del banco local de reserva del frontend
    # (fallback_key), que se usa cuando /psychometric no responde. Lo impone
    # el CHECK psyans_una_procedencia.
    question_id       = Column(Integer, ForeignKey("psychometric_questions.id"), nullable=True)
    fallback_key      = Column(String(40), nullable=True)
    option_key        = Column(CHAR(1), nullable=False)   # 'A' | 'B' | 'C' | 'D'
    order_index       = Column(SmallInteger, default=0)
    answered_at       = Column(DateTime(timezone=True), server_default=func.now())

# get_db() ya no vive aqui. La dependencia de sesion es servicio.sesion, que
# ademas fija el contexto RLS del solicitante antes de tocar ninguna tabla.
