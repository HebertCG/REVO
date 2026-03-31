from sqlalchemy import create_engine, Column, Integer, String, Boolean, SmallInteger, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from config import settings

# Engine síncrono (compatible con FastAPI + psycopg2)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name     = Column(String(150), nullable=False)
    student_code  = Column(String(30), unique=True, nullable=True)
    semester      = Column(SmallInteger, nullable=True)
    role          = Column(String(20), nullable=False, default="student")
    is_active     = Column(Boolean, nullable=False, default=True)
    avatar_url    = Column(String(500), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Dependency para obtener sesión DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
