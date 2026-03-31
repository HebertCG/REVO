from sqlalchemy import create_engine, Column, Integer, Numeric, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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
    algorithm        = Column(String(50), default="DecisionTreeClassifier")
    accuracy         = Column(Numeric(6, 4))
    precision_score  = Column(Numeric(6, 4))
    recall_score     = Column(Numeric(6, 4))
    f1_score         = Column(Numeric(6, 4))
    training_samples = Column(Integer)
    test_samples     = Column(Integer)
    max_depth        = Column(Integer)
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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
