from sqlalchemy import (
    create_engine, Column, Integer, SmallInteger, Numeric,
    String, Boolean, Text, DateTime, DECIMAL, ForeignKey, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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


class User(Base):
    """Referencia mínima para FK — no se gestiona aquí."""
    __tablename__ = "users"
    id       = Column(Integer, primary_key=True)
    email    = Column(String(255))
    full_name= Column(String(150))
    role     = Column(String(20))


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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
