"""Configuracion del ml-service."""
from functools import lru_cache

from revo_comun.ajustes import AjustesBase


class Ajustes(AjustesBase):
    SERVICE_NAME: str = "revo-ml"
    SERVICE_PORT: int = 8003

    #: Almacen versionado de modelos: un subdirectorio por version y un
    #: puntero `activo.json`. Sustituye a MODEL_PATH, que era un fichero
    #: unico que cada reentrenamiento sobrescribia (sin vuelta atras y sin
    #: sitio donde guardar la calibracion). Ver model/artefactos.py.
    MODEL_DIR: str = "model/saved"

    #: Ruta del .pkl del esquema anterior. Solo se usa una vez, al arrancar,
    #: para adoptarlo como version heredada si el almacen esta vacio. Sin
    #: esto, el primer despliegue del codigo nuevo se queda sin modelo activo
    #: y devuelve 503 hasta que alguien entrene a mano.
    MODEL_PATH_HEREDADO: str = "model/saved/decision_tree.pkl"

    #: Cuantas predicciones nuevas disparan un reentrenamiento automatico.
    UMBRAL_REENTRENAMIENTO: int = 50

    #: Si un candidato no supera a la regla trivial argmax(aff), ¿se despliega?
    #:
    #: Por defecto SI, pero dejando constancia. Motivo: con el dataset actual
    #: el lift es ~0 SIEMPRE, asi que bloquear la promocion dejaria al
    #: servicio sin ningun modelo y sin resultados para nadie. La regla "un
    #: modelo que no supera su linea base no se despliega" se enforza
    #: poniendo esto en True cuando el dataset deje de ser circular.
    EXIGIR_LIFT_POSITIVO: bool = False

    #: Cuanto puede empeorar un candidato respecto al modelo activo antes de
    #: rechazarlo. Un margen pequeno absorbe el ruido de particion; sin el,
    #: cualquier fluctuacion bloquearia reentrenamientos legitimos.
    TOLERANCIA_REGRESION_F1: float = 0.02

    #: El dataset de arranque es sintetico. Mientras esto sea True, los
    #: informes de calibracion llevan la advertencia pegada.
    DATASET_SINTETICO: bool = True

    #: ¿Entra el perfil de trabajo de la fase 3 (psy_a..psy_d) en el modelo?
    #:
    #: Apagado a proposito, aunque la maquinaria este hecha y probada. El
    #: motivo es un acoplamiento real: entrenar con esas columnas solo tiene
    #: sentido si en INFERENCIA tambien llegan, y hoy survey-service no las
    #: envia en /predict/ (PLAN.md, Fase 1.b). Entrenar con ellas ahora
    #: produciria un modelo que en produccion recibe un relleno neutro en
    #: cuatro de sus catorce entradas: un desplazamiento de distribucion
    #: silencioso, que degrada sin avisar.
    #:
    #: Medido sobre el dataset de arranque, activarlo vale unos +2 puntos de
    #: acierto. Se enciende en cuanto survey-service envie las proporciones.
    USAR_PERFIL_FASE3: bool = False


@lru_cache
def obtener_ajustes() -> Ajustes:
    return Ajustes()


settings = obtener_ajustes()
