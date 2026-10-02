"""
sombra.py — Ejecuta el motor en paralelo al cuestionario, sin tocarlo.

QUE HACE

Al cerrar una sesion, coge las respuestas que el alumno REALMENTE dio, las
pasa por el modelo de creencia, y compara su ranking con el del metodo
actual (sumar puntos por rama). El resultado se guarda en
`sombra_adaptativa` y el alumno no nota nada.

Cuando haya suficientes sesiones reales, esa tabla dira si merece la pena
cambiar el metodo. Hasta entonces, la decision solo tendria datos
sinteticos detras.

LO QUE MIDE Y LO QUE NO

Mide el MODELO DE CREENCIA: dadas las mismas respuestas, ¿ordena mejor?

NO mide el SELECTOR adaptativo. El motor habria preguntado otras cosas y no
existen las respuestas a preguntas que nadie hizo. Para medir el ahorro de
preguntas hay que ponerlo en vivo; esto es el paso previo.

REGLA DE ORO: ESTO NO PUEDE ROMPER EL CUESTIONARIO

Un alumno que termina su test y recibe un error porque fallo una medicion
paralela es inaceptable. `registrar` captura TODA excepcion y solo deja
rastro en el log.

Es la excepcion consciente a la regla del proyecto de no tragarse errores:
aqui el fallo no afecta a lo que el alumno pidio, y propagarlo convertiria
una instrumentacion opcional en un punto unico de fallo.
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from motor_adaptativo import artefacto as art
from motor_adaptativo import calidad as cal
from motor_adaptativo import creencia as cr

logger = logging.getLogger("revo.survey.sombra")

N_RAMAS = 10


def _ranking_desde_puntos(puntuaciones: dict[int, float]) -> list[dict]:
    """
    El metodo ACTUAL: sumar puntos por rama y normalizar.

    Se normaliza a proporciones para que los dos rankings sean comparables.
    Sin eso se estaria comparando una suma de 0 a 30 con una probabilidad.
    """
    total = sum(puntuaciones.values()) or 1.0
    ordenado = sorted(
        puntuaciones.items(), key=lambda par: (-par[1], par[0])
    )
    return [{"rama": rama, "p": round(valor / total, 4)} for rama, valor in ordenado]


def _ranking_desde_creencia(probabilidades: tuple[float, ...]) -> list[dict]:
    return [
        {"rama": rama, "p": round(p, 4)}
        for rama, p in cr.top(probabilidades, N_RAMAS)
    ]


def calcular(
    respuestas: list[tuple[int, float]],
    puntuaciones_actuales: dict[int, float],
    modelo: dict,
) -> dict | None:
    """
    Compara los dos metodos sobre las mismas respuestas.

    `respuestas` es [(question_id, valor 1..5)] EN EL ORDEN en que se
    contestaron. El orden importa: el descuento por rama repetida depende de
    cuantas preguntas de esa rama se llevaban ya.

    Devuelve None si no hay nada que comparar.
    """
    if not respuestas:
        return None

    estado = cr.inicial(N_RAMAS)
    valores = []

    for question_id, valor in respuestas:
        clave = f"q:{question_id}"
        tabla = art.tabla_de(modelo, clave)
        if tabla is None:
            # Una pregunta del banco viejo, jubilado en la migracion 28. No
            # esta en el artefacto y no se puede puntuar: se salta en vez de
            # fallar, porque hay 655 sesiones historicas llenas de esas.
            continue

        # El valor llega 1..5 y el tensor indexa 0..4.
        indice = max(0, min(int(round(valor)) - 1, len(tabla[0]) - 1))
        valores.append(indice)

        meta = art.meta_de(modelo, clave) or {}
        estado = cr.actualizar(
            estado, tabla, indice, clave,
            rama_item=meta.get("rama"), categoria=meta.get("categoria"),
        )

    if estado.n_preguntas == 0:
        return None

    probabilidades = cr.posterior(estado)
    ranking_motor = _ranking_desde_creencia(probabilidades)
    ranking_actual = _ranking_desde_puntos(puntuaciones_actuales)

    top3_motor = {fila["rama"] for fila in ranking_motor[:3]}
    top3_actual = {fila["rama"] for fila in ranking_actual[:3]}
    lectura = cal.evaluar(valores)

    return {
        "motor_version": modelo.get("version", "desconocida"),
        "hash_banco": modelo.get("hash_banco", ""),
        "ranking_actual": ranking_actual,
        "ranking_motor": ranking_motor,
        "coincide_top1": ranking_actual[0]["rama"] == ranking_motor[0]["rama"],
        "coincide_top3": top3_actual == top3_motor,
        "ramas_comunes": len(top3_actual & top3_motor),
        "entropia": round(cr.entropia(probabilidades), 3),
        "margen_34": round(cr.margen_en(probabilidades, 3), 4),
        "calidad": lectura.veredicto,
        "longstring": lectura.longstring,
        "varianza": lectura.varianza,
        "n_respuestas": estado.n_preguntas,
    }


SENTENCIA = text("""
    INSERT INTO sombra_adaptativa (
        session_id, motor_version, hash_banco, ranking_actual, ranking_motor,
        coincide_top1, coincide_top3, ramas_comunes, entropia, margen_34,
        calidad, longstring, varianza, n_respuestas
    ) VALUES (
        :session_id, :motor_version, :hash_banco,
        CAST(:ranking_actual AS jsonb), CAST(:ranking_motor AS jsonb),
        :coincide_top1, :coincide_top3, :ramas_comunes, :entropia, :margen_34,
        :calidad, :longstring, :varianza, :n_respuestas
    )
    ON CONFLICT (session_id) DO NOTHING
""")


def registrar(
    db: Session,
    session_id: int,
    respuestas: list[tuple[int, float]],
    puntuaciones_actuales: dict[int, float],
) -> None:
    """
    Calcula y guarda la sombra. NUNCA lanza.

    El `except` amplio es deliberado y esta justificado en el encabezado del
    modulo: el alumno acaba de terminar su cuestionario y lo que pidio es su
    resultado, no una medicion paralela.
    """
    try:
        modelo = art.activo()
        fila = calcular(respuestas, puntuaciones_actuales, modelo)
        if fila is None:
            return

        import json
        db.execute(SENTENCIA, {
            **fila,
            "session_id": session_id,
            "ranking_actual": json.dumps(fila["ranking_actual"]),
            "ranking_motor": json.dumps(fila["ranking_motor"]),
        })
        db.commit()

        if not fila["coincide_top1"] and fila["calidad"] == "ok":
            # Las discrepancias en sesiones de calidad son lo unico que
            # ensena algo. Se registran para poder mirarlas sin esperar al
            # panel.
            logger.info(
                "Sombra %s: los metodos discrepan. actual=%s motor=%s entropia=%s",
                session_id, fila["ranking_actual"][0]["rama"],
                fila["ranking_motor"][0]["rama"], fila["entropia"],
            )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error(
            "La sombra de la sesion %s fallo (el alumno no se ve afectado): %s",
            session_id, exc, exc_info=True,
        )
