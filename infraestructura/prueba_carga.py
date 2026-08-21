"""
Prueba de carga: aulas de alumnos haciendo el test a la vez.

Responde a la pregunta que importa para produccion: cuantos alumnos
simultaneos aguanta la instalacion antes de degradarse, y donde esta el
cuello de botella cuando se degrada.

No mide "peticiones por segundo" en abstracto: simula el recorrido real
(registro -> fase 1 -> fase 2 -> prediccion), que es lo que de verdad va a
pasar cuando un profesor diga "abran REVO" a 50 alumnos a la vez.

Uso:
    python infraestructura/prueba_carga.py                 # 50 alumnos
    ALUMNOS=200 python infraestructura/prueba_carga.py     # 200 alumnos
    ALUMNOS=50 OLEADAS=3 python infraestructura/prueba_carga.py
"""
from __future__ import annotations

import json
import os
import statistics
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API = os.environ.get("API", "http://localhost:8080/api")
ALUMNOS = int(os.environ.get("ALUMNOS", "50"))
OLEADAS = int(os.environ.get("OLEADAS", "1"))
CLAVE = "CargaRevo2026!"

_bloqueo = threading.Lock()
_latencias: dict[str, list[float]] = {}
_errores: dict[str, int] = {}


def registrar(etapa: str, segundos: float, fallo: bool = False) -> None:
    with _bloqueo:
        _latencias.setdefault(etapa, []).append(segundos)
        if fallo:
            _errores[etapa] = _errores.get(etapa, 0) + 1


def pedir(metodo, ruta, cuerpo=None, token=None, etapa=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(f"{API}{ruta}", data=datos, method=metodo)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            cuerpo_resp = json.loads(r.read() or b"null")
            estado = r.status
    except urllib.error.HTTPError as e:
        try:
            cuerpo_resp = json.loads(e.read() or b"null")
        except Exception:  # noqa: BLE001
            cuerpo_resp = None
        estado = e.code
    except Exception as exc:  # noqa: BLE001
        cuerpo_resp = {"error": str(exc)}
        estado = 0

    transcurrido = time.perf_counter() - inicio
    if etapa:
        registrar(etapa, transcurrido, fallo=estado >= 400 or estado == 0)
    return estado, cuerpo_resp


def recorrido_de_un_alumno(indice: int) -> tuple[bool, str]:
    """Un alumno completo, de registro a prediccion."""
    marca = f"{int(time.time() * 1000)}{indice}"

    estado, alta = pedir("POST", "/auth/register", {
        "email": f"carga.{marca}@uni.pe",
        "password": CLAVE,
        "full_name": f"Alumno Carga {indice}",
        "student_code": f"C{marca}",
        "semester": 7,
        "accept_terms": True,
    }, etapa="1. registro")
    if estado != 201:
        return False, f"registro {estado}"
    token = alta["access_token"]

    estado, sesion = pedir("POST", "/sessions/", {}, token, etapa="2. abrir sesion")
    if estado != 201:
        return False, f"sesion {estado}"
    sid = sesion["id"]

    estado, preguntas = pedir("GET", f"/sessions/{sid}/questions",
                              token=token, etapa="3. preguntas fase 1")
    if estado != 200 or not preguntas:
        return False, f"preguntas f1 {estado}"

    estado, _ = pedir("POST", f"/sessions/{sid}/answers", {
        "answers": [{"question_id": p["id"], "value": 4} for p in preguntas]
    }, token, etapa="4. guardar fase 1")
    if estado != 200:
        return False, f"respuestas f1 {estado}"

    estado, _ = pedir("POST", f"/sessions/{sid}/submit_phase", {},
                      token, etapa="5. cerrar fase 1")
    if estado != 200:
        return False, f"cierre f1 {estado}"

    estado, preguntas2 = pedir("GET", f"/sessions/{sid}/questions",
                               token=token, etapa="6. preguntas fase 2")
    if estado != 200 or not preguntas2:
        return False, f"preguntas f2 {estado}"

    estado, _ = pedir("POST", f"/sessions/{sid}/answers", {
        "answers": [{"question_id": p["id"], "value": 4} for p in preguntas2]
    }, token, etapa="7. guardar fase 2")
    if estado != 200:
        return False, f"respuestas f2 {estado}"

    estado, cierre = pedir("POST", f"/sessions/{sid}/submit_phase", {},
                           token, etapa="8. cierre + prediccion")
    if estado != 200 or not isinstance(cierre, dict) or "prediction_id" not in cierre:
        return False, f"prediccion {estado}"

    return True, "ok"


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, int(round(p / 100 * (len(ordenados) - 1))))
    return ordenados[indice]


def main() -> None:
    total = ALUMNOS * OLEADAS
    print(f"Simulando {ALUMNOS} alumnos simultaneos"
          f"{f' x {OLEADAS} oleadas' if OLEADAS > 1 else ''} contra {API}")
    print("Cada alumno hace el recorrido completo: registro, 25 respuestas y prediccion.\n")

    completados, fallidos, motivos = 0, 0, {}
    arranque = time.perf_counter()

    for oleada in range(OLEADAS):
        if OLEADAS > 1:
            print(f"-- oleada {oleada + 1}/{OLEADAS}")
        with ThreadPoolExecutor(max_workers=ALUMNOS) as pool:
            futuros = [pool.submit(recorrido_de_un_alumno, oleada * ALUMNOS + i)
                       for i in range(ALUMNOS)]
            for futuro in as_completed(futuros):
                bien, motivo = futuro.result()
                if bien:
                    completados += 1
                else:
                    fallidos += 1
                    motivos[motivo] = motivos.get(motivo, 0) + 1

    duracion = time.perf_counter() - arranque
    peticiones = sum(len(v) for v in _latencias.values())

    print(f"\n=== RESULTADO ===\n")
    print(f"  Alumnos completos:    {completados}/{total}")
    print(f"  Alumnos fallidos:     {fallidos}")
    if motivos:
        for motivo, veces in sorted(motivos.items(), key=lambda x: -x[1]):
            print(f"      {veces}x {motivo}")
    print(f"  Peticiones totales:   {peticiones}")
    print(f"  Duracion:             {duracion:.1f} s")
    print(f"  Rendimiento:          {peticiones / duracion:.1f} peticiones/s")
    print(f"                        {completados / duracion * 60:.0f} alumnos completos por minuto")

    print(f"\n=== LATENCIA POR ETAPA (segundos) ===\n")
    print(f"  {'etapa':<26} {'n':>4} {'mediana':>9} {'p95':>9} {'max':>9} {'errores':>8}")
    for etapa in sorted(_latencias):
        v = _latencias[etapa]
        print(f"  {etapa:<26} {len(v):>4} {statistics.median(v):>9.2f} "
              f"{percentil(v, 95):>9.2f} {max(v):>9.2f} {_errores.get(etapa, 0):>8}")

    todas = [x for v in _latencias.values() for x in v]
    print(f"\n  Latencia global: mediana {statistics.median(todas):.2f}s | "
          f"p95 {percentil(todas, 95):.2f}s | p99 {percentil(todas, 99):.2f}s")


if __name__ == "__main__":
    main()
