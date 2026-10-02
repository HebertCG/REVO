"""
perfil_psicometrico.py — De respuestas a perfil RIASEC / Big Five, y de ahi
al encaje con cada especializacion.

QUE RESUELVE

Es la otra mitad del anclaje externo. La primera mitad (database/onet/) puso
el perfil RIASEC de cada rama a partir del catalogo del Departamento de
Trabajo de EE. UU. Esta pone el del ALUMNO, medido con un instrumento
publicado, y las compara.

Con las dos mitades, la cadena deja de morderse la cola:

    ANTES:   "me gusta la rama 4"           -> el modelo predice la rama 4
    AHORA:   "me gustaria reparar           -> perfil RIASEC del alumno
              electrodomesticos"               -> encaje con perfiles O*NET
                                               -> ranking de ramas

Ningun item menciona una especializacion de Ingenieria de Sistemas. Esa es
justamente la propiedad que hace que el resultado no sea un eco de la
pregunta.

PUNTUACION: LA DE LOS MANUALES, NO UNA INVENTADA

  Mini-IP   escala 0..4 por item, puntuacion de cada tipo = SUMA de sus 5
            items, rango 0..20. (Rounds et al., 2016, seccion "Scoring for
            Paper-and-Pencil and Computerized IP".)

  Mini-IPIP escala 1..5 por item, los items con keyed=-1 se invierten
            (6 - valor), y cada factor = MEDIA de sus 4. (Donnellan et al.,
            2006.)

Respetarlas importa: cambiar la formula rompe la comparabilidad con la
literatura, que es lo unico que estos instrumentos aportan sobre inventarse
las preguntas.

EL ENCAJE: CORRELACION DE PERFILES

El perfil del alumno esta en escala 0..20 y el de la ocupacion en la escala
1..7 de O*NET. No son comparables punto a punto, asi que se usa la
CORRELACION de Pearson entre los seis valores.

La correlacion es invariante a escala y a desplazamiento, que es justo lo
que hace falta: lo que importa no es si el alumno puntua alto en todo, sino
la FORMA de su perfil — que dimensiones destacan sobre sus propias demas.
Eso ademas neutraliza el sesgo de aquiescencia (quien marca "me gusta" a
todo sale con el mismo perfil relativo).

Es ademas la practica habitual en psicologia vocacional para medir
congruencia entre perfiles.
"""
from __future__ import annotations

import math

#: Orden canonico de Holland. No se cambia: los perfiles de O*NET vienen en
#: este orden y compararlos desordenados daria correlaciones sin sentido.
RIASEC = ("R", "I", "A", "S", "E", "C")
BIG_FIVE = ("E", "A", "C", "N", "O")

#: Rango de respuesta de cada instrumento, segun su manual.
MINI_IP_MIN, MINI_IP_MAX = 0, 4
MINI_IPIP_MIN, MINI_IPIP_MAX = 1, 5

#: Items por escala. Si llegan menos, el perfil sigue calculandose pero
#: queda marcado como incompleto: una dimension con 2 de 5 items no es
#: comparable con otra que tiene los 5.
ITEMS_POR_DIMENSION_RIASEC = 5
ITEMS_POR_FACTOR_BIGFIVE = 4


class RespuestaInvalida(ValueError):
    """Una respuesta fuera del rango que el manual define."""


def puntuar_riasec(respuestas: dict[int, int], items: dict[int, str]) -> dict:
    """
    Suma las respuestas de cada tipo Holland.

    `respuestas` es {item_id: valor 0..4} y `items` es {item_id: dimension},
    que sale de la tabla riasec_items.

    Se valida el rango en vez de recortarlo: un 7 en una escala 0..4 no es
    un valor extremo, es un error de quien llama, y recortarlo en silencio
    lo esconde hasta que alguien analice los datos meses despues.
    """
    puntos = {d: 0 for d in RIASEC}
    contados = {d: 0 for d in RIASEC}

    for item_id, valor in respuestas.items():
        dimension = items.get(item_id)
        if dimension is None:
            raise RespuestaInvalida(f"El item {item_id} no pertenece al Mini-IP")
        if not (MINI_IP_MIN <= valor <= MINI_IP_MAX):
            raise RespuestaInvalida(
                f"El item {item_id} vale {valor}; el Mini-IP usa "
                f"{MINI_IP_MIN}..{MINI_IP_MAX}"
            )
        puntos[dimension] += valor
        contados[dimension] += 1

    return {
        "perfil": {d: puntos[d] for d in RIASEC},
        "n_respuestas": sum(contados.values()),
        "completo": all(c == ITEMS_POR_DIMENSION_RIASEC for c in contados.values()),
        "por_dimension": contados,
        "codigo_holland": codigo_holland(puntos),
    }


