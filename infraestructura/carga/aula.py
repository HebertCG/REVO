"""
aula.py — Un aula de alumnos usando REVO de verdad, de principio a fin.

Corre DENTRO de un contenedor, uno por aula. No es un detalle: la pasarela y
los servicios limitan el acceso por IP (80 altas cada 10 minutos, 400 inicios
de sesion por hora, 30 peticiones/s en nginx), y en la vida real cada salon
sale a internet por su propio router. Un contenedor por aula reproduce eso:
cada uno tiene su IP en la red de Docker. Lanzar cientos de alumnos desde una
sola IP mediria el limitador, no el sistema.

QUE HACE CADA ALUMNO, EN UN CICLO

    entrar         registro (primer ciclo) o inicio de sesion (los siguientes)
    panel          su perfil y su historial de resultados
    test           abrir sesion, fase 1, fase 2 y prediccion
    resultado      el resultado, los cursos y las preguntas de la fase 3
    realimentacion "¿la IA te leyo bien?" (el 70 % de las veces)
    progreso       su historial otra vez, que es donde se ve la evolucion

Las respuestas son aleatorias y distintas por alumno y ciclo: con respuestas
fijas todos obtendrian la misma prediccion, y eso no carga el modelo igual.

LAS PAUSAS

Un alumno real tarda ~1 minuto en la fase 1 y ~1,5 en la fase 2. Las pausas
se escalan con ESCALA_TIEMPO (0.2 = cinco veces mas rapido que la realidad):
la prueba es MAS dura que un aula real, no menos. Se declara en el informe.

Solo biblioteca estandar: el contenedor es python:3.11-alpine, sin pip.

Entorno:
    API            http://pasarela/api
    AULA           identificador del aula (entero)
    ALUMNOS        alumnos del aula (45)
    CICLO          numero de ciclo (1 = se registran)
    ESCALA_TIEMPO  factor de las pausas (1.0 = tiempo real)
    LLEGADA_S      ventana en la que van llegando los alumnos al aula
    SEMILLA        para reproducir la misma prueba
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = os.environ.get("API", "http://pasarela/api")
AULA = int(os.environ.get("AULA", "1"))
ALUMNOS = int(os.environ.get("ALUMNOS", "45"))
CICLO = int(os.environ.get("CICLO", "1"))
ESCALA = float(os.environ.get("ESCALA_TIEMPO", "0.2"))
LLEGADA_S = float(os.environ.get("LLEGADA_S", "60"))
SEMILLA = int(os.environ.get("SEMILLA", "2026"))
CLAVE = "CargaRevo2026!"

#: Segundos REALES que tarda un alumno en cada tramo (antes de escalar).
PAUSAS = {
    "leer_panel": (5, 15),
    "fase_1": (40, 80),
    "fase_2": (60, 120),
    "leer_resultado": (20, 45),
    "leer_historial": (5, 15),
}

_bloqueo = threading.Lock()
_latencias: dict[str, list[float]] = {}
_errores: dict[str, dict[str, int]] = {}


def anotar(etapa: str, segundos: float, estado: int) -> None:
    with _bloqueo:
        _latencias.setdefault(etapa, []).append(round(segundos, 4))
        if estado >= 400 or estado == 0:
            por_estado = _errores.setdefault(etapa, {})
            por_estado[str(estado)] = por_estado.get(str(estado), 0) + 1


def pedir(etapa: str, metodo: str, ruta: str, cuerpo=None, token=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(f"{API}{ruta}", data=datos, method=metodo)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            estado, respuesta = r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        estado, respuesta = e.code, None
    except Exception:  # noqa: BLE001 - red caida, timeout: cuenta como fallo 0
        estado, respuesta = 0, None
    anotar(etapa, time.perf_counter() - inicio, estado)
    return estado, respuesta


def pausa(azar: random.Random, tramo: str) -> None:
    minimo, maximo = PAUSAS[tramo]
    time.sleep(azar.uniform(minimo, maximo) * ESCALA)


def entrar(indice: int, azar: random.Random) -> tuple[str | None, int | None]:
    """Registro el primer ciclo; inicio de sesion los demas."""
    email = f"aula{AULA}.alumno{indice}@carga.revo.pe"
    if CICLO == 1:
        estado, alta = pedir("entrar", "POST", "/auth/register", {
            "email": email, "password": CLAVE,
            "full_name": f"Alumno {indice} del aula {AULA}",
            "student_code": f"U{AULA:03d}{indice:03d}",
            "semester": 1, "accept_terms": True,
        })
        ok = estado == 201
    else:
        estado, alta = pedir("entrar", "POST", "/auth/login",
                             {"email": email, "password": CLAVE})
        ok = estado == 200
    if not ok or not alta:
        return None, None

    token = alta.get("access_token")
    estado, yo = pedir("panel", "GET", "/auth/me", token=token)
    return token, (yo or {}).get("id")


def responder(preguntas: list[dict], azar: random.Random) -> dict:
    return {"answers": [{"question_id": p["id"], "value": azar.randint(1, 5)}
                        for p in preguntas]}


def un_alumno(indice: int) -> str:
    azar = random.Random(f"{SEMILLA}-{AULA}-{indice}-{CICLO}")
    time.sleep(azar.uniform(0, LLEGADA_S))   # van llegando al aula

    token, uid = entrar(indice, azar)
    if not token:
        return "no pudo entrar"

    pedir("panel", "GET", "/auth/me/consents", token=token)
    pedir("panel", "GET", f"/predict/user/{uid}/history", token=token)
    pausa(azar, "leer_panel")

    estado, sesion = pedir("test", "POST", "/sessions/", {}, token)
    if estado != 201:
        return f"sesion {estado}"
    sid = sesion["id"]

    for fase, tramo in ((1, "fase_1"), (2, "fase_2")):
        estado, preguntas = pedir("test", "GET", f"/sessions/{sid}/questions", token=token)
        if estado != 200 or not preguntas:
            return f"preguntas fase {fase} {estado}"
        pausa(azar, tramo)
        estado, _ = pedir("test", "POST", f"/sessions/{sid}/answers",
                          responder(preguntas, azar), token)
        if estado != 200:
            return f"respuestas fase {fase} {estado}"
        etapa = "prediccion" if fase == 2 else "test"
        estado, cierre = pedir(etapa, "POST", f"/sessions/{sid}/submit_phase", {}, token)
        if estado != 200:
            return f"cierre fase {fase} {estado}"

    pid = (cierre or {}).get("prediction_id")
    if not pid:
        return "sin prediccion"

    estado, resultado = pedir("resultado", "GET", f"/predict/{pid}", token=token)
    rama = ((resultado or {}).get("primary") or {}).get("specialization_id", 1)
    pedir("resultado", "GET", f"/courses/specialization/{rama}", token=token)
    pedir("resultado", "GET", f"/psychometric/specialization/{rama}", token=token)
    pausa(azar, "leer_resultado")

    if azar.random() < 0.7:
        pedir("realimentacion", "POST", f"/predict/{pid}/feedback", {
            "diagnostic_affinity": azar.random() < 0.75,
            "discovery_level": azar.choice(["known", "new"]),
        }, token)

    pedir("progreso", "GET", "/sessions/", token=token)
    pedir("progreso", "GET", f"/predict/user/{uid}/history", token=token)
    pausa(azar, "leer_historial")
    return "ok"


def main() -> None:
    inicio = time.time()
    motivos: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=ALUMNOS) as pool:
        for motivo in pool.map(un_alumno, range(1, ALUMNOS + 1)):
            motivos[motivo] = motivos.get(motivo, 0) + 1

    print(json.dumps({
        "aula": AULA, "ciclo": CICLO, "alumnos": ALUMNOS,
        "inicio": inicio, "fin": time.time(),
        "completos": motivos.pop("ok", 0), "fallos": motivos,
        "latencias": _latencias, "errores": _errores,
    }))


if __name__ == "__main__":
    main()
