"""
database.py — Modelos del auth-service.

El motor y la fabrica de sesiones ya no se crean aqui: los construye
ServicioREVO con los limites de pool, los timeouts y el contexto RLS
cableado. Este modulo solo declara las tablas que el servicio usa.
"""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    student_code = Column(String(30), unique=True, nullable=True)
    semester = Column(SmallInteger, nullable=True)
    role = Column(String(20), nullable=False, default="student")
    is_active = Column(Boolean, nullable=False, default=True)
    avatar_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LegalDocument(Base):
    """Version vigente de cada documento legal (ver database/12_consentimiento.sql)."""

    __tablename__ = "legal_documents"

    id = Column(Integer, primary_key=True)
    doc_type = Column(String(30), nullable=False)
    version = Column(String(20), nullable=False)
    title = Column(String(200), nullable=False)
    summary = Column(Text, nullable=False)
    body_md = Column(Text, nullable=False)
    is_required = Column(Boolean, nullable=False, default=False)
    effective_from = Column(DateTime(timezone=True), server_default=func.now())
    is_current = Column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("doc_type", "version", name="legal_documents_doc_type_version_key"),)


class UserConsent(Base):
    """
    Registro auditable de cada decision de consentimiento.

    No se sobrescribe: cada cambio anade una fila. Un consentimiento sin
    historial no sirve como prueba de que el alumno autorizo algo en un
    momento concreto y sobre un texto concreto.
    """

    __tablename__ = "user_consents"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type = Column(String(30), nullable=False)
    doc_version = Column(String(20), nullable=False)
    granted = Column(Boolean, nullable=False)
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(String(400), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "doc_type", "doc_version", name="user_consents_unicos"),
    )
