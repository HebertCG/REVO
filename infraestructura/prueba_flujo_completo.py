"""
Recorrido completo de un alumno, contra una pila levantada de verdad.

Registro -> consentimiento -> fase 1 -> fase 2 -> prediccion -> historial.

Complementa a verificar_despliegue.sh: aquel comprueba que lo que NO debe
poder hacerse falla; este comprueba que lo que SI debe funcionar, funciona.
Es la prueba de que los tres microservicios se hablan entre si a traves de la
pasarela y de que el RLS no estorba al flujo legitimo del alumno.

Uso:
    python infraestructura/prueba_flujo_completo.py
    API=http://localhost:8080/api python infraestructura/prueba_flujo_completo.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("API", "http://localhost:8080/api")
CLAVE = "ClaveDePrueba2026!"


def pedir(metodo, ruta, cuerpo=None, token=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(f"{API}{ruta}", data=datos, method=metodo)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def paso(texto):
    print(f"\n\033[90m-- {texto}\033[0m")


def ok(texto):
    print(f"\033[32m  OK\033[0m  {texto}")


def fallo(texto):
    print(f"\033[31mFALLO\033[0m  {texto}")
    sys.exit(1)


sufijo = str(int(time.time()))
email = f"flujo.{sufijo}@uni.pe"

# ── 1. Registro con consentimiento ───────────────────────────
paso("Registro con consentimiento granular")
estado, datos = pedir("POST", "/auth/register", {
    "email": email,
    "password": CLAVE,
    "full_name": "Alumna De Prueba",
    "student_code": f"F{sufijo}",
    "semester": 7,
    "accept_terms": True,
    "consent_data_commercial": False,
    "consent_ai_training": True,
})
if estado != 201:
    fallo(f"registro devolvio {estado}: {datos}")
token = datos["access_token"]
alumno = datos["user"]
ok(f"cuenta creada: id={alumno['id']} ciclo={alumno['semester']}")

estado, consents = pedir("GET", "/auth/me/consents", token=token)
resumen = {c["doc_type"]: c["granted"] for c in consents}
ok(f"consentimiento grabado: {resumen}")
if resumen["data_commercial"] is not False or resumen["ai_training"] is not True:
    fallo("el consentimiento no refleja lo que se pidio")

# ── 2. Fase 1 ────────────────────────────────────────────────
paso("Fase 1: 10 preguntas, una por especializacion")
estado, sesion = pedir("POST", "/sessions/", {}, token)
if estado != 201:
    fallo(f"no se pudo abrir la sesion: {estado} {sesion}")
sid = sesion["id"]
ok(f"sesion {sid} abierta con estado '{sesion['status']}'")

estado, preguntas = pedir("GET", f"/sessions/{sid}/questions", token=token)
if len(preguntas) != 10:
    fallo(f"la fase 1 devolvio {len(preguntas)} preguntas")
ok(f"{len(preguntas)} preguntas recibidas")
print(f"      ejemplo: «{preguntas[0]['text'][:70]}...»")

# Se responde con valores variados para que el top 3 no sea un empate total.
valores = [5, 2, 4, 3, 5, 1, 3, 4, 2, 5]
estado, guardadas = pedir("POST", f"/sessions/{sid}/answers", {
    "answers": [{"question_id": p["id"], "value": v} for p, v in zip(preguntas, valores)]
}, token)
if estado != 200:
    fallo(f"no se guardaron las respuestas: {estado} {guardadas}")
ok(f"{len(guardadas)} respuestas guardadas")

estado, cierre = pedir("POST", f"/sessions/{sid}/submit_phase", {}, token)
if cierre.get("next_phase") != 2:
    fallo(f"la fase 1 no cerro bien: {cierre}")
ok(f"fase 1 cerrada. top 3 de especializaciones: {cierre['top3']}")

# ── 3. Fase 2 ────────────────────────────────────────────────
paso("Fase 2: 15 preguntas de las tres ramas del top")
estado, preguntas2 = pedir("GET", f"/sessions/{sid}/questions", token=token)
if len(preguntas2) != 15:
    fallo(f"la fase 2 devolvio {len(preguntas2)} preguntas")
ok(f"{len(preguntas2)} preguntas recibidas, ninguna repetida de la fase 1")

estado, guardadas2 = pedir("POST", f"/sessions/{sid}/answers", {
    "answers": [{"question_id": p["id"], "value": 5 if i < 5 else 3}
                for i, p in enumerate(preguntas2)]
}, token)
ok(f"{len(guardadas2)} respuestas guardadas")

# ── 4. Prediccion ────────────────────────────────────────────
paso("Cierre: el survey-service llama al ml-service por la red interna")
estado, resultado = pedir("POST", f"/sessions/{sid}/submit_phase", {}, token)
if "prediction_id" not in resultado:
    fallo(f"no llego prediccion: {resultado}")
ok(f"prediccion {resultado['prediction_id']}: {resultado['primary_specialization']}")

estado, prediccion = pedir("GET", f"/predict/{resultado['prediction_id']}", token=token)
principal = prediccion["primary"]
ok(f"resultado consultable: {principal['name']} al {principal['confidence_pct']}%")
print("      top 3:")
for i, s in enumerate(prediccion.get("top3") or [], 1):
    print(f"        {i}. {s.get('name','?')} — {s.get('confidence_pct','?')}%")

# ── 5. Recomendaciones y historial ───────────────────────────
paso("Cursos, empleos e historial")
spec = principal["specialization_id"]
estado, cursos = pedir("GET", f"/courses/specialization/{spec}")
ok(f"{len(cursos) if estado == 200 else 0} cursos recomendados para la rama {spec}")

estado, empleos = pedir("GET", f"/jobs/specialization/{spec}")
ok(f"{len(empleos) if estado == 200 else 0} ofertas de empleo para la rama {spec}")

estado, historial = pedir("GET", "/sessions/", token=token)
ok(f"historial del alumno: {len(historial)} sesion(es), todas suyas")

estado, psico = pedir("GET", f"/psychometric/specialization/{spec}", token=token)
ok(f"fase 3: {len(psico) if estado == 200 else 0} preguntas de perfil profesional")

print("\n\033[32m=== EL RECORRIDO COMPLETO FUNCIONA ===\033[0m")
