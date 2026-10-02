"""
ocupaciones.py — Que perfil RIASEC le atribuye el modelo a un alumno.

PROBLEMA QUE RESUELVE

El resultado dice "Ciberseguridad, 72 %", pero no conecta con el mundo del
trabajo. O*NET tiene el perfil de intereses de 923 ocupaciones reales; si se
conoce el perfil del alumno, se pueden buscar las que mas se le parecen.

DE DONDE SALE EL PERFIL DEL ALUMNO

Lo ideal es medirlo con el Mini-IP (student_profiles.forma_riasec, que ya se
rellena sola en cuanto survey-service guarde el perfil). Mientras el
instrumento no se administre en el producto, se ESTIMA a partir de la
prediccion:

    perfil = suma de  P(rama) x perfil RIASEC de la rama

con las probabilidades CALIBRADAS. Es el perfil de intereses que el modelo le
atribuye al alumno: si duda entre Desarrollo y Ciberseguridad, el perfil
queda entre los dos. Se presenta como estimado, porque lo es.
"""
from __future__ import annotations


def perfil_esperado(
    probabilidades: dict[int, float],
    perfiles_ramas: dict[int, list[float]],
) -> list[float] | None:
    """
    Media de los perfiles de las ramas, ponderada por su probabilidad.

    Solo cuentan las ramas con perfil cargado, y se renormaliza: una rama
    sin perfil no puede tirar del resultado hacia cero. Sin ninguna, None.
    """
    pesos = {
        rama: p for rama, p in probabilidades.items()
        if rama in perfiles_ramas and p > 0
    }
    total = sum(pesos.values())
    if total <= 0:
        return None

    dimensiones = len(next(iter(perfiles_ramas.values())))
    return [
        sum(p * perfiles_ramas[rama][d] for rama, p in pesos.items()) / total
        for d in range(dimensiones)
    ]
