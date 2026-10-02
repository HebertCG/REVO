"""
calidad.py — Detecta a quien responde sin leer, y baja la confianza declarada.

EL PROBLEMA QUE ESTO ARREGLA, MEDIDO

Se simulo un alumno que marca siempre la misma casilla: "4" en cada item
Likert y la opcion B en cada eleccion forzada. Tras 15 preguntas el motor
terminaba con:

    97 % de confianza en una rama.

Eso es peor que equivocarse: es equivocarse con seguridad. El alumno recibe
una recomendacion de carrera respaldada por un porcentaje que parece medido,
cuando lo unico que se midio fue su prisa.

Y no es un caso raro. En cuestionarios largos de autoinforme, la proporcion
de respuesta descuidada ronda el 10-15 %.

POR QUE EL MOTOR SOLO NO PUEDE VERLO

La creencia se actualiza multiplicando verosimilitudes. Una secuencia
constante de "4" ES un patron: hay ramas para las que ese patron es mas
probable que para otras, asi que la posterior se concentra igual. El modelo
no tiene forma de distinguir "este alumno de verdad valora todo parecido" de
"este alumno no leyo".

La senal no esta en QUE respondio sino en COMO: sin variar, y deprisa.

LOS TRES INDICADORES

  longstring   la racha mas larga de respuestas identicas seguidas.
               Es el indicador clasico y el mas robusto.

  varianza     dispersion de las respuestas Likert. Quien usa una sola
               casilla tiene varianza cero.

  latencia     cuanto tardo. Por debajo de ~1.5 s por item no dio tiempo a
               leer el enunciado. Es opcional: si el frontend no la manda,
               los otros dos siguen funcionando.

QUE SE HACE AL DETECTARLO

NO se descarta la sesion ni se le dice al alumno que hizo trampa. Se ATENUA
la confianza: la posterior se aplana antes de mostrarla, de modo que el
resultado sigue siendo el mismo pero deja de presentarse como seguro.

Es la misma idea que la calibracion por temperatura del ml-service, aplicada
aqui: no cambia QUE se predice, cambia CUANTO se afirma.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

#: Racha de respuestas identicas a partir de la cual se sospecha. Con 15
#: preguntas, 7 seguidas iguales es casi la mitad del test sin variar.
LONGSTRING_SOSPECHOSO = 7

#: Varianza minima esperable en una escala 1..5. Alguien que usa de verdad
#: la escala varia; por debajo de esto, o no vario o vario muy poco.
VARIANZA_MINIMA = 0.40

#: Segundos por item por debajo de los cuales no dio tiempo a leer.
LATENCIA_MINIMA_S = 1.5

#: Cuanto se aplana la posterior cuando la calidad es dudosa. Es un exponente
#: sobre las probabilidades: 0.45 lleva un 97 % a un entorno del 60 %.
#: Por debajo de 1 aplana; 1.0 no toca nada.
ATENUACION_SOSPECHOSA = 0.45
ATENUACION_DUDOSA = 0.75


@dataclass(frozen=True)
class Calidad:
    """Lectura de la calidad de una sesion."""

    veredicto: str            # "ok" | "dudosa" | "sospechosa"
    longstring: int
    varianza: float
    latencia_media_s: float | None
    motivos: tuple[str, ...]

    @property
    def atenuacion(self) -> float:
        """Exponente con el que aplanar la posterior antes de mostrarla."""
        if self.veredicto == "sospechosa":
            return ATENUACION_SOSPECHOSA
        if self.veredicto == "dudosa":
            return ATENUACION_DUDOSA
        return 1.0


def longstring(respuestas: list[int]) -> int:
    """Racha mas larga de respuestas identicas consecutivas."""
    if not respuestas:
        return 0

    mayor = actual = 1
    for anterior, siguiente in zip(respuestas, respuestas[1:]):
        actual = actual + 1 if siguiente == anterior else 1
        mayor = max(mayor, actual)
    return mayor


def varianza(respuestas: list[int]) -> float:
    """Varianza poblacional. Cero significa una sola casilla en todo el test."""
    if len(respuestas) < 2:
        return 0.0
    media = sum(respuestas) / len(respuestas)
    return sum((x - media) ** 2 for x in respuestas) / len(respuestas)


def evaluar(
    respuestas: list[int],
    latencias_ms: list[int] | None = None,
    minimo_para_juzgar: int = 6,
) -> Calidad:
    """
    Juzga la calidad de una sesion.

    `minimo_para_juzgar` evita marcar como sospechosa una sesion de tres
    respuestas: tres iguales seguidas son perfectamente normales, y acusar
    de no leer a quien apenas empezo seria un falso positivo garantizado.
    """
    racha = longstring(respuestas)
    var = varianza(respuestas)
    latencia = (
        sum(latencias_ms) / len(latencias_ms) / 1000.0
        if latencias_ms else None
    )

    if len(respuestas) < minimo_para_juzgar:
        return Calidad("ok", racha, round(var, 3), latencia,
                       ("sesion demasiado corta para juzgar",))

    motivos = []
    if racha >= LONGSTRING_SOSPECHOSO:
        motivos.append(f"{racha} respuestas identicas seguidas")
    if var < VARIANZA_MINIMA:
        motivos.append(f"varianza {var:.2f}, por debajo de {VARIANZA_MINIMA}")
    if latencia is not None and latencia < LATENCIA_MINIMA_S:
        motivos.append(f"{latencia:.1f} s por pregunta, no da tiempo a leer")

    # Dos indicadores o mas: sospechosa. Uno solo: dudosa. Exigir dos para
    # el veredicto duro reduce los falsos positivos, que aqui son caros:
    # atenuar la confianza de alguien que si respondio en serio le quita
    # informacion util.
    if len(motivos) >= 2:
        veredicto = "sospechosa"
    elif motivos:
        veredicto = "dudosa"
    else:
        veredicto = "ok"

    return Calidad(veredicto, racha, round(var, 3), latencia, tuple(motivos))


def atenuar(probabilidades: tuple[float, ...], exponente: float) -> tuple[float, ...]:
    """
    Aplana la posterior sin cambiar el orden de las ramas.

    p^a normalizado, con a < 1. Es monotona, asi que la rama ganadora sigue
    siendo la misma: lo unico que cambia es cuanta confianza se declara.
    Exactamente el mismo mecanismo que la calibracion por temperatura del
    ml-service.
    """
    if exponente >= 1.0:
        return probabilidades

    elevadas = [p ** exponente for p in probabilidades]
    total = sum(elevadas)
    return tuple(p / total for p in elevadas)


def explicar(calidad: Calidad) -> str | None:
    """
    Aviso para el panel de administracion. None si no hay nada que decir.

    NO es un mensaje para el alumno: decirle "creemos que no leiste" seria
    acusarlo a partir de una heuristica. El alumno solo ve una confianza mas
    baja, que es la consecuencia honesta.
    """
    if calidad.veredicto == "ok":
        return None
    return (
        f"Calidad {calidad.veredicto}: {'; '.join(calidad.motivos)}. "
        f"La confianza mostrada se atenuo con exponente {calidad.atenuacion}."
    )
