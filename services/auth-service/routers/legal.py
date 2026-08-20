"""
legal.py — Documentos legales que el formulario de registro necesita leer.

Estas rutas son publicas a proposito: el alumno tiene que poder leer los
Terminos y la Politica de Privacidad ANTES de tener cuenta. Un consentimiento
que solo se puede leer despues de aceptarlo no es informado.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import consentimiento
from database import LegalDocument
from schemas import DocumentoLegalCompleto, DocumentoLegalResumen
from servicio_revo import servicio

router = APIRouter(prefix="/legal", tags=["Legal"])


@router.get("/documents", response_model=list[DocumentoLegalResumen])
def documentos(
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    """
    Las casillas que debe pintar el formulario de registro.

    Devuelve el resumen, no el texto completo: el cuerpo de los cuatro
    documentos son decenas de kilobytes que el formulario no necesita hasta
    que alguien pulsa "Leer mas".
    """
    return [
        DocumentoLegalResumen.model_validate(doc)
        for doc in consentimiento.documentos_vigentes(db)
    ]


@router.get("/documents/{doc_type}", response_model=DocumentoLegalCompleto)
def documento(
    doc_type: str,
    db: Session = Depends(servicio.sesion),
    _: None = Depends(servicio.limitar("read")),
):
    """El texto completo de un documento, para el enlace 'Leer mas'."""
    # doc_type llega por la URL. Se valida contra la lista cerrada antes de
    # tocar la base de datos: nada que venga del cliente se usa como filtro
    # sin comprobar primero que es uno de los valores esperados.
    tipos_validos = set(consentimiento.DOCUMENTOS_OBLIGATORIOS) | set(
        consentimiento.DOCUMENTOS_OPCIONALES
    )
    if doc_type not in tipos_validos:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    doc = db.scalar(
        select(LegalDocument).where(
            LegalDocument.doc_type == doc_type,
            LegalDocument.is_current.is_(True),
        )
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    return DocumentoLegalCompleto.model_validate(doc)
