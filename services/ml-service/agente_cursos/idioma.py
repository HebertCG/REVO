"""
idioma.py — En que lengua esta escrito un titulo o una descripcion.

POR QUE HACE FALTA

Buscar en espanol no garantiza que vuelva espanol. "Curso" se escribe igual
en portugues, y la comunidad brasilena de GitHub es enorme: en una pasada
real sobre Infraestructura, de los tres primeros candidatos de cada nivel,
cinco de nueve eran brasilenos. Tambien vuelve material en ingles.

EL DEFECTO QUE ESTO SUSTITUYE

La primera version contaba articulos y preposiciones, e incluia "para" y
"desde" como marcas de espanol. Las dos existen en portugues. Resultado,
con texto literal de repositorios reales:

    "...redes sociais e projetos de referencias para desenvolvedores"  -> es
    "This is the most modern and comprehensive course..."               -> pt
    "Entornos de Desarrollo - Clean Code y TDD"                          -> ?

Las tres mal.

SOLO CUENTA LO QUE ES EXCLUSIVO DE UNA LENGUA

    letras    ñ ¿ ¡                          -> espanol
              ã õ ç â ê ô à                  -> portugues
    palabras  y el la los del con una en...  -> espanol
              e com um na ao voce nao mais   -> portugues
              the and of for with course...  -> ingles
    sufijo    -cion, -ciones                 -> espanol (el portugues
                                                escribe -cao, que ya
                                                cuenta por la letra)

Lo que existe en mas de una NO cuenta: para, desde, de, a, o, no, curso,
gratis, sobre, como. "o" es "el" en portugues pero "o" en espanol; "dos"
es "de los" en portugues pero "2" en espanol.

Una letra pesa el doble que una palabra: una ñ es casi una prueba, una
palabra suelta puede ser un nombre propio.

POR QUE NO UNA LIBRERIA

langdetect, lingua o fastText resuelven esto en general, pero aqui el
problema es estrecho —tres lenguas, textos de una linea— y lo que hace
falta es poder explicar cada decision y probarla con los casos que fallaron.
Esto cabe en una pantalla y no trae dependencias. Si aparece una cuarta
lengua relevante, ese es el momento de reconsiderarlo.

TEXTOS QUE NI SIQUIERA SON LATINOS

GitHub casa "curso" con "Cursor", y "curso linux" devolvio un repositorio
en chino. Sin ninguna marca latina salia None y pasaba el filtro. Si mas de
un 20 % de las letras no son latinas, se devuelve "otro": no hace falta
saber que lengua es para saber que no es espanol.

ANTE LA DUDA, None

Empate o ninguna senal devuelve None, que puntua 0.5 y NO se descarta.
Admitir que no se sabe es mejor que afirmar de mas: es el mismo criterio
que sigue el resto del sistema con la incertidumbre.
"""
from __future__ import annotations

import re

LETRAS = {
    "es": frozenset("ñ¿¡"),
    "pt": frozenset("ãõçâêôà"),
}

PALABRAS = {
    "es": frozenset({
        "y", "el", "la", "los", "las", "del", "al", "con", "un", "una",
        "en", "es", "lo", "aprende", "desarrollo", "proyecto",
    }),
    "pt": frozenset({
        "e", "com", "os", "um", "uma", "na", "ao", "em", "da", "das", "do",
        "pelo", "pela", "voce", "você", "nao", "não", "mais", "esse", "essa",
        "isso", "novo", "nova", "seu", "sua", "projeto", "aulas", "é",
        # Con tilde solo existe en portugues: en espanol es "gratis".
        "grátis",
    }),
    "en": frozenset({
        "the", "and", "of", "for", "with", "this", "is", "to", "your",
        "from", "course", "learn", "how", "that", "you", "are", "in",
    }),
}

SUFIJOS_ES = ("cion", "ción", "ciones")

PESO_LETRA = 2
PESO_PALABRA = 1

#: Fraccion de letras fuera del alfabeto latino a partir de la cual el texto
#: se da por escrito en otra lengua. Deja pasar un nombre propio suelto en
#: griego o japones dentro de una frase en espanol.
PROPORCION_NO_LATINA = 0.2

#: Hasta aqui llegan el latin basico, el suplemento Latin-1 y los latinos
#: extendidos A y B, donde estan todas las letras del espanol y el portugues.
_ULTIMA_LATINA = 0x024F

_PALABRA = re.compile(r"[^\W\d_]+")


def detectar(*textos: str | None) -> str | None:
    """'es', 'pt', 'en', 'otro' (alfabeto no latino) o None si no hay evidencia."""
    texto = " ".join(t for t in textos if t).lower()
    if not texto:
        return None

    letras = [c for c in texto if c.isalpha()]
    no_latinas = sum(1 for c in letras if ord(c) > _ULTIMA_LATINA)
    if letras and no_latinas / len(letras) > PROPORCION_NO_LATINA:
        return "otro"

    puntos = {lengua: 0 for lengua in PALABRAS}

    for lengua, letras in LETRAS.items():
        puntos[lengua] += PESO_LETRA * sum(texto.count(letra) for letra in letras)

    for palabra in _PALABRA.findall(texto):
        for lengua, vocabulario in PALABRAS.items():
            if palabra in vocabulario:
                puntos[lengua] += PESO_PALABRA
        if palabra.endswith(SUFIJOS_ES):
            puntos["es"] += PESO_PALABRA

    primera, segunda = sorted(puntos.values(), reverse=True)[:2]
    if primera == 0 or primera == segunda:
        return None
    return max(puntos, key=puntos.get)
