"""
security.py — Hash y verificacion de contrasenas.

Se usa `bcrypt` directamente en vez de passlib. Motivo: passlib 1.7.4 es de
2020 y no arranca con bcrypt >= 4.1, porque su deteccion de backend hashea
una cadena larga de prueba y las versiones nuevas de bcrypt rechazan ese
caso. Eso obligaba a clavar `bcrypt==4.0.1` en requirements.txt, es decir, a
renunciar a las correcciones de seguridad de la libreria que guarda las
contrasenas. Cambiar el pin no es una opcion: hay que quitar la dependencia.

El formato de hash no cambia (`$2b$`), asi que las contrasenas ya guardadas
con passlib se siguen verificando sin migrar nada.
"""
from __future__ import annotations

import bcrypt

#: bcrypt ignora todo lo que pase de 72 bytes. Se trunca explicitamente para
#: que el comportamiento este escrito y no dependa de la libreria.
BCRYPT_MAX_BYTES = 72

#: Coste del hash. 12 son unos ~250 ms en hardware modesto: lento para un
#: ataque por diccionario y aceptable para un login. Subirlo encarece el
#: login de toda el aula a la vez; bajarlo abarata el ataque.
BCRYPT_ROUNDS = 12


def _preparar(plain: str) -> bytes:
    """
    Convierte la contrasena a los bytes que bcrypt admite.

    Se codifica ANTES de truncar. Truncar la cadena por caracteres y despues
    codificar puede pasar de 72 bytes con acentos o enes, que es justo lo que
    bcrypt rechaza.
    """
    return plain.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    """Devuelve el hash bcrypt de una contrasena, listo para guardar."""
    return bcrypt.hashpw(_preparar(plain), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """
    Comprueba una contrasena contra su hash.

    Devuelve False ante un hash corrupto o vacio en vez de propagar la
    excepcion: un registro con el hash danado debe traducirse en "no puedes
    entrar", no en un error 500 que revela que esa cuenta existe.
    """
    if not hashed:
        return False

    try:
        return bcrypt.checkpw(_preparar(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
