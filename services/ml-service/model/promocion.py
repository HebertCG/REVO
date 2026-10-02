"""
promocion.py — Decide si un modelo recien entrenado sale a produccion.

PROBLEMA QUE RESUELVE

Antes, entrenar y desplegar eran la misma operacion: `joblib.dump` sobre la
ruta que el servicio lee. El modelo nuevo entraba en produccion sin que nadie
lo comparara con el que estaba funcionando, y sin forma de volver atras.

Eso importa especialmente aqui porque el reentrenamiento es AUTOMATICO: salta
solo al acumularse 50 predicciones nuevas (routers/predict.py). Un dataset que
se degrada (por ejemplo, por el sesgo del bucle de realimentacion) degradaba
el modelo en produccion sin intervencion humana y sin dejar rastro.

LAS DOS REGLAS

  1. NO EMPEORAR. Un candidato con F1 sensiblemente peor que el activo se
     rechaza. Con tolerancia, porque la diferencia entre dos particiones del
     mismo dataset fluctua y sin margen cualquier ruido bloquearia
     reentrenamientos legitimos.

  2. SUPERAR LA LINEA BASE. Un modelo que no gana a `argmax(aff)` no aporta
     nada que una linea de codigo no haga gratis.

POR QUE LA SEGUNDA NO BLOQUEA POR DEFECTO

Con el dataset actual el lift es ~0 SIEMPRE, por construccion del generador.
Si la regla bloqueara, no se promoveria ningun modelo nunca: el servicio se
quedaria sin modelo activo y ningun alumno recibiria resultado. La regla
quedaria "cumplida" al precio de romper el producto.

Asi que por defecto avisa y deja constancia en `model_training_logs`, y se
convierte en bloqueante (EXIGIR_LIFT_POSITIVO=True) cuando el dataset deje de
ser circular. La alternativa —callarse— es la unica que no es aceptable.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Veredicto:
    """Resultado de la puerta de promocion, con su motivo por escrito."""

    promover: bool
    motivo: str
    #: Avisos que no bloquean pero tienen que quedar registrados.
    avisos: tuple[str, ...] = ()

    def como_dict(self) -> dict:
        return {
            "promovido": self.promover,
            "motivo": self.motivo,
            "avisos": list(self.avisos),
        }


def decidir(
    metricas_candidato: dict,
    metricas_activo: dict | None,
    exigir_lift_positivo: bool = False,
    tolerancia_f1: float = 0.02,
) -> Veredicto:
    """
    Decide si el candidato sustituye al modelo activo.

    `metricas_activo` es None cuando todavia no hay ninguno: ese caso se
    promueve siempre, porque no tener modelo es peor que tener uno mediocre.
    """
    avisos: list[str] = []

    lift = float(metricas_candidato.get("lift_over_baseline", 0.0))
    f1_candidato = float(metricas_candidato.get("f1", 0.0))

    if lift <= 0:
        avisos.append(
            f"El modelo NO supera a la regla trivial argmax(aff) "
            f"(lift={lift:+.4f}). Con el dataset sintetico actual esto es lo "
            f"esperado: la etiqueta es argmax por construccion. No reportar "
            f"el accuracy como evidencia de que el modelo acierta."
        )
        if exigir_lift_positivo:
            return Veredicto(
                promover=False,
                motivo=f"rechazado_sin_lift (lift={lift:+.4f})",
                avisos=tuple(avisos),
            )

    calibracion = metricas_candidato.get("calibracion") or {}
    if calibracion and not calibracion.get("cumple_objetivo", True):
        avisos.append(
            f"ECE={calibracion.get('ece_despues')} por encima del objetivo: "
            "la confianza que se muestra al alumno no es de fiar."
        )

    if metricas_activo is None:
        return Veredicto(
            promover=True,
            motivo="primer_modelo (no habia ninguno activo)",
            avisos=tuple(avisos),
        )

    f1_activo = float(metricas_activo.get("f1", 0.0))
    caida = f1_activo - f1_candidato

    if caida > tolerancia_f1:
        return Veredicto(
            promover=False,
            motivo=(
                f"rechazado_por_regresion: F1 {f1_candidato:.4f} frente a "
                f"{f1_activo:.4f} del activo (caida {caida:.4f} > "
                f"tolerancia {tolerancia_f1})"
            ),
            avisos=tuple(avisos),
        )

    return Veredicto(
        promover=True,
        motivo=(
            f"promovido: F1 {f1_candidato:.4f} frente a {f1_activo:.4f} "
            f"del activo (diferencia {f1_candidato - f1_activo:+.4f})"
        ),
        avisos=tuple(avisos),
    )
