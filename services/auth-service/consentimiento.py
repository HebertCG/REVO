"""
consentimiento.py — Registro y consulta del consentimiento informado.

Se separa del router de autenticacion porque es una responsabilidad distinta:
el router decide flujos HTTP, esto decide que se guarda como prueba de que un
alumno autorizo un uso concreto de sus datos.

Regla que sostiene todo el modulo: **el consentimiento se guarda contra una
version concreta del documento**. Si el texto cambia y no se guardo la
version, no hay forma de saber a que acepto realmente el alumno, y el
consentimiento deja de servir como prueba.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import LegalDocument, UserConsent

#: Documentos que el alumno debe aceptar para tener cuenta.
DOCUMENTOS_OBLIGATORIOS = ("terms", "privacy")

#: Documentos opcionales. Cada uno es una finalidad distinta y se autoriza
#: por separado; ninguno condiciona el uso de la plataforma.
DOCUMENTOS_OPCIONALES = ("data_commercial", "ai_training")


def documentos_vigentes(db: Session) -> list[LegalDocument]:
    """Los documentos legales en vigor, obligatorios primero."""
    return list(
        db.scalars(
            select(LegalDocument)
            .where(LegalDocument.is_current.is_(True))
            .order_by(LegalDocument.is_required.desc(), LegalDocument.doc_type)
        )
    )


def _versiones_vigentes(db: Session) -> dict[str, str]:
    """Mapa tipo -> version en vigor, en UNA consulta."""
    filas = db.execute(
        select(LegalDocument.doc_type, LegalDocument.version).where(
            LegalDocument.is_current.is_(True)
        )
    ).all()
    return {tipo: version for tipo, version in filas}


def registrar_consentimiento_inicial(
    db: Session,
    user_id: int,
    acepta_obligatorios: bool,
    acepta_comercial: bool,
    acepta_entrenamiento: bool,
    ip: str | None,
    user_agent: str | None,
) -> list[UserConsent]:
    """
    Graba las cuatro decisiones del formulario de registro.

    Se graban TODAS, incluidos los rechazos. Un rechazo explicito es tan
    importante como una aceptacion: es la prueba de que se pregunto y de que
    el alumno dijo que no, y evita volver a pedirselo.

    No hace commit: se deja en la misma transaccion que crea el usuario, para
    que sea imposible tener una cuenta sin su registro de consentimiento.
    """
    if not acepta_obligatorios:
        raise ValueError("No se puede registrar un consentimiento sin aceptar lo obligatorio")

    versiones = _versiones_vigentes(db)
    decisiones = {
        "terms": True,
        "privacy": True,
        "data_commercial": acepta_comercial,
        "ai_training": acepta_entrenamiento,
    }

    filas: list[UserConsent] = []
    for tipo, otorgado in decisiones.items():
        version = versiones.get(tipo)
        if version is None:
            # Un documento sin version vigente significa que la migracion 12
            # no se aplico. Es mejor fallar el registro que crear una cuenta
            # con un consentimiento que no se puede acreditar.
            raise ValueError(f"No hay version vigente del documento '{tipo}'")

        fila = UserConsent(
            user_id=user_id,
            doc_type=tipo,
            doc_version=version,
            granted=otorgado,
            ip_address=ip,
            user_agent=(user_agent or "")[:400] or None,
        )
        db.add(fila)
        filas.append(fila)

    return filas


def cambiar_consentimiento(
    db: Session,
    user_id: int,
    doc_type: str,
    otorgado: bool,
    ip: str | None,
    user_agent: str | None,
) -> UserConsent:
    """
    Cambia una casilla opcional desde el perfil.

    No se actualiza la fila anterior: se anade una nueva y se marca la vieja
    como revocada. El historial completo es lo que permite responder "desde
    cuando y hasta cuando estuvo autorizado esto".
    """
    if doc_type not in DOCUMENTOS_OPCIONALES:
        raise ValueError(f"'{doc_type}' no es un consentimiento revocable")

    versiones = _versiones_vigentes(db)
    version = versiones.get(doc_type)
    if version is None:
        raise ValueError(f"No hay version vigente del documento '{doc_type}'")

    ahora = datetime.now(timezone.utc)

    anteriores = db.scalars(
        select(UserConsent).where(
            UserConsent.user_id == user_id,
            UserConsent.doc_type == doc_type,
            UserConsent.revoked_at.is_(None),
        )
    ).all()
    for previa in anteriores:
        previa.revoked_at = ahora

    # Puede existir ya una fila para (user, tipo, version) de una decision
    # anterior sobre el mismo texto: el UNIQUE lo impide duplicar, asi que se
    # reutiliza en vez de insertar.
    existente = db.scalar(
        select(UserConsent).where(
            UserConsent.user_id == user_id,
            UserConsent.doc_type == doc_type,
            UserConsent.doc_version == version,
        )
    )

    if existente is not None:
        existente.granted = otorgado
        existente.granted_at = ahora
        existente.revoked_at = None
        existente.ip_address = ip
        existente.user_agent = (user_agent or "")[:400] or None
        return existente

    nueva = UserConsent(
        user_id=user_id,
        doc_type=doc_type,
        doc_version=version,
        granted=otorgado,
        granted_at=ahora,
        ip_address=ip,
        user_agent=(user_agent or "")[:400] or None,
    )
    db.add(nueva)
    return nueva


def estado_actual(db: Session, user_id: int) -> list[dict]:
    """Ultima decision vigente por tipo de documento."""
    filas = db.scalars(
        select(UserConsent)
        .where(UserConsent.user_id == user_id)
        .order_by(UserConsent.doc_type, UserConsent.granted_at.desc())
    ).all()

    visto: dict[str, dict] = {}
    for fila in filas:
        if fila.doc_type in visto:
            continue
        visto[fila.doc_type] = {
            "doc_type": fila.doc_type,
            "doc_version": fila.doc_version,
            "granted": bool(fila.granted) and fila.revoked_at is None,
            "granted_at": fila.granted_at,
        }
    return list(visto.values())
