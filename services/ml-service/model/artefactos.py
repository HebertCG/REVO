"""
artefactos.py — Almacen versionado de modelos entrenados.

PROBLEMA QUE RESUELVE

Antes, entrenar hacia esto:

    joblib.dump(clf, settings.MODEL_PATH)

sobre una ruta unica y fija (`model/saved/decision_tree.pkl`, nombre heredado
de cuando el modelo era un arbol). Tres consecuencias, todas graves:

  1. NO HAY VUELTA ATRAS. El modelo en produccion se reemplaza en el acto.
     Si el nuevo es peor, el anterior ya no existe.

  2. NO HAY DONDE GUARDAR LO QUE ACOMPANA AL MODELO. Una temperatura de
     calibracion o un umbral conformal solo valen para EL modelo con el que
     se calcularon. Guardarlos sueltos en la configuracion o en la base los
     desacopla del artefacto, y en el primer reentrenamiento pasan a
     describir un modelo que ya no existe.

  3. NO SE SABE QUE MODELO PRODUJO QUE PREDICCION. `predictions.model_version`
     guardaba la constante 'v1.0' de la configuracion mientras
     `model_training_logs` guardaba la version real. Con eso, cualquier
     analisis de deriva o comparacion entre versiones es imposible.

QUE HACE ESTE MODULO

Un directorio por version, y un puntero que dice cual esta activa:

    model/saved/
    ├── activo.json                  {"version": "v20260920_2145"}
    └── v20260920_2145/
        ├── modelo.pkl
        ├── metadatos.json           algoritmo, features, metricas
        ├── calibracion.json         temperatura y su evaluacion
        └── conformal.json           umbral y cobertura objetivo

Promover es mover el puntero, y es una operacion aparte de guardar. Esa
separacion es la que permite entrenar un candidato, medirlo contra el que
esta en produccion y decidir DESPUES si se despliega.

El puntero se escribe con fichero temporal + reemplazo atomico: si el proceso
muere a mitad, el puntero sigue apuntando a la version anterior completa, en
vez de quedar truncado y dejar al servicio sin modelo.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

logger = logging.getLogger("revo.ml.artefactos")

#: Nombres dentro del directorio de cada version. Constantes y no cadenas
#: sueltas: se nombran desde el entrenador, el predictor y las pruebas.
FICHERO_MODELO = "modelo.pkl"
FICHERO_CONJUNTO = "conjunto.pkl"
FICHERO_METADATOS = "metadatos.json"
FICHERO_CALIBRACION = "calibracion.json"
FICHERO_CONFORMAL = "conformal.json"
FICHERO_PUNTERO = "activo.json"

#: Version que se asigna al .pkl suelto que pudiera existir de antes de este
#: modulo. Permite adoptarlo sin perderlo y sin fingir que tiene fecha.
VERSION_HEREDADA = "v0-heredada"


@dataclass(frozen=True)
class Artefacto:
    """Un modelo entrenado junto a todo lo que solo vale para el."""

    version: str
    modelo: Any
    metadatos: dict
    #: None mientras el modelo no se haya calibrado. Que sea opcional es
    #: deliberado: un modelo sin calibrar tiene que poder servir, avisando.
    calibracion: dict | None = None
    conformal: dict | None = None
    #: Conjunto bootstrap para la incertidumbre epistemica. Opcional por el
    #: mismo motivo: si no esta, se sirve sin esa medida en vez de no servir.
    conjunto: list | None = None

    @property
    def temperatura(self) -> float:
        """
        Temperatura de calibracion, o 1.0 si el modelo no esta calibrado.

        1.0 deja las probabilidades como las devuelve el modelo, asi que el
        camino sin calibrar funciona sin ramificar en el codigo que la usa.
        """
        if not self.calibracion:
            return 1.0
        return float(self.calibracion.get("temperatura", 1.0))

    @property
    def esta_calibrado(self) -> bool:
        return bool(self.calibracion)


class ArtefactoNoEncontrado(FileNotFoundError):
    """No hay modelo activo, o la version pedida no existe."""


# ── Rutas ────────────────────────────────────────────────────

def ruta_de(base: str | Path, version: str) -> Path:
    """Directorio de una version. `version` se sanea: nunca sale de `base`."""
    limpia = _sanear(version)
    return Path(base) / limpia


def version_libre(base: str | Path, propuesta: str) -> str:
    """
    Devuelve `propuesta`, o la primera variante libre si ya existe.

    PROBLEMA QUE RESUELVE

    La version se construye con marca de tiempo al segundo
    (`v20260921_023344`). Dos entrenamientos dentro del MISMO segundo
    producen la misma cadena, y entonces el segundo sobrescribe el
    directorio del primero.

    La consecuencia no es solo perder un artefacto: la puerta de promocion
    lee las metricas del modelo activo para comparar, y si el candidato ya
    piso ese directorio, la puerta se compara CONSIGO MISMA y aprueba
    cualquier cosa. Es un fallo silencioso que anula la proteccion entera.

    Pasa de verdad: en las pruebas ocurre constantemente, y en produccion
    puede ocurrir con dos reentrenamientos automaticos simultaneos.
    """
    if not (ruta_de(base, propuesta) / FICHERO_MODELO).exists():
        return propuesta
    for intento in range(2, 100):
        candidata = f"{propuesta}_{intento}"
        if not (ruta_de(base, candidata) / FICHERO_MODELO).exists():
            return candidata
    raise RuntimeError(f"Cien versiones con el prefijo {propuesta}: algo va mal")


def _sanear(version: str) -> str:
    """
    Impide que una version escape del directorio base.

    `version` acaba viniendo de la base de datos o de una peticion de
    administracion. Sin esto, una version '../../etc' escribe o lee fuera del
    almacen. Es barato y cierra una via de recorrido de rutas.
    """
    limpia = os.path.basename(str(version)).strip()
    if not limpia or limpia in (".", ".."):
        raise ValueError(f"Version no valida: {version!r}")
    return limpia


# ── Escritura ────────────────────────────────────────────────

def guardar(
    base: str | Path,
    version: str,
    modelo: Any,
    metadatos: dict,
    calibracion: dict | None = None,
    conformal: dict | None = None,
    conjunto: list | None = None,
) -> Path:
    """
    Escribe una version completa. NO la promueve: eso es `promover`.

    Separar guardar de promover es lo que permite entrenar un candidato y
    decidir despues, comparandolo con el que ya esta en produccion.
    """
    destino = ruta_de(base, version)
    destino.mkdir(parents=True, exist_ok=True)

    joblib.dump(modelo, destino / FICHERO_MODELO)
    _escribir_json(destino / FICHERO_METADATOS, {**metadatos, "version": version})

    if calibracion is not None:
        _escribir_json(destino / FICHERO_CALIBRACION, calibracion)
    if conformal is not None:
        _escribir_json(destino / FICHERO_CONFORMAL, conformal)
    if conjunto:
        joblib.dump(conjunto, destino / FICHERO_CONJUNTO)

    logger.info("Artefacto %s guardado en %s", version, destino)
    return destino


def promover(base: str | Path, version: str) -> None:
    """
    Apunta el puntero de version activa a `version`.

    Se niega a promover una version que no este completa: un puntero a un
    directorio sin modelo deja el servicio devolviendo 503 sin explicar por
    que.
    """
    destino = ruta_de(base, version)
    if not (destino / FICHERO_MODELO).exists():
        raise ArtefactoNoEncontrado(
            f"No se puede promover {version}: falta {FICHERO_MODELO} en {destino}"
        )

    _escribir_json_atomico(Path(base) / FICHERO_PUNTERO, {"version": _sanear(version)})
    logger.info("Version activa: %s", version)


def _escribir_json(ruta: Path, datos: dict) -> None:
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")


def _escribir_json_atomico(ruta: Path, datos: dict) -> None:
    """
    Escribe en un temporal del MISMO directorio y reemplaza.

    Mismo directorio porque os.replace solo es atomico dentro de un sistema
    de ficheros. Un temporal en /tmp puede estar en otro y degradar a copia,
    que es justo lo que se quiere evitar.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(dir=str(ruta.parent), suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as fichero:
            json.dump(datos, fichero, indent=2, ensure_ascii=False)
            fichero.flush()
            os.fsync(fichero.fileno())
        os.replace(temporal, ruta)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise


# ── Lectura ──────────────────────────────────────────────────

def version_activa(base: str | Path) -> str | None:
    """Version en produccion, o None si todavia no se ha promovido ninguna."""
    puntero = Path(base) / FICHERO_PUNTERO
    if not puntero.exists():
        return None
    try:
        return json.loads(puntero.read_text(encoding="utf-8")).get("version")
    except (json.JSONDecodeError, OSError) as exc:
        # Un puntero corrupto no debe hacerse pasar por "no hay modelo": son
        # dos situaciones distintas y solo una es normal.
        logger.error("El puntero de version activa esta corrupto: %s", exc)
        return None


def versiones(base: str | Path) -> list[str]:
    """Versiones guardadas, de la mas reciente a la mas antigua."""
    raiz = Path(base)
    if not raiz.exists():
        return []
    encontradas = [
        hijo.name for hijo in raiz.iterdir()
        if hijo.is_dir() and (hijo / FICHERO_MODELO).exists()
    ]
    return sorted(encontradas, reverse=True)


def cargar(base: str | Path, version: str) -> Artefacto:
    """Carga una version concreta con todo lo que la acompana."""
    origen = ruta_de(base, version)
    fichero = origen / FICHERO_MODELO
    if not fichero.exists():
        raise ArtefactoNoEncontrado(f"No existe el modelo de la version {version}")

    fichero_conjunto = origen / FICHERO_CONJUNTO
    conjunto = None
    if fichero_conjunto.exists():
        try:
            conjunto = joblib.load(fichero_conjunto)
        except Exception as exc:  # noqa: BLE001
            # El conjunto es opcional: si no se puede leer, se sirve sin la
            # medida epistemica. Perderla es peor que no servir? No: no
            # servir deja al alumno sin resultado.
            logger.error("No se pudo cargar el conjunto de %s: %s", version, exc)

    return Artefacto(
        version=version,
        modelo=joblib.load(fichero),
        metadatos=_leer_json(origen / FICHERO_METADATOS) or {},
        calibracion=_leer_json(origen / FICHERO_CALIBRACION),
        conformal=_leer_json(origen / FICHERO_CONFORMAL),
        conjunto=conjunto,
    )


def cargar_activo(base: str | Path) -> Artefacto:
    """Carga la version en produccion. Falla con un mensaje accionable."""
    version = version_activa(base)
    if version is None:
        raise ArtefactoNoEncontrado(
            f"No hay modelo activo en {base}. Entrene primero (POST /stats/train)."
        )
    return cargar(base, version)


def _leer_json(ruta: Path) -> dict | None:
    if not ruta.exists():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("No se pudo leer %s: %s", ruta, exc)
        return None


# ── Adopcion del modelo anterior a este modulo ───────────────

def adoptar_heredado(base: str | Path, ruta_pkl: str | Path) -> str | None:
    """
    Convierte un .pkl suelto en una version del almacen y la promueve.

    Sirve para el despliegue en el que ya hay un modelo entrenado bajo el
    esquema viejo. Sin esto, la primera vez que arranca el codigo nuevo no
    hay version activa y el servicio devuelve 503 hasta que alguien entrene
    a mano, cosa que nadie descubriria hasta que un alumno terminara el
    cuestionario.

    Devuelve la version creada, o None si no habia nada que adoptar.
    """
    origen = Path(ruta_pkl)
    if not origen.exists():
        return None
    if version_activa(base) is not None:
        return None  # Ya hay almacen: no se toca.

    destino = ruta_de(base, VERSION_HEREDADA)
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino / FICHERO_MODELO)
    _escribir_json(
        destino / FICHERO_METADATOS,
        {
            "version": VERSION_HEREDADA,
            "origen": str(origen),
            "nota": (
                "Adoptado del esquema anterior, que guardaba un .pkl suelto. "
                "No se conocen sus metricas ni con que datos se entreno: "
                "reentrenar en cuanto sea posible."
            ),
        },
    )
    promover(base, VERSION_HEREDADA)
    logger.warning(
        "Se adopto el modelo heredado de %s como %s. Reentrenar para tener metricas.",
        origen, VERSION_HEREDADA,
    )
    return VERSION_HEREDADA