def codigo_holland(perfil: dict[str, float]) -> str:
    """
    Las tres dimensiones mas altas, en orden. Ej: 'IRC'.

    Es como se expresa un perfil RIASEC en la literatura y como se compara
    con una ocupacion. Los empates se rompen por el orden canonico R-I-A-S-E-C,
    que es arbitrario pero DETERMINISTA: un codigo que cambia entre dos
    ejecuciones con los mismos datos no es un diagnostico.
    """
    orden = sorted(RIASEC, key=lambda d: (-perfil.get(d, 0), RIASEC.index(d)))
    return "".join(orden[:3])


def puntuar_bigfive(respuestas: dict[int, int], items: dict[int, tuple[str, int]]) -> dict:
    """
    Media de cada factor, invirtiendo los items con keyed = -1.

    `items` es {item_id: (factor, keyed)}, de la tabla bigfive_items.

    La inversion no es un detalle de formato: los items invertidos son lo
    que impide que alguien que contesta lo mismo a todo saque un perfil
    coherente. Olvidarla produce factores con el signo cambiado y un perfil
    que parece valido.
    """
    suma = {f: 0.0 for f in BIG_FIVE}
    contados = {f: 0 for f in BIG_FIVE}

    for item_id, valor in respuestas.items():
        entrada = items.get(item_id)
        if entrada is None:
            raise RespuestaInvalida(f"El item {item_id} no pertenece al Mini-IPIP")
        if not (MINI_IPIP_MIN <= valor <= MINI_IPIP_MAX):
            raise RespuestaInvalida(
                f"El item {item_id} vale {valor}; el Mini-IPIP usa "
                f"{MINI_IPIP_MIN}..{MINI_IPIP_MAX}"
            )
        factor, keyed = entrada
        # 6 - valor, no 5 - valor: la escala es 1..5, asi que el espejo de 1
        # es 5 y el de 5 es 1. Con 5 - valor el espejo de 1 seria 4.
        suma[factor] += valor if keyed == 1 else (MINI_IPIP_MAX + MINI_IPIP_MIN - valor)
        contados[factor] += 1

    return {
        "perfil": {
            f: round(suma[f] / contados[f], 2) if contados[f] else None
            for f in BIG_FIVE
        },
        "n_respuestas": sum(contados.values()),
        "completo": all(c == ITEMS_POR_FACTOR_BIGFIVE for c in contados.values()),
        "por_factor": contados,
    }


# ── Encaje con las especializaciones ─────────────────────────

def correlacion(a: list[float], b: list[float]) -> float:
    """
    Pearson entre dos perfiles. Devuelve 0.0 si alguno es plano.

    Un perfil plano (el alumno marco lo mismo en las seis dimensiones) no
    tiene forma que correlacionar. Devolver 0 es lo honesto: no se parece ni
    se deja de parecer a nada, no hay informacion.
    """
    n = len(a)
    if n != len(b) or n == 0:
        raise ValueError("Los perfiles tienen que tener la misma longitud")

    media_a, media_b = sum(a) / n, sum(b) / n
    da = [x - media_a for x in a]
    db = [y - media_b for y in b]

    num = sum(x * y for x, y in zip(da, db))
    den = math.sqrt(sum(x * x for x in da) * sum(y * y for y in db))
    return 0.0 if den == 0 else num / den


def encaje_con_ramas(perfil_alumno: dict[str, float], perfiles_ramas: dict) -> list[dict]:
    """
    Ordena las ramas por parecido con el perfil del alumno.

    `perfiles_ramas` es el JSON de database/onet/perfiles_ramas.json.

    Devuelve tambien las letras compartidas del codigo Holland, que es la
    medida clasica de congruencia y la que se puede explicar al alumno sin
    hablar de correlaciones.
    """
    vector_alumno = [float(perfil_alumno.get(d, 0)) for d in RIASEC]
    codigo_alumno = codigo_holland(perfil_alumno)

    resultado = []
    for rama_id, rama in perfiles_ramas["ramas"].items():
        r = correlacion(vector_alumno, rama["riasec"])
        codigo_rama = codigo_holland(dict(zip(RIASEC, rama["riasec"])))
        resultado.append({
            "specialization_id": int(rama_id),
            "nombre": rama["nombre"],
            "correlacion": round(r, 4),
            "codigo_holland": codigo_rama,
            # Cuantas de las tres letras del alumno aparecen en las de la
            # rama, sin importar el orden. 3 = congruencia total.
            "letras_compartidas": len(set(codigo_alumno) & set(codigo_rama)),
        })

    return sorted(
        resultado,
        key=lambda x: (-x["correlacion"], -x["letras_compartidas"], x["specialization_id"]),
    )
