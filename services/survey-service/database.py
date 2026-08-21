"""
database.py — Modelos del survey-service.

El motor y la fabrica de sesiones los construye ServicioREVO, con los limites
de pool, los timeouts de sentencia y el contexto RLS ya cableados. Aqui solo
quedan las tablas.
"""
from sqlalchemy import (
    Column, DateTime, DECIMAL, ForeignKey, Integer, JSON,
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
    question_type     = Column(String(30), nullable=False, default="scale")
    options           = Column(JSON)
    min_label         = Column(String(50), default="Muy bajo")
    max_label         = Column(String(50), default="Muy alto")
    weight            = Column(DECIMAL(4, 2), default=1.00)
    order_index       = Column(SmallInteger, default=0)
    is_active         = Column(Boolean, default=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())


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
#   survey-service -> questionnaire_sessions, answers
#   ml-service     -> predictions, prediction_feedbacks, ml_training_data
#
# Esa regla es lo que mantiene bajo el acoplamiento pese a compartir base de
# datos. Antes de anadir un modelo de otro servicio aqui, considera si lo que
# hace falta es una llamada al servicio dueno.


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


class Job(Base):
    __tablename__ = "jobs"
    id                = Column(Integer, primary_key=True)
    specialization_id = Column(Integer, nullable=False)
    company           = Column(String(100), nullable=False)
    title             = Column(String(255), nullable=False)
    salary_range      = Column(String(100))
    location          = Column(String(100), default="Remoto - Latam")
    url               = Column(Text, default="#")
    posted_days_ago   = Column(Integer, default=1)


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

# get_db() ya no vive aqui. La dependencia de sesion es servicio.sesion, que
# ademas fija el contexto RLS del solicitante antes de tocar ninguna tabla.
